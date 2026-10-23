import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

from careerpilot.ingestion.jobs import JobRecord, normalize_job_record


class ExtractedJobFields(BaseModel):
    company_name: str
    role_title: str
    role_family: str = "other"
    recruiting_type: str = "unknown"
    organization_type: str = "unknown"
    employment_type: str = "unknown"
    target_graduation: str = "not_specified"
    locations: list[str] = Field(default_factory=list)
    deadline: str | None = None
    apply_url: str | None = None
    posted_at: str | None = None
    job_description: str = ""
    requirements: str = ""


def extract_job_record(
    text: str,
    *,
    source_url: str,
    verified_at: str,
    source_level: str = "S",
    source_name: str = "",
    model: Any | None = None,
) -> JobRecord:
    """Extract a validated JobRecord from raw page text; LLM is optional, schema is not."""
    values = _extract_with_model(text, model) if model is not None else _extract_labels(text)
    values.update(
        {
            "source_url": source_url,
            "apply_url": values.get("apply_url") or source_url,
            "source_level": source_level,
            "source_name": source_name,
            "status": "active" if source_level in {"S", "A"} else "unverified_lead",
        }
    )
    return normalize_job_record(values, verified_at=verified_at)


def _extract_with_model(text: str, model: Any) -> dict[str, Any]:
    structured = model.with_structured_output(ExtractedJobFields)
    prompt = (
        "从招聘原文抽取岗位字段。只填写原文明示的信息；不确定时使用 unknown、空列表或 null。"
        "organization_type 只能是 private/central_soe/local_soe/government/"
        "public_institution/unknown；employment_type 只能是 civil_service_establishment/"
        "public_institution_establishment/enterprise_contract/labor_dispatch/internship/unknown。"
        "截止时间和发布日期尽可能规范为 ISO 日期。\n\n招聘原文：\n" + text[:30000]
    )
    parsed = structured.invoke(prompt)
    if isinstance(parsed, Mapping):
        return dict(parsed)
    return parsed.model_dump()


def _extract_labels(text: str) -> dict[str, Any]:
    labels = {
        "company_name": ("企业名称", "公司名称", "单位名称", "招聘单位"),
        "role_title": ("岗位名称", "职位名称", "招聘岗位", "岗位"),
        "organization_type": ("企业类型", "单位类型", "组织类型"),
        "employment_type": ("用工类型", "编制类型", "聘用类型"),
        "recruiting_type": ("招聘类型", "招聘类别"),
        "target_graduation": ("毕业年份", "面向届次", "招聘对象"),
        "locations": ("工作地点", "岗位地点", "地点"),
        "deadline": ("投递截止时间", "截止时间", "报名截止"),
        "apply_url": ("投递链接", "申请链接", "报名链接"),
        "posted_at": ("发布时间", "发布日期"),
        "job_description": ("岗位描述", "岗位职责", "工作职责"),
        "requirements": ("任职要求", "岗位要求", "应聘条件"),
    }
    result: dict[str, Any] = {}
    for field, candidates in labels.items():
        value = _labeled_value(text, candidates)
        if value:
            result[field] = re.split(r"[、,，/;；\s]+", value) if field == "locations" else value
    if not result.get("company_name") or not result.get("role_title"):
        raise ValueError("raw job text requires company_name and role_title labels without a model")
    return result


def _labeled_value(text: str, labels: tuple[str, ...]) -> str | None:
    joined = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:^|\n)\s*(?:{joined})\s*[：:]\s*([^\n]+)", text)
    return match.group(1).strip() if match else None
