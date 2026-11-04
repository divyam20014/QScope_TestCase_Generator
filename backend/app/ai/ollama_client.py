"""Thin wrapper over the official `ollama` SDK, talking to a locally-run
Ollama server (https://ollama.com) - free, fully open-source models (Llama,
Mistral, Gemma, Qwen, etc.), no API key, no per-token cost. Verified against
the actually-installed package version (0.6.3) by inspecting its real
signatures/exception classes directly, same rigor as every other client
here. There is no "API key" for this provider - `AIProviderNotConfiguredError`
is raised instead when the local Ollama server isn't reachable at all
(connection refused), which is the closest equivalent failure mode.
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
    from ollama import Client

    return Client(host=get_settings().ollama_host)


def _usage_from_response(response: Any) -> dict:
    prompt_tokens = getattr(response, "prompt_eval_count", 0) or 0
    completion_tokens = getattr(response, "eval_count", 0) or 0
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


class OllamaClient:
    def __init__(self) -> None:
        self._sdk_client = None

    def _sdk(self):
        if self._sdk_client is None:
            self._sdk_client = _build_sdk_client()
        return self._sdk_client

    def _call_with_retry(self, fn, *, max_retries: int = MAX_RETRIES):
        import ollama as ollama_module

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return fn()
            except ConnectionError as exc:
                host = get_settings().ollama_host
                raise AIProviderNotConfiguredError(
                    f"Ollama isn't reachable at {host} - install it from https://ollama.com, run "
                    f"`ollama serve`, and `ollama pull <model>` for the model you selected."
                ) from exc
            except ollama_module.ResponseError as exc:
                if exc.status_code == 429:
                    if attempt >= max_retries:
                        raise AIProviderQuotaExceededError(str(exc)) from exc
                    time.sleep(BASE_BACKOFF_SECONDS * (2**attempt))
                    last_exc = exc
                    continue
                if exc.status_code >= 500 and attempt < max_retries:
                    time.sleep(BASE_BACKOFF_SECONDS * (2**attempt))
                    last_exc = exc
                    continue
                raise AIProviderRequestError(str(exc), status_code=exc.status_code) from exc
        raise AIProviderRequestError(str(last_exc) if last_exc else "Ollama request failed after retries")

    def test_connection(self, model: str) -> tuple[bool, int, str | None]:
        start = time.monotonic()
        try:
            self._call_with_retry(
                lambda: self._sdk().chat(model=model, messages=[{"role": "user", "content": "Reply with the single word: OK"}]),
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
        max_retries: int = MAX_RETRIES,
    ) -> tuple[T, dict]:
        def _call():
            return self._sdk().chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                format=response_schema.model_json_schema(),
                options={"temperature": temperature, "num_predict": max_output_tokens},
            )

        response = self._call_with_retry(_call, max_retries=max_retries)
        content = getattr(response.message, "content", None)
        if not content:
            raise AIProviderRequestError("Ollama returned no content")
        parsed = response_schema.model_validate_json(content)
        return parsed, _usage_from_response(response)
