from careerpilot.product_store import ProductStore


def test_exploration_graph_keeps_flexible_nodes_edges_and_evidence_owner_scoped(
    tmp_path,
) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        thread = store.create_exploration_thread(
            "owner-1",
            seed_text="我可能想走开发",
            working_question="我喜欢的是哪一种开发工作？",
        )
        family = store.upsert_career_node(
            "owner-1",
            thread_id=str(thread["id"]),
            node_type="role_family",
            raw_label="开发",
            canonical_label="软件研发",
        )
        role = store.upsert_career_node(
            "owner-1",
            thread_id=str(thread["id"]),
            node_type="role",
            raw_label="AI 应用开发",
        )
        context = store.upsert_career_node(
            "owner-1",
            thread_id=str(thread["id"]),
            node_type="organization_context",
            raw_label="国央企",
        )
        store.connect_career_nodes(
            "owner-1",
            thread_id=str(thread["id"]),
            from_node_id=str(family["id"]),
            to_node_id=str(role["id"]),
            relation_type="specializes_to",
        )
        store.connect_career_nodes(
            "owner-1",
            thread_id=str(thread["id"]),
            from_node_id=str(role["id"]),
            to_node_id=str(context["id"]),
            relation_type="contextualized_as",
        )
        for kind, excerpt in (
            ("support", "做出小工具时会持续投入"),
            ("counter", "担心基础能力不足"),
            ("unknown", "还没体验过真实开发工作"),
        ):
            store.add_career_evidence(
                "owner-1",
                thread_id=str(thread["id"]),
                node_id=str(role["id"]),
                kind=kind,
                source_type="user_turn",
                source_reference=f"turn-{kind}",
                excerpt=excerpt,
                confidence=0.9,
                confirmation_status="confirmed",
            )

        view = store.list_exploration_views("owner-1")[0]

        assert view["thread"]["working_question"] == "我喜欢的是哪一种开发工作？"
        assert {item["node_type"] for item in view["nodes"]} == {
            "role_family", "role", "organization_context"
        }
        assert {item["relation_type"] for item in view["edges"]} == {
            "specializes_to", "contextualized_as"
        }
        assert [item["excerpt"] for item in view["supporting_evidence"]] == [
            "做出小工具时会持续投入"
        ]
        assert [item["excerpt"] for item in view["counter_evidence"]] == [
            "担心基础能力不足"
        ]
        assert [item["excerpt"] for item in view["unknowns"]] == [
            "还没体验过真实开发工作"
        ]
        assert store.list_exploration_views("owner-2") == []
    finally:
        store.close()


def test_compass_batch_projects_once_into_exploration_graph(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        arguments = dict(
            run_id="run-1",
            conversation_id="conversation-1",
            label="开发",
            explicitness="explicit",
            source_quote="我想沿着开发继续看，尤其是央企里的 AI 应用开发",
            reason="用户明确提出一条可继续展开的探索线",
            confidence=0.96,
            company="某央企",
            business="信息化建设",
            role="AI 应用开发",
            constraints=("担心技术基础不足",),
        )

        store.commit_compass_update("owner-1", **arguments)
        store.commit_compass_update("owner-1", **arguments)
        views = store.list_exploration_views("owner-1")

        assert len(views) == 1
        view = views[0]
        assert view["thread"]["seed_text"] == "开发"
        assert {item["raw_label"] for item in view["nodes"]} >= {
            "开发", "AI 应用开发", "某央企", "信息化建设"
        }
        assert len([
            item for item in view["supporting_evidence"]
            if item["source_reference"] == "turn:run-1"
        ]) == 1
        assert any("技术基础不足" in item["excerpt"] for item in view["unknowns"])
    finally:
        store.close()
