"""Centralized Gemini model registry.

No model name may be hardcoded anywhere in `app/requirements`, `app/generator`,
or `app/validators` - those modules call through `app.ai.service`, which
resolves model ids from here (or from the user-selected `AIConfig`). Adding a
new Gemini model means editing this list only.
"""

from __future__ import annotations

from app.ai.models import ModelCapability
from app.core.config import get_settings

_MODELS: list[ModelCapability] = [
    ModelCapability(
        model_id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        description="Fast, low-cost, generous free-tier quota. Recommended default for test-case generation.",
        context_window_tokens=1_000_000,
    ),
    ModelCapability(
        model_id="gemini-2.0-flash-lite",
        display_name="Gemini 2.0 Flash-Lite",
        description="Lower latency/cost variant of 2.0 Flash, reduced reasoning depth.",
        context_window_tokens=1_000_000,
    ),
    ModelCapability(
        model_id="gemini-1.5-flash",
        display_name="Gemini 1.5 Flash",
        description="Previous-generation fast model, kept for compatibility.",
        context_window_tokens=1_000_000,
    ),
    ModelCapability(
        model_id="gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        description="Higher-quality reasoning, smaller free-tier quota - use for complex requirement sets.",
        context_window_tokens=2_000_000,
    ),
]


def list_models() -> list[ModelCapability]:
    default_id = default_model_id()
    return [m.model_copy(update={"is_default": m.model_id == default_id}) for m in _MODELS]


def is_known_model(model_id: str) -> bool:
    return any(m.model_id == model_id for m in _MODELS)


def default_model_id() -> str:
    return get_settings().gemini_default_model
