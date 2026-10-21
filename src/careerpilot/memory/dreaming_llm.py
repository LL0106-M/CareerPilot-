import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from careerpilot.memory.dreaming import DreamingSnapshot, HypothesisProposal


class JsonDreamingAnalyzer:
    """Generate evidence-bound candidate hypotheses with the deterministic model."""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    async def analyze(self, snapshot: DreamingSnapshot) -> tuple[HypothesisProposal, ...]:
        evidence = "\n".join(
            f"- id={item.id}; source={item.source}; content={item.content}"
            for item in snapshot.evidence
        )
        response = await self._model.ainvoke(
            [
                SystemMessage(
                    content=(
                        "你是职业成长记忆整理器。只提出待验证职业假设，不把推断写成事实。"
                        "每个假设必须引用给定 evidence id；证据不足时返回空 hypotheses。"
                        "只输出 JSON 对象，格式为 {\"hypotheses\": [{\"statement\": str, "
                        "\"confidence_band\": \"low|medium|high\", "
                        "\"supporting_evidence_ids\": [str], "
                        "\"contradicting_evidence_ids\": [str], "
                        "\"open_questions\": [str]}]}。"
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
        return tuple(self._parse_proposal(item) for item in raw_hypotheses)

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

