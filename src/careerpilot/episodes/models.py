MEANINGFUL_EVENT_KINDS = frozenset(
    {
        "new_exploration",
        "user_correction",
        "experiment_result",
        "direction_shift",
        "unresolved_question",
    }
)

OPEN_LOOP_KINDS = frozenset(
    {"map_gap", "naming_gap", "evidence_gap", "constraint_conflict", "agent_commitment"}
)
