from careerpilot.product_store import ProductStore


def test_new_owner_starts_with_empty_product_state(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        dashboard = store.dashboard("owner-1")

        assert dashboard == {
            "hypotheses": [],
            "journey": [],
            "memories": [],
            "dreaming": [],
        }
        assert store.decide_hypothesis("owner-1", "hyp-001", "confirm") is False
        assert store.create_verification_task("owner-1", "hyp-001") is None
        assert store.update_task("owner-1", "task-001", "已完成", None) is False
    finally:
        store.close()
