from careerpilot.agent import model
from careerpilot.agent.model import create_exploration_model, create_reasoning_model
from careerpilot.config import Settings


def test_model_factories_use_separate_temperatures() -> None:
    settings = Settings(_env_file=None)

    exploration = create_exploration_model(settings)
    reasoning = create_reasoning_model(settings)

    assert exploration.temperature == 0.4
    assert reasoning.temperature == 0.0
    assert exploration is not reasoning
    assert exploration.model_name == "Qwen3-4B-GGUF"


def test_dreaming_model_allows_longer_evidence_analysis_without_slowing_chat() -> None:
    settings = Settings(
        _env_file=None,
        CAREERPILOT_DREAMING_MODEL_TIMEOUT_SECONDS=180,
    )

    dreaming = model.create_dreaming_model(settings)
    reasoning = create_reasoning_model(settings)

    assert dreaming.request_timeout == 180
    assert reasoning.request_timeout == 60
