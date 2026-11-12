from openai import AsyncOpenAI, OpenAI

from careerpilot.config import Settings
from careerpilot.harness.contracts import ModelGateway
from careerpilot.harness.model import OpenAICompatibleModelGateway
from careerpilot.harness.structured import (
    OpenAICompatibleStructuredGenerator,
    StructuredGenerator,
)


def _create_model(
    settings: Settings, *, temperature: float, timeout_seconds: float = 60.0
) -> ModelGateway:
    client = AsyncOpenAI(
        api_key=settings.model_api_key.get_secret_value(),
        base_url=settings.model_base_url,
        timeout=timeout_seconds,
        max_retries=1,
    )
    return OpenAICompatibleModelGateway(
        client,
        model=settings.model_name,
        temperature=temperature,
    )


def create_exploration_model(settings: Settings) -> ModelGateway:
    """Create the creative/exploration model used for dialogue and query rewriting."""

    return _create_model(settings, temperature=settings.exploration_temperature)


def create_reasoning_model(settings: Settings) -> ModelGateway:
    """Create the deterministic model used for evidence planning and validation."""

    return _create_model(settings, temperature=settings.reasoning_temperature)


def create_dreaming_model(settings: Settings) -> ModelGateway:
    """Create the deterministic model with a deadline suited to evidence synthesis."""

    return _create_model(
        settings,
        temperature=settings.reasoning_temperature,
        timeout_seconds=settings.dreaming_model_timeout_seconds,
    )


def create_qwen_model(settings: Settings) -> ModelGateway:
    """Backward-compatible alias for the exploration model."""

    return create_exploration_model(settings)


def create_structured_generator(settings: Settings) -> StructuredGenerator:
    """Create the synchronous generator used by offline ingestion commands."""

    client = OpenAI(
        api_key=settings.model_api_key.get_secret_value(),
        base_url=settings.model_base_url,
        timeout=60.0,
        max_retries=1,
    )
    return OpenAICompatibleStructuredGenerator(
        client,
        model=settings.model_name,
        temperature=settings.reasoning_temperature,
    )
