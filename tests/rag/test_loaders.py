from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfWriter

from careerpilot.rag.loaders import load_document, load_markdown, load_pdf


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


def test_pdf_image_ids_are_unique_across_pages() -> None:
    from careerpilot.rag.loaders import _scope_pdf_image

    image = {"image_id": "markdown-image-1", "object_uri": "page.png"}
    first = _scope_pdf_image(image, 1)
    second = _scope_pdf_image(image, 2)

    assert first["image_id"] != second["image_id"]


def test_markdown_loader_extracts_tables_and_registers_images(tmp_path: Path) -> None:
    image = tmp_path / "diagram.png"
    image.write_bytes(b"png")
    source = tmp_path / "knowledge.md"
    source.write_text(
        "# RAG 知识\n\n"
        "| 方法 | 用途 |\n"
        "| --- | --- |\n"
        "| 父子分块 | 上下文扩展 |\n\n"
        "![架构图](diagram.png)\n",
        encoding="utf-8",
    )

    document = load_document(source, domain="preparation_material")

    assert document.metadata["tables"][0]["rows"][0]["values"]["方法"] == "父子分块"
    assert document.metadata["images"][0]["object_uri"] == image.resolve().as_uri()


def test_docx_loader_extracts_text_and_table_without_office_runtime(tmp_path: Path) -> None:
    source = tmp_path / "interview.docx"
    document_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>面试准备</w:t></w:r></w:p>
        <w:tbl>
          <w:tr><w:tc><w:p><w:r><w:t>问题</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>答案</w:t></w:r></w:p></w:tc></w:tr>
          <w:tr><w:tc><w:p><w:r><w:t>什么是 RAG</w:t></w:r></w:p></w:tc>
                <w:tc><w:p><w:r><w:t>检索增强生成</w:t></w:r></w:p></w:tc></w:tr>
        </w:tbl>
      </w:body>
    </w:document>"""
    with ZipFile(source, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)

    document = load_document(source, domain="preparation_material")

    assert "面试准备" in document.text
    assert document.metadata["tables"][0]["rows"][0]["values"]["答案"] == "检索增强生成"
