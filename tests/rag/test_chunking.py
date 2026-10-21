from careerpilot.rag.chunking import chunk_document
from careerpilot.rag.models import SourceDocument


def test_markdown_chunking_preserves_heading_and_source_metadata() -> None:
    document = SourceDocument(
        id="job-1",
        title="AI Agent 产品经理",
        source_uri="https://example.com/job/1",
        source_type="web_job",
        domain="job_opportunity",
        text=(
            "# AI Agent 产品经理\n\n"
            "## 岗位职责\n\n负责 Agent 规划、工具调用与效果评估。\n\n"
            "## 任职要求\n\n理解 RAG、Memory、MCP 与任务编排。"
        ),
        metadata={"organization": "示例公司", "location": "北京"},
    )

    chunks = chunk_document(document, max_chars=45, overlap_chars=8)

    assert len(chunks) >= 2
    assert chunks[0].document_id == "job-1"
    assert chunks[0].source_uri == "https://example.com/job/1"
    assert any(chunk.heading == "岗位职责" for chunk in chunks)
    assert any("RAG" in chunk.content for chunk in chunks)
    assert all(chunk.metadata["organization"] == "示例公司" for chunk in chunks)


def test_chunking_never_mixes_two_source_documents() -> None:
    first = SourceDocument("a", "A", "a", "upload", "ai_frontier", "甲" * 90)
    second = SourceDocument("b", "B", "b", "upload", "ai_frontier", "乙" * 90)

    chunks = chunk_document(first, max_chars=40, overlap_chars=5) + chunk_document(
        second, max_chars=40, overlap_chars=5
    )

    assert all("乙" not in chunk.content for chunk in chunks if chunk.document_id == "a")
    assert all("甲" not in chunk.content for chunk in chunks if chunk.document_id == "b")

