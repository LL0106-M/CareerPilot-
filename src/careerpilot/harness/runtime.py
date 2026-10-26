import asyncio
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from careerpilot.harness.context_window import ContextWindowManager
from careerpilot.harness.contracts import (
    HarnessMessage,
    ModelGateway,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
)
from careerpilot.harness.events import HarnessEvent, HarnessEventType, RunPhase
from careerpilot.harness.run_store import SqliteAgentRunStore
from careerpilot.harness.session import InMemorySessionStore
from careerpilot.harness.tools import ToolPolicy, ToolRegistry


class MaxStepsExceeded(RuntimeError):
    pass


class RunCancellationRequested(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HarnessRunResult:
    reply: str
    steps: int
    tool_names: tuple[str, ...] = ()
    usage: dict[str, int] = field(default_factory=dict)
    run_id: str = ""
    citation_ids: tuple[str, ...] = ()
    citation_warnings: tuple[str, ...] = ()


_ALLOWED_TRANSITIONS: dict[RunPhase, frozenset[RunPhase]] = {
    RunPhase.CREATED: frozenset({RunPhase.RUNNING}),
    RunPhase.RUNNING: frozenset({RunPhase.MODEL, RunPhase.FAILED, RunPhase.CANCELLED}),
    RunPhase.MODEL: frozenset(
        {RunPhase.TOOLS, RunPhase.COMPLETED, RunPhase.FAILED, RunPhase.CANCELLED}
    ),
    RunPhase.TOOLS: frozenset({RunPhase.MODEL, RunPhase.FAILED, RunPhase.CANCELLED}),
    RunPhase.COMPLETED: frozenset(),
    RunPhase.FAILED: frozenset(),
    RunPhase.CANCELLED: frozenset(),
}


@dataclass(slots=True)
class AgentRunState:
    """Mutable state owned by exactly one running async generator."""

    run_id: str
    session_id: str
    phase: RunPhase = RunPhase.CREATED
    step: int = 0
    sequence: int = 0
    turn: list[HarnessMessage] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)

    def transition(self, phase: RunPhase) -> None:
        if phase is self.phase:
            return
        if phase not in _ALLOWED_TRANSITIONS[self.phase]:
            raise RuntimeError(f"Invalid runtime transition: {self.phase} -> {phase}")
        self.phase = phase

    def event(
        self,
        event_type: HarnessEventType,
        data: dict[str, Any] | None = None,
    ) -> HarnessEvent:
        self.sequence += 1
        return HarnessEvent(
            type=event_type,
            run_id=self.run_id,
            session_id=self.session_id,
            sequence=self.sequence,
            phase=self.phase,
            step=self.step,
            data=data or {},
        )


class CareerPilotHarness:
    """Provider-neutral, event-driven model/tool runtime owned by CareerPilot."""

    def __init__(
        self,
        model: ModelGateway,
        tools: ToolRegistry | None = None,
        session_store=None,
        *,
        max_steps: int = 4,
        context_window_manager: ContextWindowManager | None = None,
        model_timeout_seconds: float = 60.0,
        tool_timeout_seconds: float = 30.0,
        event_payload_limit: int = 2_000,
        run_store: SqliteAgentRunStore | None = None,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        if model_timeout_seconds <= 0 or tool_timeout_seconds <= 0:
            raise ValueError("Harness timeouts must be positive")
        self._model = model
        self._tools = tools or ToolRegistry()
        self._sessions = session_store or InMemorySessionStore()
        self._max_steps = max_steps
        self._model_timeout_seconds = model_timeout_seconds
        self._tool_timeout_seconds = tool_timeout_seconds
        self._event_payload_limit = max(256, event_payload_limit)
        self._run_store = run_store
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._context_window = context_window_manager or ContextWindowManager(
            compaction_store=(
                self._sessions if hasattr(self._sessions, "save_compaction") else None
            )
        )

    async def run(
        self,
        *,
        user_message: str,
        system_context: str,
        session_id: str,
        allowed_tool_names: frozenset[str] | None = None,
        runtime_tools=(),
        run_id: str | None = None,
    ) -> HarnessRunResult:
        """Collect the event stream for callers that only need a final result."""

        completed: HarnessEvent | None = None
        cancelled = False
        async for event in self.stream(
            user_message=user_message,
            system_context=system_context,
            session_id=session_id,
            allowed_tool_names=allowed_tool_names,
            runtime_tools=runtime_tools,
            run_id=run_id,
        ):
            if event.type is HarnessEventType.RUN_COMPLETED:
                completed = event
            elif event.type is HarnessEventType.RUN_CANCELLED:
                cancelled = True
        if cancelled:
            raise RunCancellationRequested("Agent run cancellation was requested")
        if completed is None:
            raise RuntimeError("Harness stream ended without a terminal result")
        return HarnessRunResult(
            reply=str(completed.data["reply"]),
            steps=completed.step,
            tool_names=tuple(completed.data["tool_names"]),
            usage=dict(completed.data["usage"]),
            run_id=completed.run_id,
            citation_ids=tuple(completed.data.get("citation_ids", ())),
            citation_warnings=tuple(completed.data.get("citation_warnings", ())),
        )

    async def stream(
        self,
        *,
        user_message: str,
        system_context: str,
        session_id: str,
        allowed_tool_names: frozenset[str] | None = None,
        runtime_tools=(),
        run_id: str | None = None,
    ) -> AsyncIterator[HarnessEvent]:
        """Execute one turn and emit stable, provider-neutral runtime events."""

        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            async for event in self._stream_turn(
                user_message=user_message,
                system_context=system_context,
                session_id=session_id,
                allowed_tool_names=allowed_tool_names,
                runtime_tools=runtime_tools,
                run_id=run_id,
            ):
                if self._run_store is not None:
                    await self._run_store.append_harness_event(event)
                yield event

    async def _stream_turn(
        self,
        *,
        user_message: str,
        system_context: str,
        session_id: str,
        allowed_tool_names: frozenset[str] | None,
        runtime_tools,
        run_id: str | None,
    ) -> AsyncIterator[HarnessEvent]:

        state = AgentRunState(run_id or str(uuid4()), session_id)
        state.transition(RunPhase.RUNNING)
        yield state.event(HarnessEventType.RUN_STARTED)

        try:
            full_history = await self._sessions.load(session_id)
            history = await self._context_window.compile(session_id, full_history)
            state.turn.append(HarnessMessage(role="user", content=user_message))
            registry = self._tools.overlay(tuple(runtime_tools))
            policy = ToolPolicy(allowed_tool_names)

            for step in range(1, self._max_steps + 1):
                await self._raise_if_cancelled(state.run_id)
                state.step = step
                state.transition(RunPhase.MODEL)
                yield state.event(HarnessEventType.MODEL_STARTED)

                request = ModelRequest(
                    messages=(
                        HarnessMessage(role="system", content=system_context),
                        *history,
                        *state.turn,
                    ),
                    tools=registry.schemas(policy),
                )
                response: ModelResponse | None = None
                async with asyncio.timeout(self._model_timeout_seconds):
                    async for model_event in self._stream_model(request):
                        if model_event.text_delta:
                            yield state.event(
                                HarnessEventType.TEXT_DELTA,
                                {"text": model_event.text_delta},
                            )
                        if model_event.response is not None:
                            response = model_event.response
                if response is None:
                    raise RuntimeError("Model stream ended without a final response")

                _merge_usage(state.usage, response.usage)
                assistant = HarnessMessage(
                    role="assistant",
                    content=response.text,
                    tool_calls=response.tool_calls,
                )
                state.turn.append(assistant)
                yield state.event(
                    HarnessEventType.MODEL_COMPLETED,
                    {
                        "finish_reason": response.finish_reason,
                        "tool_call_count": len(response.tool_calls),
                        "usage": dict(response.usage),
                    },
                )

                if not response.tool_calls:
                    if not response.text:
                        raise RuntimeError("Model returned neither text nor tool calls")
                    await self._sessions.append(session_id, tuple(state.turn))
                    citation_ids, citation_warnings = _audit_citations(
                        response.text, tuple(state.turn)
                    )
                    state.transition(RunPhase.COMPLETED)
                    yield state.event(
                        HarnessEventType.RUN_COMPLETED,
                        {
                            "reply": response.text,
                            "tool_names": list(state.tool_names),
                            "usage": dict(state.usage),
                            "citation_ids": list(citation_ids),
                            "citation_warnings": list(citation_warnings),
                        },
                    )
                    return

                state.transition(RunPhase.TOOLS)
                for call in response.tool_calls:
                    await self._raise_if_cancelled(state.run_id)
                    state.tool_names.append(call.name)
                    call_data = {
                        "tool_call_id": call.id,
                        "name": call.name,
                        "arguments": _sanitize_event_value(
                            call.arguments, self._event_payload_limit
                        ),
                    }
                    yield state.event(HarnessEventType.TOOL_REQUESTED, call_data)
                    yield state.event(HarnessEventType.TOOL_STARTED, call_data)
                    try:
                        result = await asyncio.wait_for(
                            registry.execute(call.name, call.arguments, policy),
                            timeout=self._tool_timeout_seconds,
                        )
                    except TimeoutError:
                        # A slow external provider is an observation the model can
                        # recover from, not a reason to crash the entire chat API.
                        result = json.dumps(
                            {
                                "status": "timeout",
                                "tool": call.name,
                                "error": (
                                    f"tool exceeded {self._tool_timeout_seconds:g}s timeout"
                                ),
                            },
                            ensure_ascii=False,
                        )
                    state.turn.append(
                        HarnessMessage(
                            role="tool",
                            content=result,
                            tool_call_id=call.id,
                            name=call.name,
                        )
                    )
                    yield state.event(
                        HarnessEventType.TOOL_COMPLETED,
                        {
                            **call_data,
                            "result": _sanitize_event_value(
                                result, self._event_payload_limit
                            ),
                        },
                    )

            await self._sessions.append(session_id, tuple(state.turn))
            raise MaxStepsExceeded(f"Agent exceeded {self._max_steps} model steps")
        except asyncio.CancelledError:
            state.transition(RunPhase.CANCELLED)
            yield state.event(HarnessEventType.RUN_CANCELLED)
            raise
        except RunCancellationRequested:
            state.transition(RunPhase.CANCELLED)
            yield state.event(HarnessEventType.RUN_CANCELLED)
            return
        except Exception as exc:
            state.transition(RunPhase.FAILED)
            yield state.event(
                HarnessEventType.RUN_FAILED,
                {"error_type": type(exc).__name__, "message": str(exc)},
            )
            raise

    async def _stream_model(
        self, request: ModelRequest
    ) -> AsyncIterator[ModelStreamEvent]:
        stream = getattr(self._model, "stream", None)
        if callable(stream):
            async for event in stream(request):
                yield event
            return

        # Compatibility path for custom gateways written before streaming was
        # introduced. Provider adapters should implement stream().
        response = await self._model.generate(request)
        if response.text:
            yield ModelStreamEvent(text_delta=response.text)
        yield ModelStreamEvent(response=response)

    async def _raise_if_cancelled(self, run_id: str) -> None:
        if self._run_store is not None and await self._run_store.cancellation_requested(
            run_id
        ):
            raise RunCancellationRequested("Agent run cancellation was requested")


def _merge_usage(total: dict[str, int], current: dict[str, int]) -> None:
    for key, value in current.items():
        total[key] = total.get(key, 0) + value


_SENSITIVE_EVENT_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "confirmation_token",
        "cookie",
        "password",
        "secret",
        "token",
    }
)


def _sanitize_event_value(value: Any, limit: int) -> Any:
    """Bound event payloads and redact common credential-shaped fields."""

    if isinstance(value, dict):
        sanitized = {
            str(key): (
                "[REDACTED]"
                if str(key).casefold() in _SENSITIVE_EVENT_KEYS
                else _sanitize_event_value(item, limit)
            )
            for key, item in value.items()
        }
        encoded = json.dumps(sanitized, ensure_ascii=False, default=str)
        return (
            sanitized
            if len(encoded) <= limit
            else {"summary": encoded[:limit], "truncated": True}
        )
    if isinstance(value, (list, tuple)):
        return [_sanitize_event_value(item, limit) for item in value[:50]]
    if isinstance(value, str) and len(value) > limit:
        return f"{value[:limit]}…[truncated]"
    return value


def _audit_citations(
    reply: str, messages: tuple[HarnessMessage, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    available: set[str] = set()
    for message in messages:
        if message.role != "tool":
            continue
        try:
            payload = json.loads(message.content)
        except (TypeError, json.JSONDecodeError):
            continue
        evidence = payload.get("context_pack", {}).get("evidence", ())
        if isinstance(evidence, list):
            available.update(
                str(item["citation_id"])
                for item in evidence
                if isinstance(item, dict) and item.get("citation_id")
            )
    cited = tuple(dict.fromkeys(re.findall(r"\[(S\d+)\]", reply)))
    valid = tuple(item for item in cited if item in available)
    warnings: list[str] = []
    invalid = tuple(item for item in cited if item not in available)
    if invalid:
        warnings.append(f"invalid_citations:{','.join(invalid)}")
    if available and not cited:
        warnings.append("missing_citations")
    return valid, tuple(warnings)
