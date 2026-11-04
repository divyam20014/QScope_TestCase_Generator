"""Thin wrapper over the official `anthropic` SDK's Messages API
(`client.messages.parse`), verified against the actually-installed package
version (2.4.0) by inspecting its real signatures/types directly - not
assumed from memory. Like OpenAI's `.parse()`, Anthropic's handles request
schema construction (including nested models) itself, so no schema-
flattening wrapper is needed here. Note: `anthropic.types.usage.Usage` has
no `total_tokens` field (unlike Gemini/OpenAI) - it's computed here as
input + output tokens.
"""

from __future__ import annotations

import time
from typing import Any, TypeVar

from pydantic import BaseModel

from app.ai.exceptions import AIProviderError, AIProviderNotConfiguredError, AIProviderQuotaExceededError, AIProviderRequestError
from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)

MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 2.0


def _build_sdk_client():
    from anthropic import Anthropic

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise AIProviderNotConfiguredError("ANTHROPIC_API_KEY is not set - add it to .env")
    return Anthropic(api_key=settings.anthropic_api_key)


def _retry_after_seconds(exc: Any) -> float | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _usage_from_response(response: Any) -> dict:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    prompt_tokens = getattr(usage, "input_tokens", 0) or 0
    completion_tokens = getattr(usage, "output_tokens", 0) or 0
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


class AnthropicClient:
    def __init__(self) -> None:
        self._sdk_client = None

    def _sdk(self):
        if self._sdk_client is None:
            self._sdk_client = _build_sdk_client()
        return self._sdk_client

    def _call_with_retry(self, fn, *, max_retries: int = MAX_RETRIES):
        import anthropic as anthropic_module

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return fn()
            except anthropic_module.RateLimitError as exc:
                if attempt >= max_retries:
                    raise AIProviderQuotaExceededError(str(exc), retry_after_seconds=_retry_after_seconds(exc)) from exc
                retry_after = _retry_after_seconds(exc)
                time.sleep(retry_after if retry_after is not None else BASE_BACKOFF_SECONDS * (2**attempt))
                last_exc = exc
                continue
            except anthropic_module.APIStatusError as exc:
                if exc.status_code >= 500 and attempt < max_retries:
                    time.sleep(BASE_BACKOFF_SECONDS * (2**attempt))
                    last_exc = exc
                    continue
                raise AIProviderRequestError(str(exc), status_code=exc.status_code) from exc
            except anthropic_module.APIError as exc:
                raise AIProviderRequestError(str(exc)) from exc
        raise AIProviderRequestError(str(last_exc) if last_exc else "Anthropic request failed after retries")

    def test_connection(self, model: str) -> tuple[bool, int, str | None]:
        start = time.monotonic()
        try:
            self._call_with_retry(
                lambda: self._sdk().messages.create(
                    model=model,
                    max_tokens=16,
                    messages=[{"role": "user", "content": "Reply with the single word: OK"}],
                ),
                max_retries=0,
            )
            return True, int((time.monotonic() - start) * 1000), None
        except AIProviderError as exc:
            return False, int((time.monotonic() - start) * 1000), str(exc)

    def generate_json(
        self,
        *,
        model: str,
        prompt: str,
        response_schema: type[T],
        temperature: float = 0.2,
        max_output_tokens: int = 8192,
    ) -> tuple[T, dict]:
        def _call():
            return self._sdk().messages.parse(
                model=model,
                max_tokens=max_output_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
                output_format=response_schema,
            )

        response = self._call_with_retry(_call)
        parsed = response.parsed_output
        if parsed is None:
            raise AIProviderRequestError("Anthropic returned no parsable structured output")
        return parsed, _usage_from_response(response)
