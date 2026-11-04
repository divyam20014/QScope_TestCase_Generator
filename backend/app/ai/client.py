"""Thin wrapper over the official `google-genai` SDK.

Centralizes: client construction from the configured API key, retry/backoff
on transient and rate-limit errors, structured-JSON generation, and usage
metadata extraction. No model name is hardcoded here - every call site
passes a model id resolved from `app.ai.model_registry` or the user's
`AIConfig`.
"""

from __future__ import annotations

import time
from typing import Any, TypeVar

from pydantic import BaseModel

from app.ai.exceptions import GeminiError, GeminiNotConfiguredError, GeminiQuotaExceededError, GeminiRequestError
from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)

MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 2.0


def _build_sdk_client():
    from google import genai

    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiNotConfiguredError("GEMINI_API_KEY is not set - add it to .env")
    return genai.Client(api_key=settings.gemini_api_key)


def _extract_retry_after(exc: Any) -> float | None:
    details = getattr(exc, "details", None)
    if not isinstance(details, dict):
        return None
    for item in details.get("error", {}).get("details", []) or []:
        if isinstance(item, dict) and str(item.get("@type", "")).endswith("RetryInfo"):
            delay = item.get("retryDelay", "")
            if isinstance(delay, str) and delay.endswith("s"):
                try:
                    return float(delay[:-1])
                except ValueError:
                    return None
    return None


def _usage_from_response(response: Any) -> dict:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": getattr(usage, "prompt_token_count", 0) or 0,
        "completion_tokens": getattr(usage, "candidates_token_count", 0) or 0,
        "total_tokens": getattr(usage, "total_token_count", 0) or 0,
    }


class GeminiClient:
    def __init__(self) -> None:
        self._sdk_client = None

    def _sdk(self):
        if self._sdk_client is None:
            self._sdk_client = _build_sdk_client()
        return self._sdk_client

    def _call_with_retry(self, fn, *, max_retries: int = MAX_RETRIES):
        from google.genai import errors as genai_errors

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return fn()
            except genai_errors.ClientError as exc:
                if exc.code == 429:
                    if attempt >= max_retries:
                        raise GeminiQuotaExceededError(str(exc), retry_after_seconds=_extract_retry_after(exc)) from exc
                    retry_after = _extract_retry_after(exc)
                    time.sleep(retry_after if retry_after is not None else BASE_BACKOFF_SECONDS * (2**attempt))
                    last_exc = exc
                    continue
                raise GeminiRequestError(str(exc), status_code=exc.code) from exc
            except genai_errors.ServerError as exc:
                if attempt >= max_retries:
                    raise GeminiRequestError(str(exc), status_code=exc.code) from exc
                time.sleep(BASE_BACKOFF_SECONDS * (2**attempt))
                last_exc = exc
                continue
            except genai_errors.APIError as exc:
                raise GeminiRequestError(str(exc), status_code=getattr(exc, "code", None)) from exc
        raise GeminiRequestError(str(last_exc) if last_exc else "Gemini request failed after retries")

    def test_connection(self, model: str) -> tuple[bool, int, str | None]:
        start = time.monotonic()
        try:
            self._call_with_retry(
                lambda: self._sdk().models.generate_content(model=model, contents="Reply with the single word: OK"),
                max_retries=0,
            )
            return True, int((time.monotonic() - start) * 1000), None
        except GeminiError as exc:
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
        from google.genai import types

        def _call():
            return self._sdk().models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                ),
            )

        response = self._call_with_retry(_call)
        parsed = getattr(response, "parsed", None)
        if parsed is None:
            raise GeminiRequestError("Gemini returned no parsable structured output")
        return parsed, _usage_from_response(response)
