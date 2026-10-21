from pathlib import Path

from careerpilot.support.policy import SupportMode


class SkillLoader:
    """Load the product-owned emotional-support Skill into runtime context."""

    def __init__(self, skill_path: Path) -> None:
        self._skill_path = skill_path

    @classmethod
    def repository_default(cls) -> "SkillLoader":
        repository_root = Path(__file__).resolve().parents[3]
        return cls(repository_root / "skills" / "career-emotional-support" / "SKILL.md")

    def runtime_context(self, mode: SupportMode) -> str:
        skill = self._skill_path.read_text(encoding="utf-8")
        mode_guard = (
            "禁止调用行动工具；不得创建任务、日历或外部写入。"
            if mode is SupportMode.LISTEN
            else "仅在用户明确要求且通过确认门后，才允许外部行动。"
        )
        return (
            "<career_emotional_support_skill>\n"
            f"用户当前模式：{mode.value}\n"
            f"运行时约束：{mode_guard}\n\n"
            f"{skill}\n"
            "</career_emotional_support_skill>"
        )
