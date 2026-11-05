from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal, Protocol

from careerpilot.harness.contracts import HarnessMessage, ModelGateway, ModelRequest
from careerpilot.product_store import ProductStore

FuturePathKind = Literal["continue", "adjacent", "unexpected"]
EXPECTED_PATH_KINDS: tuple[FuturePathKind, ...] = (
    "continue",
    "adjacent",
    "unexpected",
)


class FuturePathValidationError(ValueError):
    pass


class JourneyNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class FuturePath:
    kind: FuturePathKind
    label: str
    title: str
    summary: str
    signals: tuple[str, ...]
    tension: str
    question: str

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "label": self.label,
            "title": self.title,
            "summary": self.summary,
            "signals": list(self.signals),
            "tension": self.tension,
            "question": self.question,
        }


@dataclass(frozen=True, slots=True)
class FutureLetter:
    id: str
    journey_id: str
    message: str
    paths: tuple[FuturePath, ...]
    created_at: str
    takeaway: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "journey_id": self.journey_id,
            "message": self.message,
            "paths": [path.to_dict() for path in self.paths],
            "created_at": self.created_at,
            "takeaway": self.takeaway,
        }


class FuturePathGenerator(Protocol):
    async def generate(
        self,
        *,
        journey: dict[str, object],
        tasks: list[dict[str, object]],
        message: str,
    ) -> tuple[FuturePath, ...]: ...


def validate_future_paths(paths: tuple[FuturePath, ...]) -> tuple[FuturePath, ...]:
    if len(paths) != 3 or tuple(path.kind for path in paths) != EXPECTED_PATH_KINDS:
        raise FuturePathValidationError(
            "future letter must contain continue, adjacent, and unexpected paths in order"
        )
    for path in paths:
        values = (path.label, path.title, path.summary, path.tension, path.question)
        if any(not value.strip() for value in values):
            raise FuturePathValidationError("future path fields cannot be empty")
        combined = " ".join(values)
        if re.search(r"(?:成功率|概率)\s*(?:为|是|:|：)?\s*\d+\s*%", combined):
            raise FuturePathValidationError("future paths cannot claim numeric probabilities")
    return paths


class ModelFuturePathGenerator:
    def __init__(self, model: ModelGateway) -> None:
        self._model = model

    async def generate(
        self,
        *,
        journey: dict[str, object],
        tasks: list[dict[str, object]],
        message: str,
    ) -> tuple[FuturePath, ...]:
        response = await self._model.generate(
            ModelRequest(
                messages=(
                    HarnessMessage(
                        role="system",
                        content=(
                            "你是 CareerPilot 当前的职业推演能力，不是另一个 agent。"
                            "根据真实航程生成恰好三种可能路径，不做预测承诺，不给成功概率、"
                            "具体公司或薪资断言。只返回 JSON，不要 Markdown。格式为 "
                            '{"paths":[{"kind":"continue|adjacent|unexpected",'
                            '"label":"...","title":"...","summary":"...",'
                            '"signals":["..."],"tension":"...","question":"...?"}]}。'
                            "顺序必须是 continue、adjacent、unexpected。"
                        ),
                    ),
                    HarnessMessage(
                        role="user",
                        content=json.dumps(
                            {"journey": journey, "tasks": tasks, "message": message},
                            ensure_ascii=False,
                        ),
                    ),
                )
            )
        )
        return parse_future_paths(response.text)


def parse_future_paths(text: str) -> tuple[FuturePath, ...]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
    try:
        raw = json.loads(cleaned)
        items = raw["paths"]
        paths = tuple(
            FuturePath(
                kind=item["kind"],
                label=str(item["label"]).strip(),
                title=str(item["title"]).strip(),
                summary=str(item["summary"]).strip(),
                signals=tuple(str(signal).strip() for signal in item.get("signals", [])[:4]),
                tension=str(item["tension"]).strip(),
                question=str(item["question"]).strip(),
            )
            for item in items
        )
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise FuturePathValidationError("model returned an invalid future letter") from exc
    return validate_future_paths(paths)


class FutureLetterService:
    def __init__(self, store: ProductStore, generator: FuturePathGenerator) -> None:
        self._store = store
        self._generator = generator

    async def generate(self, owner_id: str, journey_id: str, message: str) -> FutureLetter:
        snapshot = self._store.get_direction_journey(owner_id, journey_id)
        if snapshot is None:
            raise JourneyNotFoundError(journey_id)
        paths = validate_future_paths(
            await self._generator.generate(
                journey=snapshot["journey"],
                tasks=snapshot["tasks"],
                message=message,
            )
        )
        return _letter_from_record(
            self._store.save_future_letter(
                owner_id,
                journey_id=journey_id,
                message=message,
                paths=[path.to_dict() for path in paths],
            )
        )

    def get(self, owner_id: str, journey_id: str) -> FutureLetter | None:
        record = self._store.get_future_letter(owner_id, journey_id)
        return _letter_from_record(record) if record is not None else None

    def confirm_takeaway(
        self,
        owner_id: str,
        journey_id: str,
        letter_id: str,
        path_kind: FuturePathKind,
        question: str,
    ) -> dict[str, object]:
        takeaway = self._store.confirm_future_takeaway(
            owner_id,
            journey_id=journey_id,
            letter_id=letter_id,
            path_kind=path_kind,
            question=question,
        )
        if takeaway is None:
            raise JourneyNotFoundError(journey_id)
        return takeaway


def _letter_from_record(record: dict[str, object]) -> FutureLetter:
    return FutureLetter(
        id=str(record["id"]),
        journey_id=str(record["journey_id"]),
        message=str(record["message"]),
        paths=tuple(
            FuturePath(
                kind=item["kind"],
                label=str(item["label"]),
                title=str(item["title"]),
                summary=str(item["summary"]),
                signals=tuple(item.get("signals", [])),
                tension=str(item["tension"]),
                question=str(item["question"]),
            )
            for item in record["paths"]
        ),
        created_at=str(record["created_at"]),
        takeaway=record.get("takeaway"),
    )
