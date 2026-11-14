from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.product_store import ProductStore
from tests.api.auth_helpers import build_auth_service, issue_session


def test_user_can_dismiss_only_their_own_open_loop(tmp_path) -> None:
    products = ProductStore(tmp_path / "product.db")
    episode = products.record_episode_event(
        "owner-1",
        event_kind="unresolved_question",
        source_turn_ids=("turn-1",),
        title="开发方向还没有细化",
        summary="还缺少真实任务体验。",
        open_loop={
            "kind": "evidence_gap",
            "initiator": "shared",
            "user_need": "完成一次模拟任务",
            "agent_need": "提供任务说明",
            "trigger_condition": "再次谈到开发",
        },
    )
    assert episode is not None
    loop = products.list_open_loops("owner-1")[0]
    auth = build_auth_service(tmp_path / "auth.db")
    first = TestClient(create_app(product_store=products, auth_service=auth))
    second = TestClient(create_app(product_store=products, auth_service=auth))
    first.cookies.update(issue_session(auth, owner_id="owner-1"))
    second.cookies.update(issue_session(auth, owner_id="owner-2"))
    try:
        forbidden = second.patch(
            f"/v1/me/open-loops/{loop['id']}", json={"status": "dismissed"}
        )
        updated = first.patch(
            f"/v1/me/open-loops/{loop['id']}", json={"status": "dismissed"}
        )

        assert forbidden.status_code == 404
        assert updated.status_code == 200
        assert updated.json()["status"] == "dismissed"
        assert products.list_open_loops("owner-1")[0]["status"] == "dismissed"
    finally:
        products.close()
