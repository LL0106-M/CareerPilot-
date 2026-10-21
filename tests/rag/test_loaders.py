from pathlib import Path

from pypdf import PdfWriter

from careerpilot.rag.loaders import load_markdown, load_pdf


def test_markdown_loader_maps_frontmatter_to_document(tmp_path: Path) -> None:
    source = tmp_path / "job.md"
    source.write_text(
        """---
document_id: didi-agent-pm
content_type: job_opportunity
source_type: web_job
title: 滴滴 AI Agent 产品经理
canonical_url: https://talent.didiglobal.com/social/p/63915
organization: 滴滴
location: 北京
published_at: 2026-10-08
---

# 滴滴 AI Agent 产品经理

负责工具调用、上下文、Memory 和任务编排。
""",
        encoding="utf-8",
    )

    document = load_markdown(source)

    assert document.id == "didi-agent-pm"
    assert document.domain == "job_opportunity"
    assert document.source_uri == "https://talent.didiglobal.com/social/p/63915"
    assert document.metadata["organization"] == "滴滴"
    assert "Memory" in document.text


def test_pdf_loader_creates_developer_upload_with_page_metadata(tmp_path: Path) -> None:
    source = tmp_path / "knowledge.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with source.open("wb") as output:
        writer.write(output)

    document = load_pdf(source, domain="ai_frontier")

    assert document.source_type == "developer_upload"
    assert document.domain == "ai_frontier"
    assert document.source_uri.startswith("file:")
    assert document.metadata["page_count"] == 1
    assert "Page 1" in document.text
