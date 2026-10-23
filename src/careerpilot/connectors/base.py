"""Connector registry with provider-neutral lookup."""

from collections.abc import Mapping

from careerpilot.actions.service import Connector


class ConnectorRegistry:
    def __init__(self, connectors: Mapping[str, Connector]) -> None:
        self._connectors = dict(connectors)

    def get(self, provider_id: str) -> Connector:
        try:
            return self._connectors[provider_id]
        except KeyError as error:
            raise KeyError(f"connector is not configured: {provider_id}") from error

    def as_dict(self) -> dict[str, Connector]:
        return dict(self._connectors)
