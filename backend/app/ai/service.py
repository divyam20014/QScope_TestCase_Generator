"""Glue between the AI provider clients, the model registry, and local
persistence.

No provider's API key is ever read or written here beyond checking whether
it's set - each lives in `.env` only, per ARCHITECTURE.md. `ai.json` stores
non-secret preferences (selected model, generation params); `ai_usage.json`
stores cumulative token usage per model. Routing to the correct provider
client happens here, based on each model's `provider` tag in
`app.ai.model_registry` - callers (`app/requirements`, `app/generator`,
`app/validators`) only ever call `generate_json`/`test_connection` on this
module, never a concrete client.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.ai import model_registry
from app.ai.models import AIConfig, AIConfigUpdate, ConnectionTestResult, ModelCapability, UsageRecord, UsageStats
from app.ai.provider import AIProvider
from app.core.models import utcnow
from app.core.paths import ai_config_file, ai_usage_file
from app.storage.json_store import read_json, write_json

T = TypeVar("T", bound=BaseModel)

_clients: dict[str, AIProvider] = {}


def _build_client(provider: str) -> AIProvider:
    if provider == "gemini":
        from app.ai.client import GeminiClient

        return GeminiClient()
    if provider == "openai":
        from app.ai.openai_client import OpenAIClient

        return OpenAIClient()
    if provider == "anthropic":
        from app.ai.anthropic_client import AnthropicClient

        return AnthropicClient()
    raise ValueError(f"Unknown AI provider '{provider}'")


def get_client_for_model(model_id: str) -> AIProvider:
    provider = model_registry.get_provider(model_id)
    if provider is None:
        raise ValueError(f"Unknown model '{model_id}'")
    if provider not in _clients:
        _clients[provider] = _build_client(provider)
    return _clients[provider]


def reset_client() -> None:
    """Drop all cached SDK clients - call after an API key changes (requires
    app restart in practice, since settings are cached, but kept for tests
    that monkeypatch settings)."""
    _clients.clear()


def list_models() -> list[ModelCapability]:
    return model_registry.list_models()


def get_config() -> AIConfig:
    data = read_json(ai_config_file(), default=None)
    if data is None:
        return AIConfig(selected_model=model_registry.default_model_id())
    return AIConfig.model_validate(data)


def update_config(update: AIConfigUpdate) -> AIConfig:
    current = get_config()
    changes = update.model_dump(exclude_unset=True, exclude_none=True)
    if "selected_model" in changes and not model_registry.is_known_model(changes["selected_model"]):
        raise ValueError(f"Unknown model '{changes['selected_model']}'")

    payload = current.model_dump()
    payload.update(changes)
    payload["updated_at"] = utcnow()
    config = AIConfig.model_validate(payload)
    write_json(ai_config_file(), config.model_dump(mode="json"))
    return config


def get_usage_stats() -> UsageStats:
    data = read_json(ai_usage_file(), default=None)
    if data is None:
        return UsageStats()
    return UsageStats.model_validate(data)


def record_usage(model: str, usage: dict) -> None:
    stats = get_usage_stats()
    record = stats.by_model.get(model) or UsageRecord(model=model)
    record.prompt_tokens += usage.get("prompt_tokens", 0)
    record.completion_tokens += usage.get("completion_tokens", 0)
    record.total_tokens += usage.get("total_tokens", 0)
    record.request_count += 1
    record.last_used_at = utcnow()
    stats.by_model[model] = record
    stats.total_requests += 1
    stats.total_tokens += usage.get("total_tokens", 0)
    write_json(ai_usage_file(), stats.model_dump(mode="json"))


def test_connection(model: str | None = None) -> ConnectionTestResult:
    target_model = model or get_config().selected_model
    success, latency_ms, error = get_client_for_model(target_model).test_connection(target_model)
    return ConnectionTestResult(success=success, model=target_model, latency_ms=latency_ms, error=error)


def generate_json(
    *,
    prompt: str,
    response_schema: type[T],
    model: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
) -> T:
    config = get_config()
    target_model = model or config.selected_model
    parsed, usage = get_client_for_model(target_model).generate_json(
        model=target_model,
        prompt=prompt,
        response_schema=response_schema,
        temperature=temperature if temperature is not None else config.temperature,
        max_output_tokens=max_output_tokens if max_output_tokens is not None else config.max_output_tokens,
    )
    record_usage(target_model, usage)
    return parsed
