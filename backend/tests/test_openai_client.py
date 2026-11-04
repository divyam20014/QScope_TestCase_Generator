from __future__ import annotations

from types import SimpleNamespace

import httpx2
import openai
import pytest

from app.ai.exceptions import AIProviderNotConfiguredError, AIProviderQuotaExceededError, AIProviderRequestError
from app.ai.openai_client import OpenAIClient


def _rate_limit_error(retry_after: str | None = None) -> openai.RateLimitError:
    req = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    headers = {"retry-after": retry_after} if retry_after else {}
    resp = httpx2.Response(429, request=req, headers=headers)
    return openai.RateLimitError("rate limited", response=resp, body=None)


def _status_error(status_code: int) -> openai.APIStatusError:
    req = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    resp = httpx2.Response(status_code, request=req, headers={})
    return openai.APIStatusError(f"{status_code} error", response=resp, body=None)


def test_missing_api_key_raises_not_configured(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    client = OpenAIClient()
    with pytest.raises(AIProviderNotConfiguredError):
        client._sdk()

    get_settings.cache_clear()


def test_call_with_retry_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    client = OpenAIClient()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _rate_limit_error(retry_after="1")
        return "ok"

    assert client._call_with_retry(flaky) == "ok"
    assert calls["n"] == 2


def test_call_with_retry_quota_exceeded_after_max_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    client = OpenAIClient()

    def always_429():
        raise _rate_limit_error()

    with pytest.raises(AIProviderQuotaExceededError):
        client._call_with_retry(always_429, max_retries=1)


def test_call_with_retry_non_retryable_client_error_raises_immediately():
    client = OpenAIClient()

    def bad_request():
        raise _status_error(400)

    with pytest.raises(AIProviderRequestError) as exc_info:
        client._call_with_retry(bad_request)
    assert exc_info.value.status_code == 400


def test_call_with_retry_server_error_retries_then_raises(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    client = OpenAIClient()
    calls = {"n": 0}

    def always_500():
        calls["n"] += 1
        raise _status_error(500)

    with pytest.raises(AIProviderRequestError):
        client._call_with_retry(always_500, max_retries=2)
    assert calls["n"] == 3


def test_test_connection_returns_failure_on_not_configured(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    client = OpenAIClient()
    success, latency_ms, error = client.test_connection("gpt-5-mini")
    assert success is False
    assert latency_ms is not None
    assert "OPENAI_API_KEY" in (error or "")

    get_settings.cache_clear()


def test_generate_json_returns_parsed_and_usage(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    get_settings.cache_clear()

    fake_response = SimpleNamespace(
        output_parsed={"foo": "bar"},
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15),
    )
    fake_responses_api = SimpleNamespace(parse=lambda **kwargs: fake_response)
    fake_sdk_client = SimpleNamespace(responses=fake_responses_api)

    client = OpenAIClient()
    client._sdk_client = fake_sdk_client

    class _Schema:
        pass

    parsed, usage = client.generate_json(model="gpt-5-mini", prompt="hi", response_schema=_Schema)
    assert parsed == {"foo": "bar"}
    assert usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    get_settings.cache_clear()
