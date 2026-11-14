from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.product_store import ProductStore
from tests.api.auth_helpers import build_auth_service, issue_session


def test_relationship_profile_can_be_partially_configured_edited_and_reset(tmp_path) -> None:
    products = ProductStore(tmp_path / "product.db")
    auth = build_auth_service(tmp_path / "auth.db")
    client = TestClient(create_app(product_store=products, auth_service=auth))
    client.cookies.update(issue_session(auth, owner_id="owner-1"))
    try:
        initial = client.get("/v1/me/relationship-profile")
        selected = client.put(
            "/v1/me/relationship-profile/challenge", json={"value": "direct"}
        )
        edited = client.put(
            "/v1/me/relationship-profile/challenge", json={"value": "gentle"}
        )
        reset = client.delete("/v1/me/relationship-profile")

        assert initial.status_code == 200
        assert initial.json()["dimensions"] == []
        assert selected.json()["status"] == "confirmed"
        assert edited.json()["value"] == "gentle"
        assert reset.json() == {"status": "reset"}
        assert client.get("/v1/me/relationship-profile").json()["dimensions"] == []
    finally:
        products.close()


def test_relationship_profile_rejects_personality_labels(tmp_path) -> None:
    products = ProductStore(tmp_path / "product.db")
    auth = build_auth_service(tmp_path / "auth.db")
    client = TestClient(create_app(product_store=products, auth_service=auth))
    client.cookies.update(issue_session(auth, owner_id="owner-1"))
    try:
        response = client.put(
            "/v1/me/relationship-profile/mbti", json={"value": "INTJ"}
        )

        assert response.status_code == 422
    finally:
        products.close()
