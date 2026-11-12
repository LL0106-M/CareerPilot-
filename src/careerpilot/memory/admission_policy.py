from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from careerpilot.memory.contracts import (
    AdmissionDecision,
    AdmissionReason,
    AdmissionResult,
    MemoryAuthorship,
    MemoryClaim,
    MemoryDurability,
    MemorySubject,
)
from careerpilot.memory.models import MemoryConfidence, MemorySensitivity


class SafetyFlag(StrEnum):
    PROMPT_INJECTION = "prompt_injection"
    CREDENTIAL = "credential"
    CROSS_OWNER = "cross_owner"


@dataclass(frozen=True, slots=True)
class SafetyAssessment:
    safe: bool
    flags: tuple[SafetyFlag, ...] = ()


class MemorySafetyPrefilter:
    """Deterministic hard stop before untrusted text reaches extraction or storage."""

    _injection_patterns = (
        r"忽略(?:之前|以上|上面|所有).{0,12}(?:指令|规则|提示)",
        r"(?:系统|开发者)(?:消息|指令|提示词)",
        r"(?:泄露|显示|输出|保存).{0,12}(?:系统提示|其他用户|别人的记忆)",
        r"(?:write|save|store).{0,20}(?:system prompt|developer message)",
        r"ignore.{0,20}(?:previous|prior|system).{0,20}instructions?",
    )
    _credential_patterns = (
        r"\bsk-[A-Za-z0-9_-]{12,}\b",
        r"\b(?:api[_ -]?key|access[_ -]?token|secret[_ -]?key)\s*[:：=]\s*\S{8,}",
        r"(?:密码|口令)\s*[:：=]\s*\S{4,}",
    )
    _cross_owner_patterns = (
        r"(?:其他|别的|另一位)用户的(?:记忆|数据|资料)",
        r"(?:other|another) user(?:'s)? (?:memory|data)",
    )

    def inspect(self, text: str) -> SafetyAssessment:
        flags: list[SafetyFlag] = []
        if self._matches(text, self._injection_patterns):
            flags.append(SafetyFlag.PROMPT_INJECTION)
        if self._matches(text, self._credential_patterns):
            flags.append(SafetyFlag.CREDENTIAL)
        if self._matches(text, self._cross_owner_patterns):
            flags.append(SafetyFlag.CROSS_OWNER)
        unique = tuple(dict.fromkeys(flags))
        return SafetyAssessment(safe=not unique, flags=unique)

    @staticmethod
    def _matches(text: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


class MemoryAdmissionGate:
    def __init__(self, prefilter: MemorySafetyPrefilter | None = None) -> None:
        self._prefilter = prefilter or MemorySafetyPrefilter()

    def decide(self, claim: MemoryClaim, source_text: str) -> AdmissionResult:
        safety = self._prefilter.inspect(source_text)
        if SafetyFlag.PROMPT_INJECTION in safety.flags:
            return self._result(claim, AdmissionDecision.REJECT, AdmissionReason.PROMPT_INJECTION)
        if SafetyFlag.CREDENTIAL in safety.flags:
            return self._result(
                claim,
                AdmissionDecision.REJECT,
                AdmissionReason.CREDENTIAL_MATERIAL,
            )
        if SafetyFlag.CROSS_OWNER in safety.flags:
            return self._result(claim, AdmissionDecision.REJECT, AdmissionReason.CROSS_OWNER_CLAIM)
        if claim.subject is not MemorySubject.SELF:
            return self._result(claim, AdmissionDecision.IGNORE, AdmissionReason.NON_SELF_SUBJECT)
        if claim.durability is MemoryDurability.TRANSIENT:
            return self._result(claim, AdmissionDecision.IGNORE, AdmissionReason.TRANSIENT_CONTENT)
        if claim.sensitivity is MemorySensitivity.SENSITIVE:
            return self._result(
                claim,
                AdmissionDecision.PENDING,
                AdmissionReason.SENSITIVE_REQUIRES_CONFIRMATION,
            )
        if claim.authorship in {
            MemoryAuthorship.AGENT_INFERRED,
            MemoryAuthorship.SYSTEM_OBSERVED,
        }:
            return self._result(
                claim,
                AdmissionDecision.PENDING,
                AdmissionReason.INFERRED_REQUIRES_CONFIRMATION,
            )
        if claim.confidence is MemoryConfidence.LOW:
            return self._result(claim, AdmissionDecision.PENDING, AdmissionReason.LOW_CONFIDENCE)
        if claim.durability is not MemoryDurability.DURABLE:
            return self._result(
                claim,
                AdmissionDecision.PENDING,
                AdmissionReason.REQUIRES_CONFIRMATION,
            )
        if claim.authorship is MemoryAuthorship.USER_CONFIRMED:
            return self._result(claim, AdmissionDecision.COMMIT, AdmissionReason.USER_CONFIRMED)
        return self._result(
            claim,
            AdmissionDecision.COMMIT,
            AdmissionReason.DURABLE_USER_EXPLICIT,
        )

    @staticmethod
    def _result(
        claim: MemoryClaim,
        decision: AdmissionDecision,
        reason: AdmissionReason,
    ) -> AdmissionResult:
        return AdmissionResult(decision=decision, reason_code=reason.value, claim=claim)
