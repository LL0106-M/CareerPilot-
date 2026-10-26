from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from careerpilot.harness.contracts import HarnessMessage


class ContextSummarizer(Protocol):
    async def summarize(self, messages: tuple[HarnessMessage, ...]) -> str: ...


class CompactionStore(Protocol):
    async def load_compaction(self, session_id: str) -> SessionCompaction | None: ...

    async def save_compaction(self, compaction: SessionCompaction) -> None: ...


@dataclass(frozen=True, slots=True)
class SessionCompaction:
    session_id: str
    covered_message_count: int
    source_hash: str
    summary: str
    schema_version: str
    model_metadata: str
    created_at: datetime


class DeterministicContextSummarizer:
    """Offline-safe continuation summary used until a model summarizer is configured."""

    async def summarize(self, messages: tuple[HarnessMessage, ...]) -> str:
        lines = []
        for message in messages[-40:]:
            content = " ".join(message.content.split())
            if content:
                lines.append(f"- {message.role}: {content[:500]}")
            elif message.tool_calls:
                names = ", ".join(call.name for call in message.tool_calls)
                lines.append(f"- assistant requested tools: {names}")
        return "已压缩的较早对话：\n" + "\n".join(lines)


class ContextWindowManager:
    def __init__(
        self,
        *,
        summarizer: ContextSummarizer | None = None,
        compaction_store: CompactionStore | None = None,
        pre_compaction_flush: Callable[
            [str, tuple[HarnessMessage, ...]], Awaitable[None]
        ]
        | None = None,
        soft_token_limit: int = 120_000,
        keep_recent_turns: int = 6,
        schema_version: str = "context-summary-v1",
        model_metadata: str = "deterministic",
    ) -> None:
        if soft_token_limit < 1 or keep_recent_turns < 1:
            raise ValueError("Context limits must be positive")
        self._summarizer = summarizer or DeterministicContextSummarizer()
        self._store = compaction_store
        self._pre_compaction_flush = pre_compaction_flush
        self._soft_token_limit = soft_token_limit
        self._keep_recent_turns = keep_recent_turns
        self._schema_version = schema_version
        self._model_metadata = model_metadata

    async def compile(
        self, session_id: str, history: tuple[HarnessMessage, ...]
    ) -> tuple[HarnessMessage, ...]:
        if self._estimate_tokens(history) <= self._soft_token_limit:
            return history
        groups = self._turn_groups(history)
        if len(groups) <= self._keep_recent_turns:
            return history
        older_groups = groups[: -self._keep_recent_turns]
        recent_groups = groups[-self._keep_recent_turns :]
        older = tuple(message for group in older_groups for message in group)
        recent = tuple(message for group in recent_groups for message in group)
        source_hash = self._source_hash(older)

        previous = await self._load(session_id)
        if (
            previous is not None
            and previous.source_hash == source_hash
            and previous.covered_message_count == len(older)
            and previous.schema_version == self._schema_version
        ):
            return (self._summary_message(previous.summary), *recent)

        try:
            if self._pre_compaction_flush is not None:
                try:
                    await self._pre_compaction_flush(session_id, older)
                except Exception:
                    pass
            prepared = self._clear_refetchable_tool_results(older)
            summary = (await self._summarizer.summarize(prepared)).strip()
            if not summary:
                raise ValueError("Compaction summary cannot be empty")
            compaction = SessionCompaction(
                session_id=session_id,
                covered_message_count=len(older),
                source_hash=source_hash,
                summary=summary,
                schema_version=self._schema_version,
                model_metadata=self._model_metadata,
                created_at=datetime.now(UTC),
            )
            await self._save(compaction)
            return (self._summary_message(summary), *recent)
        except Exception:
            if (
                previous is not None
                and previous.schema_version == self._schema_version
                and previous.source_hash == source_hash
                and previous.covered_message_count == len(older)
            ):
                return (self._summary_message(previous.summary), *recent)
            return recent

    async def _load(self, session_id: str) -> SessionCompaction | None:
        if self._store is None:
            return None
        return await self._store.load_compaction(session_id)

    async def _save(self, compaction: SessionCompaction) -> None:
        if self._store is not None:
            await self._store.save_compaction(compaction)

    @staticmethod
    def _turn_groups(
        messages: tuple[HarnessMessage, ...]
    ) -> tuple[tuple[HarnessMessage, ...], ...]:
        groups: list[list[HarnessMessage]] = []
        for message in messages:
            if message.role == "user" or not groups:
                groups.append([message])
            else:
                groups[-1].append(message)
        return tuple(tuple(group) for group in groups)

    @staticmethod
    def _clear_refetchable_tool_results(
        messages: tuple[HarnessMessage, ...]
    ) -> tuple[HarnessMessage, ...]:
        return tuple(
            HarnessMessage(
                role=message.role,
                content="[older tool result cleared; re-fetch if needed]",
                tool_call_id=message.tool_call_id,
                name=message.name,
            )
            if message.role == "tool" and len(message.content) > 500
            else message
            for message in messages
        )

    @staticmethod
    def _estimate_tokens(messages: tuple[HarnessMessage, ...]) -> int:
        tokens = 0
        for message in messages:
            tokens += _estimate_text_tokens(message.content)
            tokens += sum(
                _estimate_text_tokens(json.dumps(call.arguments, ensure_ascii=False))
                + _estimate_text_tokens(call.name)
                for call in message.tool_calls
            )
        return max(1, tokens)

    @staticmethod
    def _source_hash(messages: tuple[HarnessMessage, ...]) -> str:
        payload = [
            {
                "role": message.role,
                "content": message.content,
                "tool_calls": [
                    {"id": call.id, "name": call.name, "arguments": call.arguments}
                    for call in message.tool_calls
                ],
                "tool_call_id": message.tool_call_id,
                "name": message.name,
            }
            for message in messages
        ]
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _summary_message(summary: str) -> HarnessMessage:
        return HarnessMessage(
            role="assistant", content=f"[CONVERSATION_CONTINUATION_SUMMARY]\n{summary}"
        )


def _estimate_text_tokens(text: str) -> int:
    """Conservative fallback for mixed Chinese and Latin text.

    CJK characters are close to one token each for common chat tokenizers; remaining
    text uses the conventional four-characters-per-token approximation.
    """

    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    non_cjk = max(0, len(text) - cjk)
    return cjk + (non_cjk + 3) // 4
