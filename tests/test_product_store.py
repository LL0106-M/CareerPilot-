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
            "directions": [],
            "direction_signals": [],
            "journeys": [],
            "collection_jobs": [],
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


def test_confirmed_direction_queues_jobs_but_waits_for_user_to_start_journey(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        store.record_direction_signal(
            "owner-1",
            source_run_id="run-1",
            label="新能源产品经理",
            explicitness="explicit",
            source_quote="我想申请新能源产品经理",
            reason="用户明确表达申请意图",
            confidence=0.95,
        )

        dashboard = store.dashboard("owner-1")

        assert dashboard["journeys"] == []
        assert dashboard["journey"] == []
        assert [job["purpose"] for job in dashboard["collection_jobs"]] == [
            "job_opportunity"
        ]
        assert dashboard["collection_jobs"][0]["query"] == "新能源产品经理"
        assert dashboard["collection_jobs"][0]["status"] == "queued"
    finally:
        store.close()


def test_collection_jobs_can_be_claimed_and_completed_without_crossing_owners(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        for owner in ("owner-1", "owner-2"):
            store.record_direction_signal(
                owner,
                source_run_id=f"run-{owner}",
                label="AI 产品经理",
                explicitness="explicit",
                source_quote="我想申请 AI 产品经理",
                reason="用户明确表达申请意图",
                confidence=0.95,
            )

        claimed = store.claim_collection_jobs("owner-1", purpose="job_opportunity")

        assert len(claimed) == 1
        assert claimed[0]["status"] == "collecting"
        assert claimed[0]["attempts"] == 1
        assert store.claim_collection_jobs("owner-1", purpose="job_opportunity") == []
        assert store.list_collection_jobs("owner-2")[0]["status"] == "queued"

        store.finish_collection_job(
            "owner-1", str(claimed[0]["id"]), status="completed", result_count=3
        )
        completed = store.list_collection_jobs("owner-1")[0]
        assert completed["status"] == "completed"
        assert completed["result_count"] == 3
        assert completed["last_error"] is None
    finally:
        store.close()


def test_start_direction_journey_is_owner_scoped_idempotent_and_enqueues_preparation(
    tmp_path,
) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        store.record_direction_signal(
            "owner-1",
            source_run_id="run-1",
            label="新能源产品经理",
            explicitness="explicit",
            source_quote="我想申请新能源产品经理",
            reason="用户明确表达申请意图",
            confidence=0.95,
        )
        direction = store.list_directions("owner-1")[0]

        assert store.start_direction_journey("owner-2", str(direction["id"])) is None
        started = store.start_direction_journey("owner-1", str(direction["id"]))
        repeated = store.start_direction_journey("owner-1", str(direction["id"]))

        assert started is not None
        assert repeated == started
        assert started["journey"]["title"] == "新能源产品经理"
        assert started["journey"]["direction_id"] == direction["id"]
        assert [task["step_kind"] for task in started["tasks"]] == [
            "role_profile",
            "interview_archive",
            "learning_resource",
        ]
        assert [job["purpose"] for job in started["collection_jobs"]] == [
            "job_opportunity",
            "interview_archive",
            "learning_resource",
        ]
        assert len(store.dashboard("owner-1")["journeys"]) == 1
        assert len(store.dashboard("owner-1")["journey"]) == 3
        assert store.dashboard("owner-2")["journeys"] == []
    finally:
        store.close()
