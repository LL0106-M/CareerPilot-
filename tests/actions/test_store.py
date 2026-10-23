from careerpilot.actions.registry import build_mvp_capability_registry
from careerpilot.actions.store import SqliteActionStore


def test_grants_are_owner_scoped_and_visible_by_capability(tmp_path) -> None:
    store = SqliteActionStore(tmp_path / "actions.db")
    registry = build_mvp_capability_registry()
    try:
        grant = store.grant(
            owner_id="owner-a",
            provider_id="feishu",
            capabilities=("document.create",),
            purpose="career_artifact_creation",
            scope_snapshot=("docs:write",),
        )

        assert store.find_active_grant("owner-a", "feishu", "document.create") == grant
        assert store.find_active_grant("owner-b", "feishu", "document.create") is None
        states = store.list_authorization("owner-a", registry)
        feishu_document = next(
            item
            for item in states
            if item.provider_id == "feishu" and item.capability == "document.create"
        )
        assert feishu_document.grant_state == "granted"
        assert feishu_document.grant_id == grant.id
        assert feishu_document.scope_snapshot == ("docs:write",)
    finally:
        store.close()


def test_revoked_grant_is_immediately_unusable(tmp_path) -> None:
    store = SqliteActionStore(tmp_path / "actions.db")
    try:
        grant = store.grant(
            owner_id="owner-a",
            provider_id="wps",
            capabilities=("document.create",),
            purpose="career_artifact_creation",
        )

        assert store.revoke("owner-b", grant.id) is False
        assert store.revoke("owner-a", grant.id) is True
        assert store.find_active_grant("owner-a", "wps", "document.create") is None
    finally:
        store.close()


def test_store_creates_default_parent_directory(tmp_path) -> None:
    path = tmp_path / "nested" / "actions" / "careerpilot.db"

    store = SqliteActionStore(path)
    try:
        assert path.exists()
    finally:
        store.close()
