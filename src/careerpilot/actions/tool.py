"""Safe Agent tools for authorization visibility and action previewing."""

import json
from typing import Any

from langchain_core.tools import StructuredTool

from careerpilot.actions.registry import CapabilityRegistry
from careerpilot.actions.service import ActionService
from careerpilot.actions.store import SqliteActionStore


def build_action_tools(
    owner_id: str,
    registry: CapabilityRegistry,
    store: SqliteActionStore,
    service: ActionService,
) -> tuple[StructuredTool, StructuredTool]:
    def get_integration_authorization() -> str:
        states = store.list_authorization(owner_id, registry)
        return json.dumps(
            {
                "items": [
                    {
                        "provider_id": state.provider_id,
                        "capability": state.capability,
                        "grant_state": state.grant_state,
                        "grant_id": state.grant_id,
                        "scope_snapshot": list(state.scope_snapshot),
                    }
                    for state in states
                ]
            },
            ensure_ascii=False,
        )

    def preview_external_action(
        provider_id: str,
        capability: str,
        payload: dict[str, Any],
    ) -> str:
        definition = registry.get(provider_id, capability)
        preview = service.preview(owner_id, provider_id, capability, payload)
        return json.dumps(
            {
                "action_id": preview.id,
                "preview_hash": preview.preview_hash,
                "provider_id": preview.provider_id,
                "capability": preview.capability,
                "payload": preview.payload,
                "requires_confirmation": definition.requires_confirmation,
                "next_step": (
                    "ask_user_to_confirm_in_product"
                    if definition.requires_confirmation
                    else "ready_for_user_initiated_apply"
                ),
            },
            ensure_ascii=False,
        )

    return (
        StructuredTool.from_function(
            func=get_integration_authorization,
            name="get_integration_authorization",
            description=(
                "Show which Feishu, WPS, and NetEase Mail capabilities the current user has "
                "authorized. Use before proposing an external action."
            ),
        ),
        StructuredTool.from_function(
            func=preview_external_action,
            name="preview_external_action",
            description=(
                "Create a reviewable preview for an authorized domain action. This never executes "
                "the external action; write execution requires explicit product confirmation."
            ),
        ),
    )
