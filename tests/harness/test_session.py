from pathlib import Path

import pytest

from careerpilot.harness.contracts import HarnessMessage, ToolCall
from careerpilot.harness.session import SqliteSessionStore


@pytest.mark.asyncio
async def test_sqlite_session_store_round_trips_tool_messages(tmp_path: Path) -> None:
    store = SqliteSessionStore(tmp_path / "sessions.db")
    messages = (
        HarnessMessage(role="user", content="查资料"),
        HarnessMessage(
            role="assistant",
            tool_calls=(ToolCall("call-1", "search", {"query": "产品经理"}),),
        ),
        HarnessMessage(
            role="tool", content='{"status":"ok"}', tool_call_id="call-1", name="search"
        ),
    )

    await store.append("session-1", messages)

    assert await store.load("session-1") == messages
    store.close()
