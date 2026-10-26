from dataclasses import replace

from careerpilot.rag.context import ContextAssembler
from careerpilot.rag.models import EvidenceKind, SearchHit
from careerpilot.search.models import WebSearchSource


def _hit(kind: EvidenceKind, *, evidence_id: str, metadata: dict) -> SearchHit:
    return SearchHit(
        chunk_id="child-1",
        document_id="doc-1",
        title="产品面试",
        heading="用户研究",
        content="用户研究能力可以通过访谈项目证明。",
        source_uri="file:///prep.md",
        source_type="developer_upload",
        domain="preparation_material",
        score=0.9,
        metadata=metadata,
        evidence_id=evidence_id,
        evidence_kind=kind,
        parent_id="parent-1",
        channels=("dense", "graph"),
    )


def test_context_pack_uses_passage_as_evidence_and_triple_as_navigation_clue() -> None:
    passage = _hit(
        EvidenceKind.PASSAGE,
        evidence_id="passage-1",
        metadata={"chunk_id": "child-1", "context_chunk_id": "parent-1"},
    )
    triple = _hit(
        EvidenceKind.KG_TRIPLE,
        evidence_id="triple-1",
        metadata={
            "chunk_id": "child-1",
            "context_chunk_id": "parent-1",
            "subject": "用户研究能力",
            "predicate": "可通过",
            "object": "访谈项目",
        },
    )

    pack = ContextAssembler().assemble(status="available", hits=(passage, triple))

    assert len(pack.evidence) == 1
    assert pack.evidence[0].citation_id == "S1"
    assert pack.evidence[0].evidence_kind == EvidenceKind.PASSAGE.value
    assert pack.relation_clues[0].supporting_citation_id == "S1"
    assert "navigation only" in pack.render_for_model()


def test_online_source_becomes_citable_only_when_it_has_a_snippet() -> None:
    pack = ContextAssembler().assemble(
        status="available",
        hits=(),
        online_sources=(
            WebSearchSource("https://a.example", "只有标题"),
            WebSearchSource(
                "https://b.example",
                "官方招聘",
                snippet="该岗位截止日期为 2026 年 12 月 31 日。",
            ),
        ),
        online_answer="搜索服务生成的摘要",
    )

    assert len(pack.evidence) == 1
    assert pack.evidence[0].source_uri == "https://b.example"
    assert pack.evidence[0].evidence_kind == "online_snippet"
    assert len(pack.online_sources) == 2


def test_context_pack_enforces_total_character_budget() -> None:
    first = _hit(EvidenceKind.PASSAGE, evidence_id="p1", metadata={"chunk_id": "c1"})
    second = replace(
        first,
        chunk_id="child-2",
        evidence_id="p2",
        content="第二条证据" * 1000,
        metadata={"chunk_id": "c2"},
    )
    first = replace(first, content="第一条证据" * 1000)

    pack = ContextAssembler().assemble(
        status="available",
        hits=(first, second),
        max_chars_per_evidence=10_000,
        max_total_chars=1_200,
    )

    assert sum(len(item.content) for item in pack.evidence) <= 1_200
