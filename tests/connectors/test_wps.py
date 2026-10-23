import httpx
import pytest

from careerpilot.connectors.wps import WpsConnector


@pytest.mark.asyncio
async def test_wps_create_posts_exact_contract_without_persisting_token() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": {
                    "file": {
                        "id": "file_1",
                        "name": "Career Plan",
                        "url": "https://www.kdocs.cn/l/career-plan",
                    }
                }
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
        )
        outcome = await connector.execute(
            "document.create", {"name": "Career Plan", "file_type": "docx"}
        )

    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/v7/drives/drive_1/files/parent_1/create"
    assert request.headers["Authorization"] == "Bearer secret-token"
    assert request.headers["Content-Type"] == "application/json"
    assert request.content == (
        b'{"file_id":"client_file_1","file_type":"docx","name":"Career Plan",'
        b'"on_name_conflict":"rename"}'
    )
    assert outcome.external_reference == "file_1"
    assert "secret-token" not in repr(outcome)


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
