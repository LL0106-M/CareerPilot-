from dataclasses import dataclass

import pytest

from careerpilot.harness.context_window import ContextWindowManager, _estimate_text_tokens
from careerpilot.harness.contracts import HarnessMessage, ToolCall
from careerpilot.harness.session import SqliteSessionStore


@dataclass
class RecordingSummarizer:
    calls: int = 0

    async def summarize(self, messages):
        self.calls += 1
        assert messages
        return "目标：完成求职准备；已决定：先修改简历；下一步：模拟面试"


@pytest.mark.asyncio
async def test_context_below_threshold_remains_verbatim() -> None:
    manager = ContextWindowManager(soft_token_limit=1000, keep_recent_turns=1)
    history = (
        HarnessMessage(role="user", content="你好"),
        HarnessMessage(role="assistant", content="你好"),
    )

    assert await manager.compile("s1", history) == history


@pytest.mark.asyncio
async def test_context_compacts_old_turns_and_keeps_recent_turn_verbatim() -> None:
    summarizer = RecordingSummarizer()
    manager = ContextWindowManager(
        summarizer=summarizer, soft_token_limit=20, keep_recent_turns=1
    )
    history = (
        HarnessMessage(role="user", content="第一轮：我准备产品经理岗位" * 8),
        HarnessMessage(role="assistant", content="先修改简历" * 8),
        HarnessMessage(role="user", content="第二轮：下一步是什么"),
        HarnessMessage(role="assistant", content="模拟面试"),
    )

    compiled = await manager.compile("s1", history)

    assert compiled[0].role == "assistant"
    assert compiled[0].content.startswith("[CONVERSATION_CONTINUATION_SUMMARY]")
    assert compiled[-2:] == history[-2:]
    assert summarizer.calls == 1


@pytest.mark.asyncio
async def test_recent_tool_call_and_result_are_kept_as_one_turn() -> None:
    manager = ContextWindowManager(
        summarizer=RecordingSummarizer(), soft_token_limit=10, keep_recent_turns=1
    )
    history = (
        HarnessMessage(role="user", content="旧内容" * 20),
        HarnessMessage(role="assistant", content="旧回复" * 20),
        HarnessMessage(role="user", content="查岗位"),
        HarnessMessage(
            role="assistant", tool_calls=(ToolCall("c1", "search", {"q": "岗位"}),)
        ),
        HarnessMessage(role="tool", content="结果", tool_call_id="c1", name="search"),
        HarnessMessage(role="assistant", content="找到一个岗位"),
    )

    compiled = await manager.compile("s1", history)

    assert [message.role for message in compiled[-4:]] == [
        "user",
        "assistant",
        "tool",
        "assistant",
    ]


@pytest.mark.asyncio
async def test_sqlite_compaction_is_reused_only_for_same_source(tmp_path) -> None:
    sessions = SqliteSessionStore(tmp_path / "sessions.db")
    summarizer = RecordingSummarizer()
    manager = ContextWindowManager(
        summarizer=summarizer,
        compaction_store=sessions,
        soft_token_limit=10,
        keep_recent_turns=1,
    )
    history = (
        HarnessMessage(role="user", content="旧内容" * 20),
        HarnessMessage(role="assistant", content="旧回复" * 20),
        HarnessMessage(role="user", content="最近"),
        HarnessMessage(role="assistant", content="回复"),
    )

    first = await manager.compile("s1", history)
    second = await manager.compile("s1", history)

    assert first == second
    assert summarizer.calls == 1
    changed = (HarnessMessage(role="user", content="变化" * 20), *history[1:])
    await manager.compile("s1", changed)
    assert summarizer.calls == 2


@pytest.mark.asyncio
async def test_compaction_failure_falls_back_to_recent_complete_turn() -> None:
    class FailingSummarizer:
        async def summarize(self, messages):
            raise RuntimeError("model unavailable")

    manager = ContextWindowManager(
        summarizer=FailingSummarizer(), soft_token_limit=10, keep_recent_turns=1
    )
    history = (
        HarnessMessage(role="user", content="旧内容" * 20),
        HarnessMessage(role="assistant", content="旧回复" * 20),
        HarnessMessage(role="user", content="最近"),
        HarnessMessage(role="assistant", content="回复"),
    )

    assert await manager.compile("s1", history) == history[-2:]


@pytest.mark.asyncio
async def test_pre_compaction_flush_receives_source_messages_not_summary() -> None:
    flushed = []

    async def flush(session_id, messages):
        flushed.append((session_id, messages))

    manager = ContextWindowManager(
        summarizer=RecordingSummarizer(),
        pre_compaction_flush=flush,
        soft_token_limit=10,
        keep_recent_turns=1,
    )
    history = (
        HarnessMessage(role="user", content="我有个产品想法" * 20),
        HarnessMessage(role="assistant", content="先保存为候选" * 20),
        HarnessMessage(role="user", content="继续"),
        HarnessMessage(role="assistant", content="好"),
    )

    await manager.compile("s1", history)

    assert flushed == [("s1", history[:2])]


def test_token_estimator_is_conservative_for_chinese() -> None:
    assert _estimate_text_tokens("职业方向探索") == 6
    assert _estimate_text_tokens("abcd") == 1
