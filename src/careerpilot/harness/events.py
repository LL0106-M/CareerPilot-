from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RunPhase(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    MODEL = "model"
    TOOLS = "tools"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HarnessEventType(StrEnum):
    RUN_STARTED = "run.started"
    MODEL_STARTED = "model.started"
    TEXT_DELTA = "model.text_delta"
    MODEL_COMPLETED = "model.completed"
    TOOL_REQUESTED = "tool.requested"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"


@dataclass(frozen=True, slots=True)
class HarnessEvent:
    """Provider-neutral event emitted by one harness run.

    Payloads contain JSON-compatible values so transports can map the same
    event stream to SSE, WebSocket, an event store, or an in-process consumer.
    """

    type: HarnessEventType
    run_id: str
    session_id: str
    sequence: int
    phase: RunPhase
    step: int = 0
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "phase": self.phase.value,
            "step": self.step,
            "data": self.data,
        }
