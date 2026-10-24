from careerpilot.rag.chunking import chunk_document
from careerpilot.rag.evidence import (
    build_evidence_units,
    linearize_table_row,
    linearize_triple,
)
from careerpilot.rag.models import (
    ChunkLevel,
    EvidenceKind,
    KnowledgeOrigin,
    KnowledgeTriple,
    SourceDocument,
)


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
        source_type="developer_upload",
        domain="preparation_material",
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
    assert EvidenceKind.TABLE in kinds
    assert EvidenceKind.TABLE_COLUMN in kinds
    assert EvidenceKind.TABLE_ROW in kinds
    assert EvidenceKind.TABLE_FACT in kinds
    triple = next(unit for unit in units if unit.kind is EvidenceKind.KG_TRIPLE)
    child = next(chunk for chunk in chunks if chunk.chunk_level is ChunkLevel.CHILD)
    parent = next(chunk for chunk in chunks if chunk.chunk_level is ChunkLevel.PARENT)
    assert triple.parent_id == child.id
    assert child.parent_id == parent.id
    assert triple.source_uri == document.source_uri
    assert triple.subject == "AI产品经理"
    assert triple.predicate == "需要"
    assert triple.object == "理解大模型能力边界"
    assert all(unit.metadata["source_tier"] == 2 for unit in units)
    assert len({unit.id for unit in units}) == len(units)

    table = next(unit for unit in units if unit.kind is EvidenceKind.TABLE)
    columns = [unit for unit in units if unit.kind is EvidenceKind.TABLE_COLUMN]
    row = next(unit for unit in units if unit.kind is EvidenceKind.TABLE_ROW)
    facts = [unit for unit in units if unit.kind is EvidenceKind.TABLE_FACT]
    assert len(columns) == 2
    assert row.parent_id == table.id
    assert all(column.parent_id == table.id for column in columns)
    assert all(fact.parent_id == row.id for fact in facts)
    assert {fact.metadata["column_id"] for fact in facts} == {column.id for column in columns}


def test_graph_evidence_is_only_built_for_curated_preparation_knowledge() -> None:
    triples = [{"subject": "产品经理", "relation": "需要", "object": "用户研究"}]
    job = SourceDocument(
        "job",
        "岗位",
        "https://example.com/job",
        "web_job",
        "job_opportunity",
        "产品经理岗位。",
        metadata={"triples": triples},
    )
    personal = SourceDocument(
        "personal",
        "私人笔记",
        "file:///note.docx",
        "user_upload",
        "personal_material",
        "我的用户研究经历。",
        metadata={"triples": triples},
        knowledge_origin=KnowledgeOrigin.USER_PROVIDED,
        owner_user_id="user-1",
    )

    for document in (job, personal):
        chunks = chunk_document(document)
        units = build_evidence_units(document, chunks)
        assert all(unit.kind is not EvidenceKind.KG_TRIPLE for unit in units)
