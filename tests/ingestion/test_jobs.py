from datetime import UTC, datetime

import pytest

from careerpilot.ingestion.jobs import job_to_document, normalize_job_record


def test_normalizes_job_record_without_erasing_employment_channel() -> None:
    job = normalize_job_record(
        {
            "company_name": "某央企",
            "role_title": "AI 产品经理",
            "locations": "北京、上海",
            "source_url": "https://jobs.example.cn/123?utm_source=feed&from=search",
            "apply_url": "https://jobs.example.cn/apply/123?spm=abc",
            "source_level": "S",
            "status": "active",
            "organization_type": "central_soe",
            "employment_type": "enterprise_contract",
            "recruiting_type": "soe_campus",
        },
        verified_at="2026-10-20",
    )

    assert job.role_family == "ai_product"
    assert job.locations == ("北京", "上海")
    assert job.source_url == "https://jobs.example.cn/123"
    assert job.apply_url == "https://jobs.example.cn/apply/123"
    assert job.organization_type == "central_soe"
    assert job.employment_type == "enterprise_contract"
    assert job.recruiting_type == "soe_campus"


def test_job_identity_is_stable_across_tracking_parameters() -> None:
    base = {
        "company_name": "示例公司",
        "role_title": "Agent 产品经理",
        "locations": ["杭州"],
        "source_level": "A",
        "status": "unknown",
    }

    left = normalize_job_record(
        {**base, "source_url": "https://example.com/jobs/7?utm_source=a"},
        verified_at="2026-10-20",
    )
    right = normalize_job_record(
        {**base, "source_url": "https://example.com/jobs/7?from=b"},
        verified_at="2026-10-20",
    )

    assert left.identity == right.identity


def test_missing_identity_fields_are_rejected() -> None:
    with pytest.raises(ValueError, match="company_name"):
        normalize_job_record(
            {
                "role_title": "产品经理",
                "source_url": "https://example.com/jobs/1",
                "source_level": "S",
                "status": "active",
            },
            verified_at="2026-10-20",
        )


@pytest.mark.parametrize("status", ["active", "unknown", "expired"])
def test_lead_source_must_remain_unverified(status: str) -> None:
    with pytest.raises(ValueError, match="unverified_lead"):
        normalize_job_record(
            {
                "company_name": "线索公司",
                "role_title": "产品经理",
                "source_url": "https://community.example/jobs/1",
                "source_level": "B",
                "status": status,
            },
            verified_at="2026-10-20",
        )


def test_job_document_contains_structured_table_row_and_provenance() -> None:
    job = normalize_job_record(
        {
            "company_name": "示例公司",
            "role_title": "大模型产品经理",
            "locations": ["深圳"],
            "source_url": "https://example.com/jobs/9",
            "source_level": "S",
            "status": "active",
            "requirements": "熟悉 Agent 与 RAG",
        },
        verified_at="2026-10-20",
    )

    document = job_to_document(job, fetched_at=datetime(2026, 10, 20, 12, tzinfo=UTC))

    assert document.id == job.identity
    assert document.domain == "job_opportunity"
    assert document.source_uri == "https://example.com/jobs/9"
    assert document.metadata["source_tier"] == 1
    row = document.metadata["table_rows"][0]
    assert row["row_id"] == job.identity
    assert row["values"]["requirements"] == "熟悉 Agent 与 RAG"
    assert "来源等级：S" in document.text
