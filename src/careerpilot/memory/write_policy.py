import re
from dataclasses import dataclass

from careerpilot.memory.models import MemorySensitivity, MemoryType


@dataclass(frozen=True, slots=True)
class MemoryWriteCandidate:
    type: MemoryType
    content: str
    sensitivity: MemorySensitivity
    importance: int
    correction: bool = False


class MemoryWritePolicy:
    """Conservative gate for sending a turn to long-term memory extraction."""

    _durable_markers = (
        "记住",
        "以后我",
        "以后请",
        "我希望以后",
        "我长期",
        "我一直",
        "我更看重",
        "我正在探索",
        "我的工作地点",
        "我不能接受",
        "我的职业目标",
        "我的专业是",
        "我擅长",
        "我的专业",
        "我有",
        "我做过",
        "我决定",
        "我的想法是",
        "我在考虑",
        "我想尝试",
        "我想做",
        "更正一下",
        "不再",
    )

    _sensitive_markers = (
        "身份证",
        "护照号",
        "病史",
        "疾病",
        "诊断",
        "心理疾病",
    )

    _private_markers = ("薪资", "工资", "手机号", "电话", "家庭地址")

    _type_markers = (
        (MemoryType.IDEA, ("我的想法是", "我在考虑", "我想尝试", "我想做")),
        (MemoryType.CONSTRAINT, ("不能接受", "不接受", "必须", "底线")),
        (MemoryType.GOAL, ("职业目标", "我的目标", "我正在探索", "想成为")),
        (MemoryType.DECISION, ("我决定", "已经决定")),
        (MemoryType.EXPERIENCE, ("我做过", "我曾经", "我有过")),
        (MemoryType.PREFERENCE, ("偏好", "喜欢", "更看重", "我希望以后", "以后我")),
    )

    _correction_markers = ("更正一下", "不再", "现在改为", "以前", "之前说错了")

    def should_write(self, user_message: str) -> bool:
        return any(marker in user_message for marker in self._durable_markers)

    def extract(self, user_message: str) -> tuple[MemoryWriteCandidate, ...]:
        """Extract conservative, user-authored durable statements.

        This deliberately does not infer hidden traits. Semantic extraction can be added
        later behind the same contract, while explicit statements remain deterministic.
        """

        if not self.should_write(user_message):
            return ()
        clauses = tuple(
            clause.strip(" ，,;；:：")
            for clause in re.split(r"[。！？!?\n]+", user_message)
            if self.should_write(clause)
        )
        candidates: list[MemoryWriteCandidate] = []
        for clause in clauses:
            content = re.sub(r"^记住\s*[:：]?\s*", "", clause).strip()
            if not content:
                continue
            memory_type = self._classify_type(content)
            sensitivity = self._classify_sensitivity(content)
            candidates.append(
                MemoryWriteCandidate(
                    type=memory_type,
                    content=content[:1000],
                    sensitivity=sensitivity,
                    importance=4 if clause.startswith("记住") else 3,
                    correction=any(marker in content for marker in self._correction_markers),
                )
            )
        return tuple(candidates[:4])

    def _classify_type(self, content: str) -> MemoryType:
        for memory_type, markers in self._type_markers:
            if any(marker in content for marker in markers):
                return memory_type
        return MemoryType.FACT

    def _classify_sensitivity(self, content: str) -> MemorySensitivity:
        if any(marker in content for marker in self._sensitive_markers):
            return MemorySensitivity.SENSITIVE
        if any(marker in content for marker in self._private_markers):
            return MemorySensitivity.PRIVATE
        return MemorySensitivity.NORMAL
