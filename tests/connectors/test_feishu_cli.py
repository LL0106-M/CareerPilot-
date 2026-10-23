import json

import pytest

from careerpilot.actions.service import ConnectorError, ConnectorOutcome
from careerpilot.connectors.feishu_cli import CommandResult, FeishuCliConnector


class RecordingRunner:
    def __init__(self, result: CommandResult) -> None:
        self.result = result
        self.calls = []

    async def run(self, argv, *, stdin_text, timeout_seconds):
        self.calls.append((argv, stdin_text, timeout_seconds))
        return self.result


@pytest.mark.asyncio
async def test_document_create_uses_fixed_argv_stdin_and_parses_json() -> None:
    runner = RecordingRunner(
        CommandResult(
            returncode=0,
            stdout=json.dumps(
                {
                    "ok": True,
                    "identity": "user",
                    "data": {
                        "document": {
                            "document_id": "docx_123",
                            "url": "https://example.feishu.cn/docx/docx_123",
                        }
                    },
                }
            ),
            stderr="",
        )
    )
    connector = FeishuCliConnector(runner=runner, executable="lark-cli", timeout_seconds=12)

    outcome = await connector.execute(
        "document.create",
        {"title": "Career Plan", "content": "# Next step", "parent_token": "folder_1"},
    )

    assert runner.calls == [
        (
            (
                "lark-cli",
                "docs",
                "+create",
                "--doc-format",
                "markdown",
                "--title",
                "Career Plan",
                "--content",
                "-",
                "--parent-token",
                "folder_1",
                "--as",
                "user",
                "--format",
                "json",
            ),
            "# Next step",
            12,
        )
    ]
    assert outcome.external_reference == "docx_123"
    assert outcome.observations == ("https://example.feishu.cn/docx/docx_123",)


@pytest.mark.asyncio
async def test_calendar_create_uses_only_allowlisted_arguments() -> None:
    runner = RecordingRunner(
        CommandResult(
            returncode=0,
            stdout=json.dumps(
                {
                    "ok": True,
                    "identity": "user",
                    "data": {"event_id": "event_1", "summary": "Interview"},
                }
            ),
            stderr="",
        )
    )
    connector = FeishuCliConnector(runner=runner)

    outcome = await connector.execute(
        "calendar.create",
        {
            "summary": "Interview",
            "start": "2026-10-25T10:00:00+08:00",
            "end": "2026-10-25T11:00:00+08:00",
            "ignored_shell_fragment": "; Remove-Item -Recurse C:\\",
        },
    )

    argv = runner.calls[0][0]
    assert argv == (
        "lark-cli",
        "calendar",
        "+create",
        "--summary",
        "Interview",
        "--start",
        "2026-10-25T10:00:00+08:00",
        "--end",
        "2026-10-25T11:00:00+08:00",
        "--as",
        "user",
        "--format",
        "json",
    )
    assert outcome.external_reference == "event_1"


@pytest.mark.asyncio
async def test_timeout_and_error_envelopes_are_mapped() -> None:
    timeout_runner = RecordingRunner(
        CommandResult(returncode=124, stdout="", stderr="command timed out", timed_out=True)
    )
    connector = FeishuCliConnector(runner=timeout_runner)
    with pytest.raises(ConnectorError) as timeout_error:
        await connector.execute("document.create", {"title": "Plan", "content": "body"})
    assert timeout_error.value.uncertain is True

    error_runner = RecordingRunner(
        CommandResult(
            returncode=1,
            stdout="",
            stderr=json.dumps({"ok": False, "error": {"message": "permission denied"}}),
        )
    )
    connector = FeishuCliConnector(runner=error_runner)
    with pytest.raises(RuntimeError, match="permission denied"):
        await connector.execute("document.create", {"title": "Plan", "content": "body"})


@pytest.mark.asyncio
async def test_feishu_rejects_non_user_identity_and_verifies_by_readback() -> None:
    bot_runner = RecordingRunner(
        CommandResult(
            0,
            json.dumps(
                {
                    "ok": True,
                    "identity": "bot",
                    "data": {"document": {"document_id": "docx_123"}},
                }
            ),
            "",
        )
    )
    with pytest.raises(RuntimeError, match="user identity"):
        await FeishuCliConnector(runner=bot_runner).execute(
            "document.create", {"title": "Plan", "content": "body"}
        )

    verify_runner = RecordingRunner(
        CommandResult(
            0,
            json.dumps(
                {
                    "ok": True,
                    "identity": "user",
                    "data": {"document": {"document_id": "docx_123"}},
                }
            ),
            "",
        )
    )
    connector = FeishuCliConnector(runner=verify_runner)
    assert await connector.verify(
        ConnectorOutcome(external_reference="docx_123", verification_kind="document")
    )
    assert verify_runner.calls[0][0] == (
        "lark-cli",
        "docs",
        "+fetch",
        "--doc",
        "docx_123",
        "--detail",
        "with-ids",
        "--as",
        "user",
        "--format",
        "json",
    )
