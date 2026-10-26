from pathlib import Path

import pytest

from careerpilot.agent.orchestration import AgentStage
from careerpilot.harness.events import HarnessEvent, HarnessEventType, RunPhase
from careerpilot.harness.run_store import SqliteAgentRunStore


async def _create(store: SqliteAgentRunStore, run_id: str = "run-1") -> None:
    await store.create(
        run_id=run_id,
        owner_id="owner-1",
        conversation_id="conversation-1",
        session_id="session-1",
        objective="完成任务",
    )


@pytest.mark.asyncio
async def test_run_events_and_checkpoint_survive_store_reopen(tmp_path: Path) -> None:
    path = tmp_path / "runs.db"
    store = SqliteAgentRunStore(path)
    await _create(store)
    await store.transition_stage("run-1", AgentStage.PLAN, data={"steps": ["search"]})
    await store.append_harness_event(
        HarnessEvent(
            type=HarnessEventType.MODEL_STARTED,
            run_id="run-1",
            session_id="session-1",
            sequence=1,
            phase=RunPhase.MODEL,
            step=1,
        )
    )
    store.close()

    reopened = SqliteAgentRunStore(path)
    try:
        run = await reopened.get("owner-1", "run-1")
        events = await reopened.list_events("owner-1", "run-1")
        checkpoint = await reopened.get_checkpoint("owner-1", "run-1")

        assert run is not None
        assert run.stage is AgentStage.PLAN
        assert run.runtime_phase == "model"
        assert [item.event_type for item in events or ()] == [
            "agent.plan",
            "model.started",
        ]
        assert checkpoint is not None
        assert checkpoint.runtime_phase == "model"
        assert checkpoint.step == 1
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_run_store_is_owner_scoped_and_cancellation_is_durable(tmp_path: Path) -> None:
    store = SqliteAgentRunStore(tmp_path / "runs.db")
    try:
        await _create(store)

        assert await store.get("owner-2", "run-1") is None
        assert await store.list_events("owner-2", "run-1") is None
        assert await store.request_cancel("owner-2", "run-1") is False
        assert await store.request_cancel("owner-1", "run-1") is True
        assert await store.cancellation_requested("run-1") is True
    finally:
        store.close()
