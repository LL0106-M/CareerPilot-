import pytest

from careerpilot.product_store import ProductStore


@pytest.mark.parametrize(
    "event_kind",
    [
        "new_exploration",
        "user_correction",
        "experiment_result",
        "direction_shift",
        "unresolved_question",
    ],
)
def test_only_meaningful_events_create_source_backed_episode(tmp_path, event_kind) -> None:
    store = ProductStore(tmp_path / f"{event_kind}.db")
    try:
        episode = store.record_episode_event(
            "owner-1",
            event_kind=event_kind,
            source_turn_ids=(f"turn-{event_kind}",),
            title="一次值得记住的变化",
            summary="用户对探索方向形成了新的理解。",
            callback_cue="再次谈到这个方向时可以提起。",
        )

        assert episode is not None
        assert episode["event_kind"] == event_kind
        assert episode["source_turn_ids"] == [f"turn-{event_kind}"]
        assert episode["status"] == "active"
    finally:
        store.close()


def test_ordinary_turn_does_not_create_episode(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        result = store.record_episode_event(
            "owner-1",
            event_kind="ordinary",
            source_turn_ids=("turn-1",),
            title="普通寒暄",
            summary="用户说了你好。",
        )

        assert result is None
        assert store.list_episodes("owner-1") == []
    finally:
        store.close()


def test_episode_hook_and_real_agent_commitment_are_owner_scoped_and_idempotent(
    tmp_path,
) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        first = store.record_episode_event(
            "owner-1",
            event_kind="unresolved_question",
            source_turn_ids=("turn-1",),
            title="开发方向还没有细化",
            summary="用户还不知道自己更喜欢哪一类开发工作。",
            callback_cue="用户再次谈到开发时继续细化。",
            open_loop={
                "kind": "map_gap",
                "initiator": "shared",
                "user_need": "描述一次投入的开发经历",
                "agent_need": "整理可低成本体验的开发任务",
                "trigger_condition": "再次谈到开发",
            },
        )
        repeated = store.record_episode_event(
            "owner-1",
            event_kind="unresolved_question",
            source_turn_ids=("turn-1",),
            title="开发方向还没有细化",
            summary="用户还不知道自己更喜欢哪一类开发工作。",
            callback_cue="用户再次谈到开发时继续细化。",
        )
        hook = store.list_open_loops("owner-1")[0]
        commitment = store.create_agent_commitment(
            "owner-1",
            open_loop_id=str(hook["id"]),
            description="整理可低成本体验的开发任务",
            executor_kind="knowledge_collection",
        )

        assert repeated == first
        assert len(store.list_episodes("owner-1")) == 1
        assert hook["episode_id"] == first["id"]
        assert commitment["status"] == "queued"
        assert store.list_open_loops("owner-2") == []
        assert store.list_agent_commitments("owner-2") == []
    finally:
        store.close()
