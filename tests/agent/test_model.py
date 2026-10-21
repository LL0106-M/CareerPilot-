from careerpilot.agent.model import create_exploration_model, create_reasoning_model
from careerpilot.config import Settings


def test_model_factories_use_separate_temperatures() -> None:
    settings = Settings(_env_file=None)

    exploration = create_exploration_model(settings)
    reasoning = create_reasoning_model(settings)

    assert exploration.temperature == 0.4
    assert reasoning.temperature == 0.0
    assert exploration is not reasoning
