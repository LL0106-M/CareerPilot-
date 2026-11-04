from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


class DirectionExplicitness(StrEnum):
    NONE = "none"
    UNCERTAIN = "uncertain"
    IMPLICIT = "implicit"
    EXPLICIT = "explicit"


class DirectionSignalAction(StrEnum):
    NONE = "none"
    CLARIFY = "clarify"
    ASK_TO_ADD = "ask_to_add"
    ADD_TO_COMPASS = "add_to_compass"


@dataclass(frozen=True, slots=True)
class DirectionSignal:
    explicitness: DirectionExplicitness
    action: DirectionSignalAction
    label: str | None = None
    source_quote: str | None = None
    reason: str | None = None
    confidence: float = 0.0

    @classmethod
    def none(cls) -> "DirectionSignal":
        return cls(DirectionExplicitness.NONE, DirectionSignalAction.NONE)

    @property
    def detected(self) -> bool:
        return self.explicitness not in {
            DirectionExplicitness.NONE,
            DirectionExplicitness.UNCERTAIN,
        }


class DirectionSignalDetector(Protocol):
    async def analyze(
        self, user_message: str, assistant_message: str
    ) -> DirectionSignal: ...


class JsonDirectionSignalDetector:
    """Extract a provenance-bound direction signal without mutating state."""

    _actions = {
        DirectionExplicitness.NONE: DirectionSignalAction.NONE,
        DirectionExplicitness.UNCERTAIN: DirectionSignalAction.CLARIFY,
        DirectionExplicitness.IMPLICIT: DirectionSignalAction.ASK_TO_ADD,
        DirectionExplicitness.EXPLICIT: DirectionSignalAction.ADD_TO_COMPASS,
    }

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    async def analyze(
        self, user_message: str, assistant_message: str
    ) -> DirectionSignal:
        try:
            response = await self._model.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "你是职业方向信号提取器，不是职业决策者。只判断用户是否表达了"
                            "一个可命名的职业方向。explicit 表示用户明确要考虑、申请或推进；"
                            "implicit 表示持续兴趣或倾向但没有确认；uncertain 表示证据不足；"
                            "none 表示没有方向信号。source_quote 必须逐字摘自用户消息，不能改写。"
                            "只输出 JSON 对象：{\"explicitness\":\"none|uncertain|implicit|explicit\","
                            "\"label\":string|null,\"source_quote\":string|null,\"reason\":string,"
                            "\"confidence\":0到1数字,\"suggested_action\":"
                            "\"none|clarify|ask_to_add|add_to_compass\"}。"
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"用户消息：{user_message}\n"
                            f"助手回复：{assistant_message}\n"
                            "助手回复只用于消歧，不能作为用户意图证据。"
                        )
                    ),
                ]
            )
            content = response.content
            if not isinstance(content, str):
                return DirectionSignal.none()
            return self._parse(content, user_message)
        except Exception:
            return DirectionSignal.none()

    @classmethod
    def _parse(cls, content: str, user_message: str) -> DirectionSignal:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) < 3 or lines[-1].strip() != "```":
                return DirectionSignal.none()
            stripped = "\n".join(lines[1:-1]).strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].lstrip()
        try:
            value = json.loads(stripped)
        except (TypeError, json.JSONDecodeError):
            return DirectionSignal.none()
        if not isinstance(value, dict):
            return DirectionSignal.none()
        try:
            explicitness = DirectionExplicitness(value.get("explicitness"))
            action = DirectionSignalAction(value.get("suggested_action"))
        except (TypeError, ValueError):
            return DirectionSignal.none()
        if cls._actions[explicitness] is not action:
            return DirectionSignal.none()

        confidence = value.get("confidence")
        reason = value.get("reason")
        label = value.get("label")
        quote = value.get("source_quote")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            return DirectionSignal.none()
        if not 0 <= float(confidence) <= 1 or not isinstance(reason, str):
            return DirectionSignal.none()

        if explicitness in {DirectionExplicitness.NONE, DirectionExplicitness.UNCERTAIN}:
            return DirectionSignal(
                explicitness=explicitness,
                action=action,
                reason=reason.strip() or None,
                confidence=float(confidence),
            )
        if not isinstance(label, str) or not label.strip():
            return DirectionSignal.none()
        if not isinstance(quote, str) or not quote.strip() or quote not in user_message:
            return DirectionSignal.none()
        return DirectionSignal(
            explicitness=explicitness,
            action=action,
            label=" ".join(label.split()),
            source_quote=quote,
            reason=reason.strip() or None,
            confidence=float(confidence),
        )
