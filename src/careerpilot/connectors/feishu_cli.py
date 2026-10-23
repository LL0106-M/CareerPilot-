"""Safe adapter for the official Lark/Feishu CLI."""

import asyncio
import json
from dataclasses import dataclass
from typing import Protocol

from careerpilot.actions.service import ConnectorOutcome


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class CommandRunner(Protocol):
    async def run(
        self, argv: tuple[str, ...], *, stdin_text: str | None, timeout_seconds: float
    ) -> CommandResult: ...


class AsyncioCommandRunner:
    async def run(
        self, argv: tuple[str, ...], *, stdin_text: str | None, timeout_seconds: float
    ) -> CommandResult:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE if stdin_text is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(stdin_text.encode() if stdin_text is not None else None),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            return CommandResult(124, "", "command timed out", timed_out=True)
        return CommandResult(
            process.returncode or 0,
            stdout.decode(errors="replace"),
            stderr.decode(errors="replace"),
        )


class FeishuCliConnector:
    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        executable: str = "lark-cli",
        timeout_seconds: float = 30,
    ) -> None:
        self._runner = runner or AsyncioCommandRunner()
        self._executable = executable
        self._timeout_seconds = timeout_seconds

    async def probe(self) -> bool:
        result = await self._runner.run(
            (self._executable, "auth", "status", "--verify", "--format", "json"),
            stdin_text=None,
            timeout_seconds=self._timeout_seconds,
        )
        return result.returncode == 0 and not result.timed_out

    async def execute(self, capability: str, payload: dict) -> ConnectorOutcome:
        if capability == "document.create":
            argv, stdin_text = self._document_command(payload)
        elif capability == "calendar.create":
            argv, stdin_text = self._calendar_command(payload)
        else:
            raise ValueError(f"unsupported Feishu capability: {capability}")

        result = await self._runner.run(
            argv, stdin_text=stdin_text, timeout_seconds=self._timeout_seconds
        )
        if result.timed_out:
            raise TimeoutError("Feishu CLI timed out")
        envelope = self._parse_envelope(result)
        data = envelope.get("data", {})
        if capability == "document.create":
            document = data.get("document", data)
            reference = document.get("document_id")
            observations = tuple(value for value in (document.get("url"),) if value)
        else:
            event = data.get("event", data)
            reference = event.get("event_id")
            observations = tuple(value for value in (event.get("app_link"),) if value)
        if not reference:
            raise RuntimeError("Feishu CLI returned no external reference")
        return ConnectorOutcome(external_reference=reference, observations=observations)

    async def verify(self, outcome: ConnectorOutcome) -> bool:
        return bool(outcome.external_reference)

    def _document_command(self, payload: dict) -> tuple[tuple[str, ...], str]:
        argv = [
            self._executable,
            "docs",
            "+create",
            "--doc-format",
            "markdown",
            "--title",
            str(payload["title"]),
            "--content",
            "-",
        ]
        if parent_token := payload.get("parent_token"):
            argv.extend(("--parent-token", str(parent_token)))
        argv.extend(("--format", "json"))
        return tuple(argv), str(payload.get("content", ""))

    def _calendar_command(self, payload: dict) -> tuple[tuple[str, ...], None]:
        argv = [
            self._executable,
            "calendar",
            "+create",
            "--summary",
            str(payload.get("summary", "")),
            "--start",
            str(payload["start"]),
            "--end",
            str(payload["end"]),
        ]
        if calendar_id := payload.get("calendar_id"):
            argv.extend(("--calendar-id", str(calendar_id)))
        argv.extend(("--format", "json"))
        return tuple(argv), None

    @staticmethod
    def _parse_envelope(result: CommandResult) -> dict:
        raw = result.stdout if result.returncode == 0 else result.stderr
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError("Feishu CLI returned an invalid response") from error
        if result.returncode != 0 or not envelope.get("ok", False):
            message = envelope.get("error", {}).get("message", "Feishu CLI request failed")
            raise RuntimeError(str(message))
        return envelope
