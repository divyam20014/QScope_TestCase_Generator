from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.client import GeminiClient
from app.ai.exceptions import AIProviderNotConfiguredError, AIProviderQuotaExceededError, AIProviderRequestError


class _FakeAPIError(Exception):
    def __init__(self, code: int, details: dict | None = None):
        super().__init__(f"{code} error")
        self.code = code
        self.details = details or {}


class _FakeErrorsModule:
    """Mimics google.genai.errors' exception hierarchy for tests."""

    class APIError(_FakeAPIError):
        pass

    class ClientError(APIError):
        pass

    class ServerError(APIError):
        pass


@pytest.fixture(autouse=True)
def fake_genai_errors(monkeypatch):
    import sys

    fake_google_genai = SimpleNamespace(errors=_FakeErrorsModule, types=SimpleNamespace(GenerateContentConfig=dict))
    monkeypatch.setitem(sys.modules, "google.genai", fake_google_genai)
    monkeypatch.setitem(sys.modules, "google.genai.errors", _FakeErrorsModule)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_google_genai.types)
    yield


def test_missing_api_key_raises_not_configured(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    # setenv to "" (not delenv) - delenv only removes the os.environ
    # override, and Settings still falls back to a real value in the
    # developer's own .env file if one exists; "" always wins since
    # pydantic-settings prefers os.environ over the .env file.
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()

    client = GeminiClient()
    with pytest.raises(AIProviderNotConfiguredError):
        client._sdk()


def test_call_with_retry_succeeds_first_try():
    client = GeminiClient()
    result = client._call_with_retry(lambda: "ok")
    assert result == "ok"


def test_call_with_retry_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    client = GeminiClient()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _FakeErrorsModule.ClientError(429)
        return "ok"

    result = client._call_with_retry(flaky)
    assert result == "ok"
    assert calls["n"] == 2


def test_call_with_retry_quota_exceeded_after_max_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    client = GeminiClient()

    def always_429():
        raise _FakeErrorsModule.ClientError(429)

    with pytest.raises(AIProviderQuotaExceededError):
        client._call_with_retry(always_429, max_retries=1)


def test_call_with_retry_non_quota_client_error_raises_immediately():
    client = GeminiClient()

    def bad_request():
        raise _FakeErrorsModule.ClientError(400)

    with pytest.raises(AIProviderRequestError) as exc_info:
        client._call_with_retry(bad_request)
    assert exc_info.value.status_code == 400


def test_call_with_retry_server_error_retries_then_raises(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    client = GeminiClient()
    calls = {"n": 0}

    def always_500():
        calls["n"] += 1
        raise _FakeErrorsModule.ServerError(500)

    with pytest.raises(AIProviderRequestError):
        client._call_with_retry(always_500, max_retries=2)
    assert calls["n"] == 3


def test_test_connection_returns_failure_on_not_configured(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()

    client = GeminiClient()
    success, latency_ms, error = client.test_connection("gemini-3.8-flash")
    assert success is False
    assert latency_ms is not None
    assert "GEMINI_API_KEY" in (error or "")


def test_generate_json_returns_parsed_and_usage(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    get_settings.cache_clear()

    fake_response = SimpleNamespace(
        parsed={"foo": "bar"},
        usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=5, total_token_count=15),
    )
    fake_models = SimpleNamespace(generate_content=lambda **kwargs: fake_response)
    fake_sdk_client = SimpleNamespace(models=fake_models)

    client = GeminiClient()
    client._sdk_client = fake_sdk_client

    class _Schema:
        pass

    parsed, usage = client.generate_json(model="gemini-3.8-flash", prompt="hi", response_schema=_Schema)
    assert parsed == {"foo": "bar"}
    assert usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    get_settings.cache_clear()
