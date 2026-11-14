import pytest

from careerpilot.harness.context import CareerContextCompiler, ContextRequest
from careerpilot.memory.base import DisabledMemoryStore
from careerpilot.product_store import ProductStore
from careerpilot.support.policy import SupportMode, SupportPolicy


def _seed_episode(store: ProductStore) -> None:
    thread = store.create_exploration_thread(
        "u1",
        seed_text="开发",
        working_question="我喜欢的是哪一种开发工作？",
    )
    store.record_episode_event(
        "u1",
        event_kind="unresolved_question",
        source_turn_ids=("turn-source-1",),
        thread_id=str(thread["id"]),
        title="开发方向还没有细化",
        summary="用户还没有体验过不同类型的开发任务。",
        callback_cue="再次谈到开发时可以继续细化。",
        open_loop={
            "kind": "evidence_gap",
            "initiator": "shared",
            "user_need": "回忆一次投入的开发经历",
            "agent_need": "提供一个低成本模拟任务",
            "trigger_condition": "再次谈到开发",
        },
    )


@pytest.mark.asyncio
async def test_context_recalls_one_source_backed_episode_and_hook(tmp_path) -> None:
    products = ProductStore(tmp_path / "product.db")
    _seed_episode(products)
    compiler = CareerContextCompiler(
        DisabledMemoryStore(), SupportPolicy(), product_store=products
    )
    try:
        context = await compiler.compile(
            ContextRequest(
                user_id="u1",
                conversation_id="c1",
                message="我还想继续聊聊开发",
                page_context={"page": "compass", "path": "/compass"},
            )
        )

        assert "<shared_episode_context>" in context.system_prompt
        assert "开发方向还没有细化" in context.system_prompt
        assert "turn-source-1" in context.system_prompt
        assert "回忆一次投入的开发经历" in context.system_prompt
        assert "不是用户事实" in context.system_prompt
    finally:
        products.close()


@pytest.mark.asyncio
async def test_listen_mode_does_not_force_episode_callback(tmp_path) -> None:
    products = ProductStore(tmp_path / "product.db")
    _seed_episode(products)
    compiler = CareerContextCompiler(
        DisabledMemoryStore(), SupportPolicy(), product_store=products
    )
    try:
        context = await compiler.compile(
            ContextRequest(
                user_id="u1",
                conversation_id="c1",
                message="我今天被拒了，现在只想说说",
                requested_mode=SupportMode.LISTEN,
            )
        )

        assert "开发方向还没有细化" not in context.system_prompt
        assert "当前没有适合主动提起的共同经历" in context.system_prompt
    finally:
        products.close()


@pytest.mark.asyncio
async def test_prompt_uses_only_confirmed_relationship_style_with_distress_override(
    tmp_path,
) -> None:
    products = ProductStore(tmp_path / "product.db")
    products.record_relationship_signal(
        "u1", dimension="challenge", value="direct", source="settings", explicit=True
    )
    products.record_relationship_signal(
        "u1", dimension="detail", value="detailed", source="settings", explicit=True
    )
    products.record_relationship_signal(
        "u1", dimension="pace", value="action_first", source="behavior", explicit=False
    )
    compiler = CareerContextCompiler(
        DisabledMemoryStore(), SupportPolicy(), product_store=products
    )
    try:
        normal = await compiler.compile(
            ContextRequest(user_id="u1", conversation_id="c1", message="帮我分析下一步")
        )
        distressed = await compiler.compile(
            ContextRequest(
                user_id="u1",
                conversation_id="c1",
                message="我被拒了，很难受，现在只想说说",
            )
        )

        assert "challenge=direct" in normal.system_prompt
        assert "detail=detailed" in normal.system_prompt
        assert "pace=action_first" not in normal.system_prompt
        assert "临时降低 challenge 为 gentle" in distressed.system_prompt
        assert "临时降低 initiative 为 wait" in distressed.system_prompt
        assert "安全边界和事实标准不随风格变化" in normal.system_prompt
    finally:
        products.close()
