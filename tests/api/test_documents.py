from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.config import Settings
from careerpilot.knowledge.collection import KnowledgeCollectionProcessor
from careerpilot.product_store import ProductStore
from careerpilot.rag.indexer import RagIndexer
from careerpilot.rag.models import KnowledgeOrigin, SourceDocument
from careerpilot.rag.store import SqliteRagStore
from careerpilot.search.models import SearchStrategy, WebSearchResponse, WebSearchSource
from tests.api.auth_helpers import build_auth_service, issue_session

OWNER = "550e8400-e29b-41d4-a716-446655440000"


def authenticated_client(tmp_path, settings, **app_kwargs):
    auth = build_auth_service(tmp_path / "auth.db")
    client = TestClient(create_app(settings, auth_service=auth, **app_kwargs))
    client.cookies.update(issue_session(auth, owner_id=OWNER))
    return client


def test_upload_document_persists_owner_scoped_file_and_metadata(tmp_path) -> None:
    rag_path = tmp_path / "rag" / "careerpilot.db"
    store = SqliteRagStore(rag_path)
    client = authenticated_client(
        tmp_path,
        Settings(_env_file=None, CAREERPILOT_RAG_DB_PATH=rag_path),
        rag_store=store,
    )

    response = client.post(
        "/v1/me/documents",
        params={"title": "我的简历.pdf", "category": "简历", "file_format": "PDF"},
        content=b"%PDF-1.7 test",
        headers={"content-type": "application/octet-stream"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "我的简历.pdf"
    assert payload["category"] == "简历"
    assert payload["status"] == "解析失败"
    assert client.get("/v1/me/documents").json()["items"][0]["id"] == payload["id"]
    uploaded = list((rag_path.parent / "uploads").rglob(f"{payload['id']}.*"))
    assert len(uploaded) == 1
    assert uploaded[0].read_bytes() == b"%PDF-1.7 test"


def test_upload_document_rejects_unsupported_or_oversized_content(tmp_path) -> None:
    rag_path = tmp_path / "rag.db"
    client = authenticated_client(
        tmp_path, Settings(_env_file=None, CAREERPILOT_RAG_DB_PATH=rag_path)
    )

    unsupported = client.post(
        "/v1/me/documents",
        params={"title": "photo.png", "category": "其他资料", "file_format": "PNG"},
        content=b"image",
        headers={"content-type": "application/octet-stream"},
    )

    assert unsupported.status_code == 422

def test_upload_document_enforces_configured_byte_limit(tmp_path) -> None:
    rag_path = tmp_path / "rag.db"
    client = authenticated_client(
        tmp_path,
        Settings(
            _env_file=None,
            CAREERPILOT_RAG_DB_PATH=rag_path,
            CAREERPILOT_MAX_UPLOAD_BYTES=4,
        ),
    )

    response = client.post(
        "/v1/me/documents",
        params={"title": "large.txt", "category": "其他资料", "file_format": "TXT"},
        content=b"12345",
        headers={"content-type": "application/octet-stream"},
    )

    assert response.status_code == 413


def test_uploaded_text_document_is_immediately_available_to_owner_retrieval(tmp_path) -> None:
    rag_path = tmp_path / "rag" / "careerpilot.db"
    store = SqliteRagStore(rag_path)
    client = authenticated_client(
        tmp_path,
        Settings(_env_file=None, CAREERPILOT_RAG_DB_PATH=rag_path),
        rag_store=store,
    )
    owner = OWNER

    response = client.post(
        "/v1/me/documents",
        params={"title": "AI 产品复盘.txt", "category": "项目与作品集", "file_format": "TXT"},
        content="我负责了智能客服的需求拆解与评估指标设计。".encode(),
        headers={"content-type": "application/octet-stream"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "可检索"
    assert response.json()["retrieval_enabled"] is True
    hits = store.search(
        "智能客服",
        user_id=owner,
        origins=frozenset({KnowledgeOrigin.USER_PROVIDED}),
    )
    assert hits and hits[0].document_id == response.json()["id"]
    assert store.search(
        "智能客服",
        user_id="550e8400-e29b-41d4-a716-446655440001",
        origins=frozenset({KnowledgeOrigin.USER_PROVIDED}),
    ) == ()

    deleted = client.delete(
        f"/v1/me/documents/{response.json()['id']}",
    )
    assert deleted.status_code == 200
    assert store.search(
        "智能客服",
        user_id=owner,
        origins=frozenset({KnowledgeOrigin.USER_PROVIDED}),
    ) == ()


def test_preparation_endpoint_lists_indexed_materials_instead_of_an_empty_stub(tmp_path) -> None:
    rag_path = tmp_path / "rag.db"
    store = SqliteRagStore(rag_path)
    RagIndexer(store).ingest_document(
        SourceDocument(
            id="prep-1",
            title="AI 产品课程",
            source_uri="https://example.com/course",
            source_type="web_search",
            domain="preparation_material",
            text="一份面向产品岗位的 AI 实践课程。",
            metadata={"publisher": "Example University", "category": "产品设计"},
            fetched_at="2026-10-28T00:00:00+00:00",
            knowledge_origin=KnowledgeOrigin.SYSTEM_WEB,
        )
    )
    client = authenticated_client(
        tmp_path,
        Settings(_env_file=None, CAREERPILOT_RAG_DB_PATH=rag_path),
        rag_store=store,
    )

    response = client.get("/v1/knowledge/preparation")

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "id": "prep-1",
            "title": "AI 产品课程",
            "publisher": "Example University",
            "category": "产品设计",
            "format": "网页",
            "url": "https://example.com/course",
            "description": "一份面向产品岗位的 AI 实践课程。",
            "updated_at": "2026-10-28T00:00:00+00:00",
            "source_type": "web_search",
        }
    ]


def test_jobs_endpoint_projects_existing_job_documents_when_structured_table_is_empty(
    tmp_path,
) -> None:
    rag_path = tmp_path / "rag.db"
    store = SqliteRagStore(rag_path)
    RagIndexer(store).ingest_document(
        SourceDocument(
            id="legacy-job-1",
            title="京东 AI Agent 产品经理",
            source_uri="https://zhaopin.jd.com/job/1",
            source_type="web_job",
            domain="job_opportunity",
            text="# 京东 AI Agent 产品经理\n\n负责企业级 Agent 产品。",
            metadata={"organization": "京东", "location": "北京"},
            published_at="2026-10-20",
            fetched_at="2026-11-01T00:00:00+00:00",
            knowledge_origin=KnowledgeOrigin.SYSTEM_CURATED,
        )
    )
    client = authenticated_client(
        tmp_path, Settings(_env_file=None, CAREERPILOT_RAG_DB_PATH=rag_path), rag_store=store
    )

    response = client.get("/v1/knowledge/jobs")

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "id": "legacy-job-1",
            "company_type": "未知",
            "organization_type": "unknown",
            "company": "京东",
            "role": "AI Agent 产品经理",
            "role_family": "ai_product",
            "recruiting_type": "unknown",
            "locations": ["北京"],
            "location": "北京",
            "posted_at": "2026-10-20",
            "deadline": None,
            "deadline_status": "时间未知",
            "status": "unknown",
            "source": "官方招聘页",
            "source_level": "S",
            "source_url": "https://zhaopin.jd.com/job/1",
            "apply_url": "https://zhaopin.jd.com/job/1",
            "updated_at": "2026-11-01T00:00:00+00:00",
            "description": "负责企业级 Agent 产品。",
            "requirements": "",
        }
    ]


def test_jobs_refresh_processes_queued_collection_and_exposes_new_source(tmp_path) -> None:
    rag_path = tmp_path / "rag.db"
    rag = SqliteRagStore(rag_path)
    product = ProductStore(tmp_path / "product.db")
    product.record_direction_signal(
        OWNER,
        source_run_id="run-refresh",
        label="Agent 产品经理",
        explicitness="explicit",
        source_quote="我想申请 Agent 产品经理",
        reason="明确申请意图",
        confidence=0.96,
    )

    class Search:
        async def search(self, query: str, strategy: SearchStrategy) -> WebSearchResponse:
            return WebSearchResponse(
                answer="找到岗位",
                sources=(
                    WebSearchSource(
                        "https://careers.example.com/agent-pm",
                        "Agent 产品经理",
                        site_name="Example Careers",
                        snippet="需要打开原始招聘页核验。",
                    ),
                ),
                strategy=strategy,
            )

    processor = KnowledgeCollectionProcessor(product, rag, Search())
    client = authenticated_client(
        tmp_path,
        Settings(_env_file=None, CAREERPILOT_RAG_DB_PATH=rag_path),
        rag_store=rag,
        product_store=product,
        knowledge_collection_processor=processor,
    )

    refreshed = client.post("/v1/knowledge/jobs/refresh")

    assert refreshed.status_code == 200
    assert refreshed.json()["processed"] == 1
    assert refreshed.json()["saved"] == 1
    jobs = client.get("/v1/knowledge/jobs").json()
    assert [source["url"] for source in jobs["collected_sources"]] == [
        "https://careers.example.com/agent-pm"
    ]


def test_interview_and_learning_refresh_process_their_queued_collection_jobs(tmp_path) -> None:
    rag_path = tmp_path / "rag.db"
    rag = SqliteRagStore(rag_path)
    product = ProductStore(tmp_path / "product.db")
    product.record_direction_signal(
        OWNER,
        source_run_id="run-preparation",
        label="Agent 产品经理",
        explicitness="explicit",
        source_quote="我想申请 Agent 产品经理",
        reason="明确申请意图",
        confidence=0.96,
    )
    direction = product.list_directions(OWNER)[0]
    product.start_direction_journey(OWNER, str(direction["id"]))

    class Search:
        async def search(self, query: str, strategy: SearchStrategy) -> WebSearchResponse:
            kind = "interview" if "面试" in query else "learning"
            return WebSearchResponse(
                answer="找到资料",
                sources=(
                    WebSearchSource(
                        f"https://example.com/{kind}",
                        "Agent 面试经验" if kind == "interview" else "Agent 学习指南",
                        site_name="Example",
                        snippet="保留来源的材料。",
                    ),
                ),
                strategy=strategy,
            )

    client = authenticated_client(
        tmp_path,
        Settings(_env_file=None, CAREERPILOT_RAG_DB_PATH=rag_path),
        rag_store=rag,
        product_store=product,
        knowledge_collection_processor=KnowledgeCollectionProcessor(product, rag, Search()),
    )

    interview = client.post("/v1/knowledge/interview-archive/refresh")
    learning = client.post("/v1/knowledge/learning/refresh")

    assert interview.status_code == 200
    assert interview.json()["saved"] == 1
    assert learning.status_code == 200
    assert learning.json()["saved"] == 1
    interview_items = client.get("/v1/knowledge/interview-archive").json()["items"]
    assert [item["url"] for item in interview_items] == ["https://example.com/interview"]
    assert [item["url"] for item in client.get("/v1/knowledge/learning").json()["items"]] == [
        "https://example.com/learning"
    ]


def test_interview_archive_and_learning_endpoints_keep_domains_separate(tmp_path) -> None:
    rag_path = tmp_path / "rag.db"
    store = SqliteRagStore(rag_path)
    indexer = RagIndexer(store)
    indexer.ingest_document(SourceDocument(
        id="interview-1", title="产品经理一面面经", source_uri="https://example.com/interview",
        source_type="experience_report", domain="interview_experience",
        text="候选人回忆的一面问题。",
        metadata={
            "publisher": "候选人经验",
            "year": "2025",
            "round": "一面",
            "trust": "experience",
        },
        fetched_at="2026-11-04T00:00:00+00:00", knowledge_origin=KnowledgeOrigin.SYSTEM_WEB,
    ))
    indexer.ingest_document(SourceDocument(
        id="learning-1", title="产品指标学习指南", source_uri="https://example.com/learning",
        source_type="official_guide", domain="learning_resource",
        text="官方发布的产品指标学习材料。",
        metadata={"publisher": "Example Lab", "category": "产品设计"},
        fetched_at="2026-11-04T00:00:00+00:00", knowledge_origin=KnowledgeOrigin.SYSTEM_WEB,
    ))
    client = authenticated_client(
        tmp_path, Settings(_env_file=None, CAREERPILOT_RAG_DB_PATH=rag_path), rag_store=store,
    )

    interviews = client.get("/v1/knowledge/interview-archive").json()["items"]
    learning = client.get("/v1/knowledge/learning").json()["items"]

    assert [item["id"] for item in interviews] == ["interview-1"]
    assert interviews[0]["trust"] == "experience"
    assert [item["id"] for item in learning] == ["learning-1"]
