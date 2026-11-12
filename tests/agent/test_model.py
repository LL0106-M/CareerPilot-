from careerpilot.agent import model
from careerpilot.agent.model import create_exploration_model, create_reasoning_model
from careerpilot.config import Settings


def test_model_factories_use_separate_temperatures() -> None:
    settings = Settings(_env_file=None)

    exploration = create_exploration_model(settings)
    reasoning = create_reasoning_model(settings)

    assert exploration._temperature == 0.4
    assert reasoning._temperature == 0.0
    assert exploration is not reasoning
    assert exploration._model == "Qwen3-4B-GGUF"


def test_dreaming_model_allows_longer_evidence_analysis_without_slowing_chat(
    monkeypatch,
) -> None:
    client_options: list[dict] = []

    def fake_client(**kwargs):
        client_options.append(kwargs)
        return object()

    monkeypatch.setattr(model, "AsyncOpenAI", fake_client)
    settings = Settings(
        _env_file=None,
        CAREERPILOT_DREAMING_MODEL_TIMEOUT_SECONDS=180,
    )

    model.create_dreaming_model(settings)
    create_reasoning_model(settings)

    assert [item["timeout"] for item in client_options] == [180, 60.0]
    assert all(item["max_retries"] == 1 for item in client_options)


def test_structured_generator_factory_uses_sync_sdk_and_reasoning_settings(
    monkeypatch,
) -> None:
    client_options: list[dict] = []
    fake_client = object()

    def fake_openai(**kwargs):
        client_options.append(kwargs)
        return fake_client

    monkeypatch.setattr(model, "OpenAI", fake_openai)
    settings = Settings(_env_file=None)

    generator = model.create_structured_generator(settings)

    assert generator._client is fake_client
    assert generator._model == settings.model_name
    assert generator._temperature == settings.reasoning_temperature
    assert client_options == [
        {
            "api_key": settings.model_api_key.get_secret_value(),
            "base_url": settings.model_base_url,
            "timeout": 60.0,
            "max_retries": 1,
        }
    ]
