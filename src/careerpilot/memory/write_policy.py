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
    )

    def should_write(self, user_message: str) -> bool:
        return any(marker in user_message for marker in self._durable_markers)
