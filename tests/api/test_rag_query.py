from pathlib import Path

from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.config import Settings
from careerpilot.rag.chunking import chunk_document
from careerpilot.rag.models import SourceDocument
from careerpilot.rag.store import SqliteRagStore
from tests.api.auth_helpers import build_auth_service, issue_session


def test_standalone_rag_query_routes_and_returns_agent_context(tmp_path: Path) -> None:
    store = SqliteRagStore(tmp_path / "rag.db")
    document = SourceDocument(
        "prep-1",
        "需求分析方法",
        "file:///prep.md",
        "developer_upload",
        "preparation_material",
        "需求分析需要先识别用户问题，再验证需求优先级。",
    )
    store.upsert(document, chunk_document(document))
    auth = build_auth_service(tmp_path / "auth.db")
    app = create_app(Settings(_env_file=None), rag_store=store, auth_service=auth)

    with TestClient(app) as client:
        response = client.post(
            "/v1/rag/query",
            json={"query": "需求分析是什么"},
            cookies=issue_session(auth, owner_id="550e8400-e29b-41d4-a716-446655440000"),
        )
        health = client.get("/v1/rag/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "available"
    assert payload["scopes"] == ["preparation"]
    assert payload["route"]["external_reason"] == "default_preparation"
    assert payload["route"]["internal"] == ["preparation:sparse,dense,online"]
    assert payload["route"]["retrieval_mode"] == "local_first"
    assert payload["route"]["graph_mode"] == "none"
    assert payload["query_analysis"]["intent"] == "knowledge_lookup"
    assert payload["context_pack"]["evidence"][0]["citation_id"] == "S1"
    assert "[S1]" in payload["context_for_model"]
    assert health.status_code == 200
    assert health.json()["ready"] is False
    assert health.json()["dense_vectors"] == 0
