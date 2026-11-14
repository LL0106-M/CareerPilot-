"""CareerPilot-owned agent harness.

The package intentionally owns the runtime contracts instead of exposing a
framework-specific graph to the rest of the product.
"""

from typing import TYPE_CHECKING, Any

from careerpilot.harness.events import HarnessEvent, HarnessEventType, RunPhase

if TYPE_CHECKING:
    from careerpilot.harness.runtime import AgentRunState, CareerPilotHarness, HarnessRunResult

__all__ = [
    "AgentRunState",
    "CareerPilotHarness",
    "HarnessEvent",
    "HarnessEventType",
    "HarnessRunResult",
    "RunPhase",
]


def __getattr__(name: str) -> Any:
    if name in {"AgentRunState", "CareerPilotHarness", "HarnessRunResult"}:
        from careerpilot.harness import runtime

        return getattr(runtime, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
