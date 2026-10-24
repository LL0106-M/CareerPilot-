import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from careerpilot.rag.models import KnowledgeOrigin, SourceDocument

_TRACKING_KEYS = {"from", "source", "token", "spm"}
_SOURCE_LEVELS = frozenset({"S", "A", "B", "C"})
_STATUSES = frozenset({"active", "expired", "unknown", "unverified_lead"})
_ORGANIZATION_TYPES = frozenset(
    {"private", "central_soe", "local_soe", "government", "public_institution", "unknown"}
)
_EMPLOYMENT_TYPES = frozenset(
    {
        "civil_service_establishment",
        "public_institution_establishment",
        "enterprise_contract",
        "labor_dispatch",
        "internship",
        "unknown",
    }
)


@dataclass(frozen=True, slots=True)
class JobRecord:
    identity: str
    company_name: str
    role_title: str
    role_family: str
    recruiting_type: str
    organization_type: str
    employment_type: str
    target_graduation: str
    locations: tuple[str, ...]
    deadline: str | None
    apply_url: str
    source_url: str
    source_level: str
    source_name: str
    posted_at: str | None
    verified_at: str
    job_description: str
    requirements: str
    status: str
    confidence_note: str

    @property
    def content_hash(self) -> str:
        values = asdict(self)
        # Verification time describes our crawl, not a change on the source page.
        values.pop("verified_at", None)
        payload = json.dumps(values, ensure_ascii=False, sort_keys=True)
        return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()}"


def normalize_job_record(record: Mapping[str, Any], *, verified_at: str) -> JobRecord:
    company_name = _required(record, "company_name")
    role_title = _required(record, "role_title")
    source_url = _clean_url(str(record.get("source_url") or record.get("apply_url") or ""))
    if not source_url:
        raise ValueError("source_url is required")
    apply_url = _clean_url(str(record.get("apply_url") or source_url))
    source_level = str(record.get("source_level") or "").upper()
    if source_level not in _SOURCE_LEVELS:
        raise ValueError("source_level must be one of S, A, B, C")
    status = str(record.get("status") or "")
    if status not in _STATUSES:
        raise ValueError("status must be active, expired, unknown, or unverified_lead")
    if source_level in {"B", "C"} and status != "unverified_lead":
        raise ValueError("B/C source records must use unverified_lead until officially verified")
    organization_type = str(record.get("organization_type") or "unknown")
    if organization_type not in _ORGANIZATION_TYPES:
        raise ValueError(f"unsupported organization_type: {organization_type}")
    employment_type = str(record.get("employment_type") or "unknown")
    if employment_type not in _EMPLOYMENT_TYPES:
        raise ValueError(f"unsupported employment_type: {employment_type}")
    locations = _locations(record.get("locations"))
    recruiting_type = str(record.get("recruiting_type") or "unknown")
    role_family = str(record.get("role_family") or _infer_role_family(role_title))
    identity_seed = "|".join(
        (source_url, company_name, role_title, recruiting_type, ",".join(locations))
    )
    identity = f"job-{hashlib.sha256(identity_seed.encode()).hexdigest()[:24]}"
    return JobRecord(
        identity=identity,
        company_name=company_name,
        role_title=role_title,
        role_family=role_family,
        recruiting_type=recruiting_type,
        organization_type=organization_type,
        employment_type=employment_type,
        target_graduation=str(record.get("target_graduation") or "not_specified"),
        locations=locations,
        deadline=_optional(record.get("deadline")),
        apply_url=apply_url,
        source_url=source_url,
        source_level=source_level,
        source_name=str(record.get("source_name") or ""),
        posted_at=_optional(record.get("posted_at")),
        verified_at=verified_at,
        job_description=str(record.get("job_description") or "").strip(),
        requirements=str(record.get("requirements") or "").strip(),
        status=status,
        confidence_note=str(record.get("confidence_note") or "").strip(),
    )


def job_to_document(job: JobRecord, *, fetched_at: datetime) -> SourceDocument:
    values = {
        "company_name": job.company_name,
        "role_title": job.role_title,
        "role_family": job.role_family,
        "recruiting_type": job.recruiting_type,
        "organization_type": job.organization_type,
        "employment_type": job.employment_type,
        "target_graduation": job.target_graduation,
        "locations": "、".join(job.locations),
        "deadline": job.deadline or "未公开",
        "status": job.status,
        "requirements": job.requirements,
        "apply_url": job.apply_url,
        "verified_at": job.verified_at,
    }
    text = "\n".join(
        (
            f"# {job.company_name}｜{job.role_title}",
            "",
            f"- 岗位方向：{job.role_family}",
            f"- 招聘类型：{job.recruiting_type}",
            f"- 单位类型：{job.organization_type}",
            f"- 用工/编制类型：{job.employment_type}",
            f"- 地点：{'、'.join(job.locations)}",
            f"- 截止时间：{job.deadline or '未公开'}",
            f"- 状态：{job.status}",
            f"- 来源等级：{job.source_level}",
            f"- 核验时间：{job.verified_at}",
            f"- 投递地址：{job.apply_url}",
            "",
            "## 岗位描述",
            job.job_description or "来源未提供。",
            "",
            "## 任职要求",
            job.requirements or "来源未提供。",
        )
    )
    return SourceDocument(
        id=job.identity,
        title=f"{job.company_name}｜{job.role_title}",
        source_uri=job.source_url,
        source_type=_source_type(job.source_level),
        domain="job_opportunity",
        text=text,
        metadata={
            "source_tier": {"S": 1, "A": 2, "B": 3, "C": 4}[job.source_level],
            "source_level": job.source_level,
            "status": job.status,
            "content_hash": job.content_hash,
            "table_name": "job_record",
            "table_rows": [{"row_id": job.identity, "values": values}],
        },
        published_at=job.posted_at,
        fetched_at=fetched_at.isoformat(),
        knowledge_origin=KnowledgeOrigin.SYSTEM_WEB,
    )


def job_to_storage_record(job: JobRecord) -> dict[str, object]:
    return {
        "id": job.identity,
        "company_name": job.company_name,
        "role_title": job.role_title,
        "role_family": job.role_family,
        "recruiting_type": job.recruiting_type,
        "organization_type": job.organization_type,
        "employment_type": job.employment_type,
        "locations_json": json.dumps(job.locations, ensure_ascii=False),
        "deadline": job.deadline,
        "apply_url": job.apply_url,
        "source_url": job.source_url,
        "source_level": job.source_level,
        "source_name": job.source_name,
        "posted_at": job.posted_at,
        "verified_at": job.verified_at,
        "job_description": job.job_description,
        "requirements": job.requirements,
        "status": job.status,
        "knowledge_origin": "system_web",
        "owner_user_id": None,
    }


def _required(record: Mapping[str, Any], field: str) -> str:
    value = str(record.get(field) or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _clean_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    split = urlsplit(value)
    query = [
        (key, item)
        for key, item in parse_qsl(split.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_KEYS and not key.lower().startswith("utm_")
    ]
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), ""))


def _locations(value: object) -> tuple[str, ...]:
    raw = (
        value if isinstance(value, (list, tuple)) else re.split(r"[、,，/;；\s]+", str(value or ""))
    )
    result = tuple(dict.fromkeys(str(item).strip() for item in raw if str(item).strip()))
    return result or ("未注明",)


def _infer_role_family(title: str) -> str:
    compact = title.lower().replace(" ", "")
    if any(term in compact for term in ("ai产品", "agent产品", "大模型产品", "人工智能产品")):
        return "ai_product"
    if "产品" in compact:
        return "product"
    if any(term in compact for term in ("agent", "rag", "大模型应用", "ai应用")):
        return "ai_app"
    return "other"


def _source_type(level: str) -> str:
    return {
        "S": "official_job_page",
        "A": "authorized_job_page",
        "B": "job_lead",
        "C": "unverified_job_lead",
    }[level]


def _optional(value: object) -> str | None:
    normalized = str(value).strip() if value not in (None, "") else ""
    return normalized or None
