"""Fixed domain capability registry exposed to the Personal Agent."""

from collections.abc import Iterable

from careerpilot.actions.models import CapabilityDefinition, ProviderDefinition


class CapabilityRegistry:
    def __init__(self, providers: Iterable[ProviderDefinition]) -> None:
        self._providers = {provider.provider_id: provider for provider in providers}
        self._capabilities = {
            capability.id: capability
            for provider in self._providers.values()
            for capability in provider.capabilities
        }

    @property
    def provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    @property
    def capability_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._capabilities))

    def get(self, provider_id: str, capability: str) -> CapabilityDefinition:
        capability_id = f"{provider_id}:{capability}"
        try:
            return self._capabilities[capability_id]
        except KeyError as error:
            raise KeyError(f"unknown capability: {capability_id}") from error


def build_mvp_capability_registry() -> CapabilityRegistry:
    return CapabilityRegistry(
        (
            ProviderDefinition(
                provider_id="feishu",
                display_name="飞书",
                auth_mode="oauth",
                capabilities=(
                    CapabilityDefinition(
                        provider_id="feishu",
                        capability="document.create",
                        risk_level="L3",
                        write=True,
                        requires_confirmation=True,
                        required_scopes=("docs:write",),
                    ),
                    CapabilityDefinition(
                        provider_id="feishu",
                        capability="calendar.create",
                        risk_level="L3",
                        write=True,
                        requires_confirmation=True,
                        required_scopes=("calendar:write",),
                    ),
                ),
            ),
            ProviderDefinition(
                provider_id="netease_mail",
                display_name="网易邮箱",
                auth_mode="app_password",
                capabilities=(
                    CapabilityDefinition(
                        provider_id="netease_mail",
                        capability="email.search_recruiting",
                        risk_level="L1",
                        write=False,
                        requires_confirmation=False,
                        required_scopes=("mail:read",),
                    ),
                ),
            ),
            ProviderDefinition(
                provider_id="wps",
                display_name="WPS",
                auth_mode="oauth",
                capabilities=(
                    CapabilityDefinition(
                        provider_id="wps",
                        capability="document.create",
                        risk_level="L3",
                        write=True,
                        requires_confirmation=True,
                        required_scopes=("kso.file.readwrite",),
                    ),
                ),
            ),
        )
    )
