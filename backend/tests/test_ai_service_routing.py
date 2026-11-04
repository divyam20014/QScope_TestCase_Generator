from __future__ import annotations

import pytest

from app.ai import service as ai_service
from app.ai.anthropic_client import AnthropicClient
from app.ai.client import GeminiClient
from app.ai.ollama_client import OllamaClient
from app.ai.openai_client import OpenAIClient


def test_get_client_for_model_routes_by_provider():
    ai_service.reset_client()
    assert isinstance(ai_service.get_client_for_model("gemini-3.8-flash"), GeminiClient)
    assert isinstance(ai_service.get_client_for_model("gpt-5-mini"), OpenAIClient)
    assert isinstance(ai_service.get_client_for_model("claude-haiku-5-5"), AnthropicClient)
    assert isinstance(ai_service.get_client_for_model("llama3.2"), OllamaClient)
    ai_service.reset_client()


def test_get_client_for_model_caches_one_instance_per_provider():
    ai_service.reset_client()
    first = ai_service.get_client_for_model("gemini-3.8-flash")
    second = ai_service.get_client_for_model("gemini-3.8-flash")
    assert first is second
    ai_service.reset_client()


def test_get_client_for_model_unknown_model_raises():
    with pytest.raises(ValueError):
        ai_service.get_client_for_model("not-a-real-model")


def test_list_models_includes_all_providers():
    models = ai_service.list_models()
    providers = {m.provider for m in models}
    assert providers == {"gemini", "openai", "anthropic", "ollama"}
