from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.journey.future_letter import FutureLetterService, FuturePath
from careerpilot.product_store import ProductStore
from tests.api.auth_helpers import build_auth_service, issue_session

OWNER_A = "550e8400-e29b-41d4-a716-446655440000"
OWNER_B = "550e8400-e29b-41d4-a716-446655440001"


class FixedGenerator:
    async def generate(self, *, journey, tasks, message):
        del journey, tasks, message
        return (
            FuturePath(
                "continue", "沿着这条路", "继续走深", "主线逐渐清晰", (),
                "机会成本", "还想继续吗？",
            ),
            FuturePath(
                "adjacent", "换一条相邻的路", "相邻转向", "能力可以迁移", (),
                "重新证明", "什么能带过去？",
            ),
            FuturePath(
                "unexpected", "意外的第三条路", "意外入口", "作品带来连接", (),
                "更不确定", "先公开什么？",
            ),
        )


def seed(store: ProductStore) -> str:
    store.record_direction_signal(
        OWNER_A,
        source_run_id="run-api-future",
        label="AI 产品经理",
        explicitness="explicit",
        source_quote="我确定这个方向",
        reason="明确方向",
        confidence=0.99,
    )
    direction = store.list_directions(OWNER_A)[0]
    payload = store.start_direction_journey(OWNER_A, str(direction["id"]))
    return str(payload["journey"]["id"])


def test_future_letter_endpoints_are_owner_scoped_and_confirm_only_a_question(tmp_path) -> None:
    product = ProductStore(tmp_path / "product.db")
    journey_id = seed(product)
    service = FutureLetterService(product, FixedGenerator())
    auth = build_auth_service(tmp_path / "auth.db")
    client = TestClient(
        create_app(
            product_store=product,
            auth_service=auth,
            future_letter_service=service,
        )
    )
    try:
        denied = client.post(
            f"/v1/me/journeys/{journey_id}/future-letter",
            json={"message": "两年后的我会怎样？"},
            cookies=issue_session(auth, owner_id=OWNER_B),
        )
        assert denied.status_code == 404

        client.cookies.update(issue_session(auth, owner_id=OWNER_A))
        generated = client.post(
            f"/v1/me/journeys/{journey_id}/future-letter",
            json={"message": "两年后的我会怎样？"},
        )
        assert generated.status_code == 201
        assert [item["kind"] for item in generated.json()["paths"]] == [
            "continue", "adjacent", "unexpected",
        ]

        confirmed = client.post(
            f"/v1/me/journeys/{journey_id}/future-letter/takeaway",
            json={
                "letter_id": generated.json()["id"],
                "path_kind": "adjacent",
                "question": "什么能力可以带过去？",
            },
        )
        assert confirmed.status_code == 201
        assert confirmed.json()["question"] == "什么能力可以带过去？"
        assert len(product.dashboard(OWNER_A)["journey"]) == 3
    finally:
        product.close()
