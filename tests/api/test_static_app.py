from fastapi.testclient import TestClient

from careerpilot.api.app import create_app
from careerpilot.config import Settings


def test_built_frontend_and_spa_routes_are_served_without_swallowing_api_404(tmp_path) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<main>CareerPilot production</main>", "utf-8")
    (assets / "app.js").write_text("console.log('ready')", "utf-8")
    client = TestClient(
        create_app(Settings(_env_file=None, CAREERPILOT_FRONTEND_DIST_PATH=dist))
    )

    assert client.get("/").text == "<main>CareerPilot production</main>"
    assert client.get("/chat").text == "<main>CareerPilot production</main>"
    assert client.get("/assets/app.js").text == "console.log('ready')"
    assert client.get("/v1/does-not-exist").status_code == 404


def test_readiness_checks_runtime_directories_and_frontend_bundle(tmp_path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("ready", "utf-8")
    settings = Settings(
        _env_file=None,
        CAREERPILOT_FRONTEND_DIST_PATH=dist,
        CAREERPILOT_RAG_DB_PATH=tmp_path / "data" / "rag.db",
        CAREERPILOT_MEMORY_DB_PATH=tmp_path / "data" / "memory.db",
        CAREERPILOT_SESSION_DB_PATH=tmp_path / "data" / "sessions.db",
        CAREERPILOT_PRODUCT_DB_PATH=tmp_path / "data" / "product.db",
        CAREERPILOT_ACTION_DB_PATH=tmp_path / "data" / "actions.db",
    )
    client = TestClient(create_app(settings))

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "careerpilot-agent"}
    assert (tmp_path / "data").is_dir()
