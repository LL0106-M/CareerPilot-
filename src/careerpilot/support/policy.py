from dataclasses import dataclass
from enum import StrEnum


class SupportMode(StrEnum):
    LISTEN = "listen"
    ORGANIZE = "organize"
    EXPLORE = "explore"
    ACT = "act"


@dataclass(frozen=True, slots=True)
class SupportDecision:
    mode: SupportMode
    distress_detected: bool
    action_tools_allowed: bool


class SupportPolicy:
    """Resolve the current user-controlled support mode.

    This is intentionally conservative: availability of an action never upgrades a turn to
    action mode. Only an explicit mode or an explicit action request can do that.
    """

    _distress_markers = ("焦虑", "难受", "崩溃", "害怕", "自责", "绝望", "压力", "被拒")
    _listen_markers = ("只想说说", "听我说", "不要建议", "不想听建议", "先别安排")
    _action_markers = (
        "帮我创建",
        "帮我安排",
        "帮我设置",
        "提醒我",
        "加入日历",
        "替我执行",
    )
    _organize_markers = ("梳理", "整理", "总结一下", "理清")
    _explore_markers = ("适合什么", "更适合", "很纠结", "怎么选择", "职业方向", "想看看")

    def decide(
        self,
        message: str,
        requested_mode: SupportMode | None = None,
    ) -> SupportDecision:
        distress_detected = self._contains_any(message, self._distress_markers)
        mode = requested_mode or self._infer_mode(message)
        return SupportDecision(
            mode=mode,
            distress_detected=distress_detected,
            action_tools_allowed=mode is SupportMode.ACT,
        )

    def _infer_mode(self, message: str) -> SupportMode:
        if self._contains_any(message, self._listen_markers):
            return SupportMode.LISTEN
        if self._contains_any(message, self._action_markers):
            return SupportMode.ACT
        if self._contains_any(message, self._organize_markers):
            return SupportMode.ORGANIZE
        if self._contains_any(message, self._explore_markers):
            return SupportMode.EXPLORE
        if self._contains_any(message, self._distress_markers):
            return SupportMode.LISTEN
        return SupportMode.ORGANIZE

    @staticmethod
    def _contains_any(message: str, markers: tuple[str, ...]) -> bool:
        return any(marker in message for marker in markers)

