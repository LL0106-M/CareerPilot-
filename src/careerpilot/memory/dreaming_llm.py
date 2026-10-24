import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from careerpilot.memory.daily_review import DailyReviewDraft
from careerpilot.memory.dreaming import (
    DreamingAnalysis,
    DreamingSnapshot,
    HypothesisProposal,
    MemoryPatchProposal,
)


class JsonDreamingAnalyzer:
    """Generate evidence-bound candidate hypotheses with the deterministic model."""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    async def analyze(self, snapshot: DreamingSnapshot) -> DreamingAnalysis:
        evidence = "\n".join(
            f"- id={item.id}; source={item.source}; content={item.content}"
            for item in snapshot.evidence
        )
        response = await self._model.ainvoke(
            [
                SystemMessage(
                    content=(
                        "你是职业成长记忆整理器。输出待验证假设、用户可见每日回顾和"
                        "可审查记忆补丁，不把推断写成事实。每项必须引用给定 evidence id。"
                        "只输出 JSON 对象，格式为 {\"hypotheses\": [{\"statement\": str, "
                        "\"confidence_band\": \"low|medium|high\", "
                        "\"supporting_evidence_ids\": [str], "
                        "\"contradicting_evidence_ids\": [str], "
                        "\"open_questions\": [str]}], \"daily_review\": null 或 "
                        "{\"local_date\": \"YYYY-MM-DD\", \"wins\": [str], \"ideas\": [str], "
                        "\"blockers\": [str], \"open_loops\": [str], \"tomorrow_step\": str|null, "
                        "\"source_event_ids\": [str]}, \"patches\": [{\"operation\": str, "
                        "\"target_type\": str, \"content\": str, "
                        "\"supporting_evidence_ids\": [str], \"requires_confirmation\": bool}]}。"
                    )
                ),
                HumanMessage(
                    content=(
                        f"触发类型：{snapshot.trigger.value}\n"
                        f"用户消息：{snapshot.user_message}\n"
                        f"助手回复：{snapshot.assistant_message}\n"
                        f"可用证据：\n{evidence}"
                    )
                ),
            ]
        )
        content = response.content
        if not isinstance(content, str):
            raise ValueError("Dreaming model must return text JSON")
        data = self._parse_json(content)
        raw_hypotheses = data.get("hypotheses")
        if not isinstance(raw_hypotheses, list):
            raise ValueError("Dreaming JSON must contain a hypotheses list")
        daily_review = self._parse_daily_review(data.get("daily_review"))
        raw_patches = data.get("patches", [])
        if not isinstance(raw_patches, list):
            raise ValueError("Dreaming patches must be a list")
        return DreamingAnalysis(
            hypotheses=tuple(self._parse_proposal(item) for item in raw_hypotheses),
            daily_review=daily_review,
            patches=tuple(self._parse_patch(item) for item in raw_patches),
        )

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                stripped = "\n".join(lines[1:-1])
                if stripped.lstrip().startswith("json"):
                    stripped = stripped.lstrip()[4:].lstrip()
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise ValueError("Dreaming response must be a JSON object")
        return parsed

    @staticmethod
    def _parse_proposal(value: object) -> HypothesisProposal:
        if not isinstance(value, dict):
            raise ValueError("Each Dreaming hypothesis must be an object")

        def string_tuple(field: str) -> tuple[str, ...]:
            raw = value.get(field, [])
            if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
                raise ValueError(f"Dreaming field {field} must be a string list")
            return tuple(raw)

        statement = value.get("statement")
        confidence = value.get("confidence_band")
        if not isinstance(statement, str) or not isinstance(confidence, str):
            raise ValueError("Dreaming statement and confidence_band must be strings")
        return HypothesisProposal(
            statement=statement,
            confidence_band=confidence,
            supporting_evidence_ids=string_tuple("supporting_evidence_ids"),
            contradicting_evidence_ids=string_tuple("contradicting_evidence_ids"),
            open_questions=string_tuple("open_questions"),
        )

    @staticmethod
    def _parse_daily_review(value: object) -> DailyReviewDraft | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("Dreaming daily_review must be an object or null")

        def strings(field: str) -> tuple[str, ...]:
            raw = value.get(field, [])
            if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
                raise ValueError(f"Dreaming daily_review field {field} must be a string list")
            return tuple(raw)

        local_date = value.get("local_date")
        tomorrow_step = value.get("tomorrow_step")
        if not isinstance(local_date, str) or not (
            tomorrow_step is None or isinstance(tomorrow_step, str)
        ):
            raise ValueError("Dreaming daily_review scalar fields are invalid")
        return DailyReviewDraft(
            local_date=local_date,
            wins=strings("wins"),
            ideas=strings("ideas"),
            blockers=strings("blockers"),
            open_loops=strings("open_loops"),
            tomorrow_step=tomorrow_step,
            source_event_ids=strings("source_event_ids"),
        )

    @staticmethod
    def _parse_patch(value: object) -> MemoryPatchProposal:
        if not isinstance(value, dict):
            raise ValueError("Each Dreaming patch must be an object")
        operation = value.get("operation")
        target_type = value.get("target_type")
        content = value.get("content")
        evidence = value.get("supporting_evidence_ids", [])
        confirmation = value.get("requires_confirmation", True)
        if not all(isinstance(item, str) for item in (operation, target_type, content)):
            raise ValueError("Dreaming patch scalar fields must be strings")
        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
            raise ValueError("Dreaming patch evidence must be a string list")
        if not isinstance(confirmation, bool):
            raise ValueError("Dreaming patch requires_confirmation must be boolean")
        return MemoryPatchProposal(
            operation=operation,
            target_type=target_type,
            content=content,
            supporting_evidence_ids=tuple(evidence),
            requires_confirmation=confirmation,
        )
