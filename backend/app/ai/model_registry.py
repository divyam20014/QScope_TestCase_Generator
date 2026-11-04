"""Centralized AI model registry across all supported providers.

No model name may be hardcoded anywhere in `app/requirements`, `app/generator`,
or `app/validators` - those modules call through `app.ai.service`, which
resolves model ids from here (or from the user-selected `AIConfig`) and uses
each model's tagged `provider` to pick the right client. Adding a new model
or provider means editing this list (and, for a new provider, adding its
client under `app/ai/`) only.
"""

from __future__ import annotations

from app.ai.models import ModelCapability
from app.core.config import get_settings

_MODELS: list[ModelCapability] = [
    ModelCapability(
        model_id="gemini-3.8-flash",
        provider="gemini",
        display_name="Gemini 3.8 Flash",
        description=(
            "Fast, free-tier-friendly model. Confirmed live against a real API key and a real "
            "generation call (the 2.0/1.5-generation ids previously here were retired by Google - "
            "a live call returned '404 NOT_FOUND ... use models/gemini-3.8-flash' and this registry "
            "was updated to match)."
        ),
        context_window_tokens=1_000_000,
    ),
    ModelCapability(
        model_id="gpt-5-mini",
        provider="openai",
        display_name="GPT-5 Mini",
        description=(
            "OpenAI's smaller, lower-cost model via the Responses API. Not yet confirmed against a "
            "real API key in this environment - verify with Test Connection before relying on it, "
            "and correct the model id here if OpenAI has since renamed/retired it."
        ),
        context_window_tokens=400_000,
    ),
    ModelCapability(
        model_id="claude-haiku-5-5",
        provider="anthropic",
        display_name="Claude Haiku 5.5",
        description=(
            "Anthropic's fastest, lowest-cost current model via the Messages API structured-output "
            "mode. Not yet confirmed against a real API key in this environment - verify with Test "
            "Connection before relying on it."
        ),
        context_window_tokens=200_000,
    ),
    ModelCapability(
        model_id="llama3.2",
        provider="ollama",
        display_name="Llama 3.2 (local, via Ollama)",
        description=(
            "Free, fully open-source, runs entirely on your own machine via Ollama - no API key, no "
            "per-token cost, no external rate limits. Requires installing Ollama "
            "(https://ollama.com) and running `ollama pull llama3.2` first. Not yet confirmed live in "
            "this environment (no Ollama server was running here) - verify with Test Connection."
        ),
        context_window_tokens=128_000,
    ),
    ModelCapability(
        model_id="qwen2.5",
        provider="ollama",
        display_name="Qwen 2.5 (local, via Ollama)",
        description=(
            "Another free, open-source local option via Ollama - good at structured/JSON output. "
            "Requires `ollama pull qwen2.5` first. Not yet confirmed live in this environment."
        ),
        context_window_tokens=128_000,
    ),
]


def list_models() -> list[ModelCapability]:
    default_id = default_model_id()
    return [m.model_copy(update={"is_default": m.model_id == default_id}) for m in _MODELS]


def is_known_model(model_id: str) -> bool:
    return any(m.model_id == model_id for m in _MODELS)


def get_provider(model_id: str) -> str | None:
    return next((m.provider for m in _MODELS if m.model_id == model_id), None)


def default_model_id() -> str:
    return get_settings().gemini_default_model
