import pytest

from careerpilot.product_store import ProductStore


def test_explicit_relationship_choice_is_confirmed_with_provenance(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        item = store.record_relationship_signal(
            "owner-1",
            dimension="challenge",
            value="direct",
            source="onboarding",
            explicit=True,
        )

        assert item["status"] == "confirmed"
        assert item["source"] == "onboarding"
        assert item["confidence"] == 1.0
        assert store.get_relationship_profile("owner-2")["dimensions"] == []
    finally:
        store.close()


def test_behavior_signal_stays_candidate_until_repeated_three_times(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        first = store.record_relationship_signal(
            "owner-1",
            dimension="detail",
            value="concise",
            source="behavior",
            explicit=False,
        )
        second = store.record_relationship_signal(
            "owner-1",
            dimension="detail",
            value="concise",
            source="behavior",
            explicit=False,
        )
        third = store.record_relationship_signal(
            "owner-1",
            dimension="detail",
            value="concise",
            source="behavior",
            explicit=False,
        )

        assert first["status"] == "candidate"
        assert second["status"] == "candidate"
        assert third["status"] == "confirmed"
        assert third["signal_count"] == 3
    finally:
        store.close()


def test_relationship_profile_reset_does_not_change_career_evidence(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        thread = store.create_exploration_thread(
            "owner-1", seed_text="产品", working_question="我喜欢哪类产品工作？"
        )
        node = store.upsert_career_node(
            "owner-1",
            thread_id=str(thread["id"]),
            node_type="role_family",
            raw_label="产品",
        )
        store.add_career_evidence(
            "owner-1",
            thread_id=str(thread["id"]),
            node_id=str(node["id"]),
            kind="support",
            source_type="user_turn",
            source_reference="turn-1",
            excerpt="喜欢拆解用户问题",
            confidence=1.0,
            confirmation_status="confirmed",
        )
        store.record_relationship_signal(
            "owner-1",
            dimension="pace",
            value="listen_first",
            source="user_correction",
            explicit=True,
        )

        store.reset_relationship_profile("owner-1")

        assert store.get_relationship_profile("owner-1")["dimensions"] == []
        assert store.list_exploration_views("owner-1")[0]["supporting_evidence"][0][
            "excerpt"
        ] == "喜欢拆解用户问题"
    finally:
        store.close()


def test_relationship_profile_rejects_unknown_dimension(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        with pytest.raises(ValueError, match="unsupported relationship dimension"):
            store.record_relationship_signal(
                "owner-1",
                dimension="loyalty",
                value="high",
                source="behavior",
                explicit=False,
            )
    finally:
        store.close()
