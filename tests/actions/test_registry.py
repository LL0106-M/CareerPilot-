import pytest

from careerpilot.actions.registry import build_mvp_capability_registry


def test_mvp_registry_exposes_only_selected_provider_capabilities() -> None:
    registry = build_mvp_capability_registry()

    assert registry.provider_ids == ("feishu", "netease_mail", "wps")
    assert registry.capability_ids == (
        "feishu:calendar.create",
        "feishu:document.create",
        "netease_mail:email.search_recruiting",
        "wps:document.create",
    )
    assert registry.get("feishu", "document.create").requires_confirmation is True
    assert registry.get("netease_mail", "email.search_recruiting").write is False


def test_registry_rejects_unknown_capability() -> None:
    registry = build_mvp_capability_registry()

    with pytest.raises(KeyError, match="unknown capability"):
        registry.get("wechat", "message.send")
