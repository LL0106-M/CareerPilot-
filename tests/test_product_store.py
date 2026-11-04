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


def test_journey_event_keeps_calendar_fields_owner_scoped(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        event = store.create_journey_event(
            "owner-1",
            title="腾讯产品二面",
            start_at="2026-10-30T15:00:00+08:00",
            end_at="2026-10-30T16:00:00+08:00",
            reminder_minutes=30,
            meeting_url="https://meeting.tencent.com/dm/abc",
            notes="准备三个项目案例",
            created_via="manual",
        )

        assert event["due"] == "2026-10-30"
        assert event["start_at"] == "2026-10-30T15:00:00+08:00"
        assert event["reminder_minutes"] == 30
        assert event["meeting_url"] == "https://meeting.tencent.com/dm/abc"
        assert event["created_via"] == "manual"
        assert store.dashboard("owner-1")["journey"] == [event]
        assert store.dashboard("owner-2")["journey"] == []
    finally:
        store.close()
