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
            "compass_update_batches": [],
            "direction_branches": [],
            "career_profile": [],
            "direction_evidence": [],
            "direction_summaries": [],
            "journey_branches": [],
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


def test_compass_update_batch_creates_one_direction_and_target_branch(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        result = store.commit_compass_update(
            "owner-1",
            run_id="run-branch-1",
            conversation_id="thread-1",
            label="AI 产品经理",
            explicitness="explicit",
            source_quote="我想看腾讯混元的 AI 产品经理，最好在深圳",
            reason="用户明确给出目标",
            confidence=0.98,
            signal_kind="direction",
            company="腾讯",
            business="混元",
            role="AI 产品经理",
            location="深圳",
            constraints=(),
        )
        repeated = store.commit_compass_update(
            "owner-1",
            run_id="run-branch-1",
            conversation_id="thread-1",
            label="AI 产品经理",
            explicitness="explicit",
            source_quote="我想看腾讯混元的 AI 产品经理，最好在深圳",
            reason="用户明确给出目标",
            confidence=0.98,
            signal_kind="direction",
            company="腾讯",
            business="混元",
            role="AI 产品经理",
            location="深圳",
            constraints=(),
        )

        dashboard = store.dashboard("owner-1")
        assert repeated == result
        assert len(dashboard["directions"]) == 1
        assert dashboard["direction_branches"][0]["company"] == "腾讯"
        assert dashboard["direction_branches"][0]["business"] == "混元"
        assert dashboard["direction_branches"][0]["location"] == "深圳"
        assert [item["kind"] for item in result["items"]] == [
            "direction", "company", "business", "role", "location"
        ]
    finally:
        store.close()


def test_target_only_update_uses_conversation_bound_direction(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        store.commit_compass_update(
            "owner-1", run_id="run-direction", conversation_id="thread-1",
            label="AI 产品经理", explicitness="explicit",
            source_quote="我想试试 AI 产品经理", reason="明确方向", confidence=0.96,
            signal_kind="direction", company=None, business=None,
            role="AI 产品经理", location=None, constraints=(),
        )
        update = store.commit_compass_update(
            "owner-1", run_id="run-target", conversation_id="thread-1",
            label=None, explicitness="explicit", source_quote="我更想看腾讯混元",
            reason="明确目标公司和业务", confidence=0.94, signal_kind="target",
            company="腾讯", business="混元", role=None, location=None, constraints=(),
        )

        dashboard = store.dashboard("owner-1")
        assert len(dashboard["directions"]) == 1
        assert (
            dashboard["direction_branches"][0]["direction_id"]
            == dashboard["directions"][0]["id"]
        )
        assert update["direction_id"] == dashboard["directions"][0]["id"]
    finally:
        store.close()


def test_direction_journey_reuses_common_tasks_and_activates_target_branch(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        store.commit_compass_update(
            "owner-1", run_id="run-branch", conversation_id="thread-1",
            label="AI 产品经理", explicitness="explicit",
            source_quote="我想看腾讯混元的 AI 产品经理", reason="明确目标",
            confidence=0.98, signal_kind="direction", company="腾讯",
            business="混元", role="AI 产品经理", location=None, constraints=(),
        )
        direction = store.list_directions("owner-1")[0]
        branch = store.dashboard("owner-1")["direction_branches"][0]

        started = store.start_direction_journey("owner-1", str(direction["id"]))
        assert started is not None
        journey_branches = store.dashboard("owner-1")["journey_branches"]
        common = next(item for item in journey_branches if item["kind"] == "common")
        target = next(item for item in journey_branches if item["kind"] == "target")
        assert target["status"] == "draft"
        assert target["compass_branch_id"] == branch["id"]
        assert {task["journey_branch_id"] for task in started["tasks"]} == {common["id"]}

        activated = store.activate_journey_branch(
            "owner-1", str(started["journey"]["id"]), str(target["id"])
        )
        repeated = store.activate_journey_branch(
            "owner-1", str(started["journey"]["id"]), str(target["id"])
        )
        assert activated == repeated
        branch_tasks = [task for task in activated["tasks"] if task["scope"] == "branch_specific"]
        assert len(branch_tasks) == 2
        assert {task["journey_branch_id"] for task in branch_tasks} == {target["id"]}
        assert len([task for task in activated["tasks"] if task["scope"] == "common"]) == 3
        branch_jobs = [
            job
            for job in activated["collection_jobs"]
            if job.get("compass_branch_id") == branch["id"]
        ]
        assert {job["purpose"] for job in branch_jobs} == {
            "job_opportunity", "interview_archive", "learning_resource"
        }
        assert {
            job.get("journey_branch_id")
            for job in branch_jobs
            if job["purpose"] != "job_opportunity"
        } == {target["id"]}
    finally:
        store.close()


def test_new_explicit_target_adds_draft_to_existing_journey(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        store.commit_compass_update(
            "owner-1", run_id="direction", conversation_id="thread-1",
            label="AI 产品经理", explicitness="explicit",
            source_quote="我想试试 AI 产品经理", reason="明确方向", confidence=0.96,
        )
        direction = store.list_directions("owner-1")[0]
        started = store.start_direction_journey("owner-1", str(direction["id"]))
        assert started is not None

        store.commit_compass_update(
            "owner-1", run_id="target", conversation_id="thread-1",
            label=None, explicitness="explicit", source_quote="我更想看腾讯混元",
            reason="明确目标", confidence=0.95, signal_kind="target",
            company="腾讯", business="混元",
        )

        targets = [
            branch for branch in store.dashboard("owner-1")["journey_branches"]
            if branch["kind"] == "target"
        ]
        assert len(targets) == 1
        assert targets[0]["status"] == "draft"
        assert not [
            task for task in store.dashboard("owner-1")["journey"]
            if task["journey_branch_id"] == targets[0]["id"]
        ]
    finally:
        store.close()


def test_implicit_target_stays_candidate_without_collection_job(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        store.commit_compass_update(
            "owner-1", run_id="direction", conversation_id="thread-1",
            label="AI 产品经理", explicitness="explicit",
            source_quote="我想试试 AI 产品经理", reason="明确方向", confidence=0.96,
        )
        update = store.commit_compass_update(
            "owner-1", run_id="target", conversation_id="thread-1",
            label=None, explicitness="implicit", source_quote="最近总看到腾讯混元",
            reason="可能感兴趣", confidence=0.7, signal_kind="target",
            company="腾讯", business="混元",
        )

        dashboard = store.dashboard("owner-1")
        assert update["items"][0]["status"] == "pending"
        assert dashboard["direction_branches"][0]["status"] == "candidate"
        assert not [
            job for job in dashboard["collection_jobs"]
            if job.get("compass_branch_id") == update["branch_id"]
        ]
    finally:
        store.close()


def test_repeated_direction_reuses_identity_and_later_batch_protects_branch(tmp_path) -> None:
    store = ProductStore(tmp_path / "product.db")
    try:
        first = store.commit_compass_update(
            "owner-1", run_id="first", conversation_id="thread-1",
            label="AI 产品经理", explicitness="explicit",
            source_quote="我想看腾讯混元的 AI 产品经理", reason="明确目标",
            confidence=0.97, company="腾讯", business="混元", role="AI 产品经理",
        )
        second = store.commit_compass_update(
            "owner-1", run_id="second", conversation_id="thread-1",
            label="AI 产品经理", explicitness="explicit",
            source_quote="还是腾讯混元的 AI 产品经理", reason="再次确认",
            confidence=0.98, company="腾讯", business="混元", role="AI 产品经理",
        )
        assert second["direction_id"] == first["direction_id"]
        assert second["branch_id"] == first["branch_id"]

        store.undo_compass_update("owner-1", str(first["id"]))
        dashboard = store.dashboard("owner-1")
        assert len(dashboard["directions"]) == 1
        branch = next(
            item
            for item in dashboard["direction_branches"]
            if item["id"] == first["branch_id"]
        )
        assert branch["status"] == "active"
    finally:
        store.close()
