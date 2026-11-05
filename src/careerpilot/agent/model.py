from langchain_openai import ChatOpenAI

from careerpilot.config import Settings


def _create_model(
    settings: Settings, *, temperature: float, timeout_seconds: float = 60.0
) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.model_name,
        base_url=settings.model_base_url,
        api_key=settings.model_api_key.get_secret_value(),
        temperature=temperature,
        timeout=timeout_seconds,
        max_retries=1,
    )


def create_exploration_model(settings: Settings) -> ChatOpenAI:
    """Create the creative/exploration model used for dialogue and query rewriting."""

    return _create_model(settings, temperature=settings.exploration_temperature)


def create_reasoning_model(settings: Settings) -> ChatOpenAI:
    """Create the deterministic model used for evidence planning and validation."""

    return _create_model(settings, temperature=settings.reasoning_temperature)


def create_dreaming_model(settings: Settings) -> ChatOpenAI:
    """Create the deterministic model with a deadline suited to evidence synthesis."""

    return _create_model(
        settings,
        temperature=settings.reasoning_temperature,
        timeout_seconds=settings.dreaming_model_timeout_seconds,
    )


def create_qwen_model(settings: Settings) -> ChatOpenAI:
    """Backward-compatible alias for the exploration model."""

    return create_exploration_model(settings)
