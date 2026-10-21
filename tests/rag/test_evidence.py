from careerpilot.rag.chunking import chunk_document
from careerpilot.rag.evidence import (
    build_evidence_units,
    linearize_table_row,
    linearize_triple,
)
from careerpilot.rag.models import EvidenceKind, KnowledgeTriple, SourceDocument


def test_linearizes_triple_as_query_readable_statement() -> None:
    triple = KnowledgeTriple("AI产品经理", "需要", "理解大模型能力边界")

    assert linearize_triple(triple) == (
        "[KG_TRIPLE] AI产品经理 | 需要 | 理解大模型能力边界"
    )


def test_linearizes_table_row_with_explicit_row_identity() -> None:
    text = linearize_table_row(
        "job_postings",
        "job-032",
        {"职位": "AI产品经理", "城市": "上海", "截止日期": "2026-10-31"},
    )

    assert text == (
        "[TABLE_ROW table=job_postings row=job-032] "
        "(职位, AI产品经理) | (城市, 上海) | (截止日期, 2026-10-31)"
    )


def test_builds_passage_triple_and_table_evidence_with_provenance() -> None:
    document = SourceDocument(
        id="doc-1",
        title="AI 产品岗位样本",
        source_uri="https://example.com/jobs",
        source_type="web_job",
        domain="job_opportunity",
        text="AI 产品经理需要理解模型边界。",
        metadata={
            "source_tier": 2,
            "source_level": "A",
            "triples": [
                {
                    "subject": "AI产品经理",
                    "relation": "需要",
                    "object": "理解大模型能力边界",
                    "chunk_ordinal": 0,
                }
            ],
            "table_name": "job_postings",
            "table_rows": [
                {
                    "row_id": "job-032",
                    "values": {"职位": "AI产品经理", "城市": "上海"},
                }
            ],
        },
    )
    chunks = chunk_document(document)

    units = build_evidence_units(document, chunks)

    kinds = {unit.kind for unit in units}
    assert EvidenceKind.PASSAGE in kinds
    assert EvidenceKind.KG_TRIPLE in kinds
    assert EvidenceKind.TABLE_ROW in kinds
    assert EvidenceKind.TABLE_FACT in kinds
    triple = next(unit for unit in units if unit.kind is EvidenceKind.KG_TRIPLE)
    assert triple.parent_id == chunks[0].id
    assert triple.source_uri == document.source_uri
    assert triple.subject == "AI产品经理"
    assert triple.predicate == "需要"
    assert triple.object == "理解大模型能力边界"
    assert all(unit.metadata["source_tier"] == 2 for unit in units)
    assert len({unit.id for unit in units}) == len(units)
