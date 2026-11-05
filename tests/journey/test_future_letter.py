import pytest

from careerpilot.journey.future_letter import (
    FutureLetterService,
    FuturePath,
    FuturePathValidationError,
    validate_future_paths,
)
from careerpilot.product_store import ProductStore

OWNER = "owner-a"


class RecordingGenerator:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, *, journey, tasks, message):
        self.calls += 1
        assert journey["title"] == "AI 产品经理"
        assert message == "我想知道两年后的选择"
        return (
            FuturePath(
                "continue", "沿着这条路", "走深", "能力逐渐连成线",
                ("完成岗位拆解",), "选择变窄", "我愿意继续深挖吗？",
            ),
            FuturePath(
                "adjacent", "换一条相邻的路", "横向一步", "已有能力换了场景",
                ("联系从业者",), "需要重新建立可信度", "哪些能力可以带过去？",
            ),
            FuturePath(
                "unexpected", "意外的第三条路", "从作品出发",
                "一次公开输出带来新入口", ("完成岗位拆解",),
                "结果更不可控", "我愿意先公开什么？",
            ),
        )


def seed_journey(store: ProductStore) -> str:
    store.record_direction_signal(
        OWNER,
        source_run_id="run-future",
        label="AI 产品经理",
        explicitness="explicit",
        source_quote="我想走 AI 产品经理",
        reason="用户明确选择",
        confidence=0.96,
    )
    direction = store.list_directions(OWNER)[0]
    return str(store.start_direction_journey(OWNER, str(direction["id"]))["journey"]["id"])


def test_future_paths_require_each_of_the_three_distinct_kinds() -> None:
    duplicate = FuturePath("continue", "继续", "标题", "摘要", (), "张力", "问题？")
    with pytest.raises(FuturePathValidationError):
        validate_future_paths((duplicate, duplicate, duplicate))


@pytest.mark.asyncio
async def test_service_generates_once_and_only_persists_confirmed_takeaway(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    generator = RecordingGenerator()
    journey_id = seed_journey(store)
    service = FutureLetterService(store, generator)
    try:
        letter = await service.generate(OWNER, journey_id, "我想知道两年后的选择")

        assert generator.calls == 1
        assert [path.kind for path in letter.paths] == ["continue", "adjacent", "unexpected"]
        assert store.dashboard(OWNER)["memories"] == []
        before_tasks = list(store.dashboard(OWNER)["journey"])

        takeaway = service.confirm_takeaway(
            OWNER,
            journey_id,
            letter.id,
            "adjacent",
            "哪些能力可以带过去？",
        )

        assert takeaway["question"] == "哪些能力可以带过去？"
        assert store.dashboard(OWNER)["journey"] == before_tasks
        assert service.get(OWNER, journey_id).takeaway["path_kind"] == "adjacent"
        assert service.get("owner-b", journey_id) is None
    finally:
        store.close()
