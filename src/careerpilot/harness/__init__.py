"""CareerPilot-owned agent harness.

The package intentionally owns the runtime contracts instead of exposing a
framework-specific graph to the rest of the product.
"""

from careerpilot.harness.runtime import CareerPilotHarness, HarnessRunResult

__all__ = ["CareerPilotHarness", "HarnessRunResult"]
