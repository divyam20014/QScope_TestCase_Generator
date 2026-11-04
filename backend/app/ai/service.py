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
from app.ai.exceptions import AIProviderError
from app.ai.models import AIConfig, AIConfigUpdate, ConnectionTestResult, ModelCapability, UsageRecord, UsageStats
from app.ai.provider import AIProvider
from app.core.models import utcnow
from app.core.paths import ai_config_file, ai_usage_file
from app.storage.json_store import read_json, write_json

T = TypeVar("T", bound=BaseModel)

# generate_json tries every model in this many in-provider retries before
# moving on to the next candidate model - kept at 0 so a struggling model
# (quota exhausted, 503 overload, not configured) is abandoned immediately
# rather than burning its own multi-minute backoff schedule first. Cross-
# model failover *is* the resilience mechanism here, not in-model retry.
FAILOVER_MAX_RETRIES_PER_MODEL = 0

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
    if provider == "ollama":
        from app.ai.ollama_client import OllamaClient

        return OllamaClient()
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


def _candidate_models(preferred: str) -> list[str]:
    """Preferred model first, then every other registered model in registry
    order - so a quota/overload/not-configured failure on one never stops
    execution outright, it just moves on to the next available model."""
    all_models = [m.model_id for m in model_registry.list_models()]
    rest = [m for m in all_models if m != preferred]
    return [preferred, *rest]


def generate_json(
    *,
    prompt: str,
    response_schema: type[T],
    model: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
) -> T:
    """Tries the preferred model first, then automatically fails over to
    every other registered model (any provider) in turn if it's
    unconfigured, over quota, or overloaded - only raising once every
    candidate has failed. Whichever model actually serves the request is
    what gets credited in usage tracking. If every candidate fails, the
    *preferred* model's own error is raised (not whichever fallback
    happened to be tried last) - it's the one most relevant to what the
    caller/user actually selected."""
    config = get_config()
    preferred_model = model or config.selected_model

    preferred_exc: AIProviderError | ValueError | None = None
    last_exc: AIProviderError | ValueError | None = None
    for candidate_model in _candidate_models(preferred_model):
        try:
            client = get_client_for_model(candidate_model)
            parsed, usage = client.generate_json(
                model=candidate_model,
                prompt=prompt,
                response_schema=response_schema,
                temperature=temperature if temperature is not None else config.temperature,
                max_output_tokens=max_output_tokens if max_output_tokens is not None else config.max_output_tokens,
                max_retries=FAILOVER_MAX_RETRIES_PER_MODEL,
            )
        except (AIProviderError, ValueError) as exc:
            last_exc = exc
            if candidate_model == preferred_model:
                preferred_exc = exc
            continue
        record_usage(candidate_model, usage)
        return parsed

    raised = preferred_exc or last_exc
    assert raised is not None
    raise raised
