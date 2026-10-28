from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.config import Settings
from careerpilot.rag.indexer import RagIndexer
from careerpilot.rag.models import KnowledgeOrigin, SourceDocument
from careerpilot.rag.store import SqliteRagStore
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
