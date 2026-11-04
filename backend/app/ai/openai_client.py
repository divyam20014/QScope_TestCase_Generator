"""Thin wrapper over the official `openai` SDK's Responses API
(`client.responses.parse`), verified against the actually-installed
package version (3.45.0) by inspecting its real signatures/types directly -
not assumed from memory, same rigor as `app/ai/client.py`'s Gemini fix.
Unlike Gemini's SDK, OpenAI's `.parse()` helper builds and resolves the
request schema (including nested models) itself, so no schema-flattening
wrapper is needed here."""

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
    from openai import OpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        raise AIProviderNotConfiguredError("OPENAI_API_KEY is not set - add it to .env")
    return OpenAI(api_key=settings.openai_api_key)


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
    return {
        "prompt_tokens": getattr(usage, "input_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "output_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }


class OpenAIClient:
    def __init__(self) -> None:
        self._sdk_client = None

    def _sdk(self):
        if self._sdk_client is None:
            self._sdk_client = _build_sdk_client()
        return self._sdk_client

    def _call_with_retry(self, fn, *, max_retries: int = MAX_RETRIES):
        import openai as openai_module

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return fn()
            except openai_module.RateLimitError as exc:
                if attempt >= max_retries:
                    raise AIProviderQuotaExceededError(str(exc), retry_after_seconds=_retry_after_seconds(exc)) from exc
                retry_after = _retry_after_seconds(exc)
                time.sleep(retry_after if retry_after is not None else BASE_BACKOFF_SECONDS * (2**attempt))
                last_exc = exc
                continue
            except openai_module.APIStatusError as exc:
                if exc.status_code >= 500 and attempt < max_retries:
                    time.sleep(BASE_BACKOFF_SECONDS * (2**attempt))
                    last_exc = exc
                    continue
                raise AIProviderRequestError(str(exc), status_code=exc.status_code) from exc
            except openai_module.APIError as exc:
                raise AIProviderRequestError(str(exc)) from exc
        raise AIProviderRequestError(str(last_exc) if last_exc else "OpenAI request failed after retries")

    def test_connection(self, model: str) -> tuple[bool, int, str | None]:
        start = time.monotonic()
        try:
            self._call_with_retry(
                lambda: self._sdk().responses.create(model=model, input="Reply with the single word: OK"),
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
            return self._sdk().responses.parse(
                model=model,
                input=prompt,
                text_format=response_schema,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

        response = self._call_with_retry(_call)
        parsed = response.output_parsed
        if parsed is None:
            raise AIProviderRequestError("OpenAI returned no parsable structured output")
        return parsed, _usage_from_response(response)
