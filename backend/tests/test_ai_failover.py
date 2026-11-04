from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai import service as ai_service
from app.ai.exceptions import AIProviderNotConfiguredError, AIProviderQuotaExceededError, AIProviderRequestError


class _FakeSchema:
    pass


def _fake_client(behavior):
    """behavior(**kwargs) either returns (parsed, usage) or raises."""
    return SimpleNamespace(generate_json=behavior, test_connection=lambda model: (True, 1, None))


def test_candidate_models_puts_preferred_first_then_the_rest():
    candidates = ai_service._candidate_models("gpt-5-mini")
    assert candidates[0] == "gpt-5-mini"
    assert set(candidates) == {m.model_id for m in ai_service.list_models()}
    assert len(candidates) == len(set(candidates))


def test_generate_json_falls_back_to_next_model_on_quota_exceeded(client, monkeypatch):
    # `client` is unused directly but its fixture isolates LOCAL_DATA_DIR to
    # a temp dir, so this test's usage-tracking writes never touch the
    # repo's real local_data/.
    ai_service.reset_client()
    calls = []

    def gemini_behavior(**kwargs):
        calls.append(("gemini-3.8-flash", kwargs["max_retries"]))
        raise AIProviderQuotaExceededError("over quota")

    def openai_behavior(**kwargs):
        calls.append(("gpt-5-mini", kwargs["max_retries"]))
        return {"ok": True}, {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}

    monkeypatch.setattr(
        ai_service,
        "get_client_for_model",
        lambda model_id: {
            "gemini-3.8-flash": _fake_client(gemini_behavior),
            "gpt-5-mini": _fake_client(openai_behavior),
        }[model_id],
    )

    result = ai_service.generate_json(prompt="hi", response_schema=_FakeSchema, model="gemini-3.8-flash")
    assert result == {"ok": True}
    assert calls[0] == ("gemini-3.8-flash", ai_service.FAILOVER_MAX_RETRIES_PER_MODEL)
    assert calls[1] == ("gpt-5-mini", ai_service.FAILOVER_MAX_RETRIES_PER_MODEL)

    usage = ai_service.get_usage_stats()
    assert "gpt-5-mini" in usage.by_model
    assert "gemini-3.8-flash" not in usage.by_model  # the failed model is never credited

    ai_service.reset_client()


def test_generate_json_falls_back_past_not_configured_models(client, monkeypatch):
    ai_service.reset_client()

    def not_configured(**kwargs):
        raise AIProviderNotConfiguredError("no key")

    def overloaded(**kwargs):
        raise AIProviderRequestError("503 overloaded")

    def succeeds(**kwargs):
        return {"ok": True}, {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}

    monkeypatch.setattr(
        ai_service,
        "get_client_for_model",
        lambda model_id: {
            "gemini-3.8-flash": _fake_client(overloaded),
            "gpt-5-mini": _fake_client(not_configured),
            "claude-haiku-5-5": _fake_client(not_configured),
            "llama3.2": _fake_client(succeeds),
            "qwen2.5": _fake_client(not_configured),
        }[model_id],
    )

    result = ai_service.generate_json(prompt="hi", response_schema=_FakeSchema, model="gemini-3.8-flash")
    assert result == {"ok": True}

    ai_service.reset_client()


def test_generate_json_raises_only_when_every_model_fails(client, monkeypatch):
    ai_service.reset_client()

    def always_fails(**kwargs):
        raise AIProviderRequestError("down")

    monkeypatch.setattr(ai_service, "get_client_for_model", lambda model_id: _fake_client(always_fails))

    with pytest.raises(AIProviderRequestError):
        ai_service.generate_json(prompt="hi", response_schema=_FakeSchema, model="gemini-3.8-flash")

    ai_service.reset_client()
