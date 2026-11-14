from careerpilot.product_store import ProductStore


def _thread_and_node(store: ProductStore) -> tuple[str, str]:
    thread = store.create_exploration_thread(
        "u1", seed_text="开发", working_question="哪类开发工作适合我？"
    )
    node = store.upsert_career_node(
        "u1", thread_id=thread["id"], node_type="role_family", raw_label="开发"
    )
    return str(thread["id"]), str(node["id"])


def test_consolidation_archives_duplicate_episode_and_merges_sources(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        first = store.record_episode_event(
            "u1",
            event_kind="unresolved_question",
            source_turn_ids=("turn-1",),
            title="开发方向还没有细化",
            summary="还需要体验不同类型的开发任务。",
        )
        second = store.record_episode_event(
            "u1",
            event_kind="unresolved_question",
            source_turn_ids=("turn-2",),
            title="  开发方向还没有细化  ",
            summary="还需要体验不同类型的开发任务。",
        )

        report = store.maintain_memory("u1")
        episodes = store.list_episodes("u1")

        assert first is not None and second is not None
        assert report["episodes_archived"] == 1
        active = [item for item in episodes if item["status"] == "active"]
        archived = [item for item in episodes if item["status"] == "archived"]
        assert len(active) == 1
        assert len(archived) == 1
        assert set(active[0]["source_turn_ids"]) == {"turn-1", "turn-2"}
    finally:
        store.close()


def test_source_invalidation_archives_derived_items_without_erasing_conflicts(
    tmp_path,
) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        thread_id, node_id = _thread_and_node(store)
        store.add_career_evidence(
            "u1",
            thread_id=thread_id,
            node_id=node_id,
            kind="support",
            source_type="user_turn",
            source_reference="turn:turn-deleted",
            excerpt="做项目时很投入",
            confidence=1.0,
            confirmation_status="confirmed",
        )
        store.add_career_evidence(
            "u1",
            thread_id=thread_id,
            node_id=node_id,
            kind="support",
            source_type="experiment",
            source_reference="experiment:1",
            excerpt="完成模拟任务后仍然感兴趣",
            confidence=0.8,
            confirmation_status="confirmed",
        )
        store.add_career_evidence(
            "u1",
            thread_id=thread_id,
            node_id=node_id,
            kind="counter",
            source_type="experiment",
            source_reference="experiment:2",
            excerpt="不喜欢长时间排查环境问题",
            confidence=0.9,
            confirmation_status="confirmed",
        )
        store.record_episode_event(
            "u1",
            event_kind="direction_shift",
            source_turn_ids=("turn-deleted", "turn-kept"),
            title="对开发方向的理解发生变化",
            summary="从泛开发转向具体工作任务。",
        )

        report = store.invalidate_memory_source("u1", "turn-deleted")
        view = store.list_exploration_views("u1")[0]
        episode = store.list_episodes("u1")[0]

        assert report == {"evidence_archived": 1, "episodes_archived": 0, "episodes_updated": 1}
        assert len(view["supporting_evidence"]) == 1
        assert len(view["counter_evidence"]) == 1
        assert episode["source_turn_ids"] == ["turn-kept"]
        assert episode["status"] == "active"
    finally:
        store.close()

