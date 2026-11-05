from dataclasses import dataclass, field

import pytest

from careerpilot.knowledge.collection import KnowledgeCollectionProcessor
from careerpilot.product_store import ProductStore
from careerpilot.rag.store import SqliteRagStore
from careerpilot.search.models import SearchStrategy, WebSearchResponse, WebSearchSource


@dataclass
class RecordingSearch:
    calls: list[tuple[str, SearchStrategy]] = field(default_factory=list)

    async def search(self, query: str, strategy: SearchStrategy) -> WebSearchResponse:
        self.calls.append((query, strategy))
        return WebSearchResponse(
            answer="找到一个带来源的岗位页面。",
            sources=(
                WebSearchSource(
                    url="https://careers.example.com/jobs/agent-pm",
                    title="Agent 产品经理",
                    site_name="Example Careers",
                    snippet="Example 公司发布的 Agent 产品经理岗位。",
                ),
            ),
            strategy=strategy,
        )


@pytest.mark.asyncio
async def test_processor_claims_queued_job_and_saves_sources_to_jobs_library(tmp_path) -> None:
    product = ProductStore(tmp_path / "product.db")
    rag = SqliteRagStore(tmp_path / "rag.db")
    search = RecordingSearch()
    product.record_direction_signal(
        "owner-1",
        source_run_id="run-1",
        label="Agent 产品经理",
        explicitness="explicit",
        source_quote="我想申请 Agent 产品经理",
        reason="明确申请意图",
        confidence=0.96,
    )

    result = await KnowledgeCollectionProcessor(product, rag, search).process_for_owner(
        "owner-1", purpose="job_opportunity"
    )

    assert result.processed == 1
    assert result.saved == 1
    assert search.calls == [("Agent 产品经理 最新招聘 官方", SearchStrategy.TURBO)]
    saved = rag.list_documents_for_domains(("job_source",))
    assert [row["source_uri"] for row in saved] == [
        "https://careers.example.com/jobs/agent-pm"
    ]
    job = product.list_collection_jobs("owner-1")[0]
    assert job["status"] == "completed"
    assert job["result_count"] == 1


@pytest.mark.asyncio
async def test_processor_marks_empty_search_partial_instead_of_claiming_success(tmp_path) -> None:
    product = ProductStore(tmp_path / "product.db")
    rag = SqliteRagStore(tmp_path / "rag.db")
    search = RecordingSearch()

    async def empty(query: str, strategy: SearchStrategy) -> WebSearchResponse:
        return WebSearchResponse(answer="", sources=(), strategy=strategy, partial=True)

    search.search = empty  # type: ignore[method-assign]
    product.record_direction_signal(
        "owner-1",
        source_run_id="run-1",
        label="AI 产品经理",
        explicitness="explicit",
        source_quote="我想申请 AI 产品经理",
        reason="明确申请意图",
        confidence=0.96,
    )

    result = await KnowledgeCollectionProcessor(product, rag, search).process_for_owner(
        "owner-1", purpose="job_opportunity"
    )

    assert result.saved == 0
    job = product.list_collection_jobs("owner-1")[0]
    assert job["status"] == "partial"
    assert job["last_error"] == "no_sources_found"
