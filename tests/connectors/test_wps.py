import httpx
import pytest

from careerpilot.actions.service import ConnectorOutcome
from careerpilot.connectors.wps import WpsConnector


@pytest.mark.asyncio
async def test_wps_create_posts_exact_contract_without_persisting_token() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"code": 0, "data": {"id": "file_1"}})
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "id": "file_1",
                    "name": "Career Plan",
                    "link_url": "https://www.kdocs.cn/l/career-plan",
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://openapi.wps.cn"
    ) as client:
        connector = WpsConnector(
            client=client,
            access_token="secret-token",
            drive_id="drive_1",
            parent_id="parent_1",
            file_id_factory=lambda: "client_file_1",
            access_key="app-id",
            secret_key="app-secret",
            date_factory=lambda: "Mon, 02 Jan 2006 15:04:05 GMT",
        )
        outcome = await connector.execute(
            "document.create", {"name": "Career Plan", "file_type": "docx"}
        )
        assert await connector.verify(outcome) is True

    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/v7/drives/drive_1/files/parent_1/create"
    assert request.headers["Authorization"] == "Bearer secret-token"
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["X-Kso-Date"] == "Mon, 02 Jan 2006 15:04:05 GMT"
    assert request.headers["X-Kso-Authorization"].startswith("KSO-1 app-id:")
    assert request.content == (
        b'{"file_id":"client_file_1","file_type":"docx","name":"Career Plan",'
        b'"on_name_conflict":"rename"}'
    )
    assert outcome.external_reference == "file_1"
    assert "secret-token" not in repr(outcome)
    assert requests[1].url.path == "/v7/files/file_1/meta"


@pytest.mark.asyncio
async def test_wps_provider_errors_are_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"code": 403001, "message": "permission denied"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://openapi.wps.cn"
    ) as client:
        connector = WpsConnector(
            client=client,
            access_token="secret-token",
            drive_id="drive_1",
            parent_id="parent_1",
        )
        with pytest.raises(RuntimeError, match="permission denied") as error:
            await connector.execute("document.create", {"name": "Plan"})

    assert "secret-token" not in str(error.value)


@pytest.mark.asyncio
async def test_wps_verify_returns_false_when_readback_id_does_not_match() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 0, "data": {"id": "different"}})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://openapi.wps.cn"
    ) as client:
        connector = WpsConnector(
            client=client,
            access_token="secret-token",
            drive_id="drive_1",
            parent_id="parent_1",
        )
        assert await connector.verify(ConnectorOutcome(external_reference="file_1")) is False
