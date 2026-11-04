from __future__ import annotations

from types import SimpleNamespace

import ollama
import pytest

from app.ai.exceptions import AIProviderNotConfiguredError, AIProviderQuotaExceededError, AIProviderRequestError
from app.ai.ollama_client import OllamaClient


def test_unreachable_server_raises_not_configured(monkeypatch):
    client = OllamaClient()

    def unreachable():
        raise ConnectionError("Could not connect to Ollama")

    with pytest.raises(AIProviderNotConfiguredError) as exc_info:
        client._call_with_retry(unreachable)
    assert "localhost:11434" in str(exc_info.value)


def test_call_with_retry_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    client = OllamaClient()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ollama.ResponseError("rate limited", 429)
        return "ok"

    assert client._call_with_retry(flaky) == "ok"
    assert calls["n"] == 2


def test_call_with_retry_quota_exceeded_after_max_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    client = OllamaClient()

    def always_429():
        raise ollama.ResponseError("rate limited", 429)

    with pytest.raises(AIProviderQuotaExceededError):
        client._call_with_retry(always_429, max_retries=1)


def test_call_with_retry_non_retryable_client_error_raises_immediately():
    client = OllamaClient()

    def model_not_found():
        raise ollama.ResponseError("model not found", 404)

    with pytest.raises(AIProviderRequestError) as exc_info:
        client._call_with_retry(model_not_found)
    assert exc_info.value.status_code == 404


def test_call_with_retry_server_error_retries_then_raises(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    client = OllamaClient()
    calls = {"n": 0}

    def always_500():
        calls["n"] += 1
        raise ollama.ResponseError("internal error", 500)

    with pytest.raises(AIProviderRequestError):
        client._call_with_retry(always_500, max_retries=2)
    assert calls["n"] == 3


def test_test_connection_returns_failure_when_unreachable():
    client = OllamaClient()
    client._sdk_client = SimpleNamespace(chat=lambda **kwargs: (_ for _ in ()).throw(ConnectionError("down")))
    success, latency_ms, error = client.test_connection("llama3.2")
    assert success is False
    assert latency_ms is not None
    assert "ollama.com" in (error or "")


def test_generate_json_returns_parsed_and_usage():
    fake_response = SimpleNamespace(
        message=SimpleNamespace(content='{"foo": "bar"}'),
        prompt_eval_count=10,
        eval_count=5,
    )
    fake_sdk_client = SimpleNamespace(chat=lambda **kwargs: fake_response)

    client = OllamaClient()
    client._sdk_client = fake_sdk_client

    from pydantic import BaseModel

    class _Schema(BaseModel):
        foo: str

    parsed, usage = client.generate_json(model="llama3.2", prompt="hi", response_schema=_Schema)
    assert parsed.foo == "bar"
    assert usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
