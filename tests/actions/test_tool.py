import json

from careerpilot.actions.registry import build_mvp_capability_registry
from careerpilot.actions.service import ActionService
from careerpilot.actions.store import SqliteActionStore
from careerpilot.actions.tool import build_action_tools


def test_agent_tools_expose_status_and_preview_but_never_apply(tmp_path) -> None:
    registry = build_mvp_capability_registry()
    store = SqliteActionStore(tmp_path / "actions.db")
    service = ActionService(registry=registry, store=store, connectors={})
    try:
        store.grant(
            owner_id="owner-a",
            provider_id="feishu",
            capabilities=("document.create",),
            purpose="career_artifact_creation",
        )
        tools = build_action_tools("owner-a", registry, store, service)

        assert {tool.name for tool in tools} == {
            "get_integration_authorization",
            "preview_external_action",
        }
        status_tool = next(tool for tool in tools if tool.name == "get_integration_authorization")
        preview_tool = next(tool for tool in tools if tool.name == "preview_external_action")
        status = json.loads(status_tool.invoke({}))
        preview = json.loads(
            preview_tool.invoke(
                {
                    "provider_id": "feishu",
                    "capability": "document.create",
                    "payload": {"title": "Career Plan", "content": "# Plan"},
                }
            )
        )

        assert any(
            item["provider_id"] == "feishu"
            and item["capability"] == "document.create"
            and item["grant_state"] == "granted"
            for item in status["items"]
        )
        assert preview["requires_confirmation"] is True
        assert preview["action_id"]
        assert "apply" not in {tool.name for tool in tools}
    finally:
        store.close()
