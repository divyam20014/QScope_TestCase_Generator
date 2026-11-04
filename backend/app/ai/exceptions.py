from __future__ import annotations


class GeminiError(Exception):
    """Base class for all Gemini-related failures."""


class GeminiNotConfiguredError(GeminiError):
    """No GEMINI_API_KEY is set in the environment/.env."""


class GeminiQuotaExceededError(GeminiError):
    """Rate limit/quota (HTTP 429) exceeded after exhausting retries."""

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class GeminiRequestError(GeminiError):
    """Any other non-recoverable Gemini API error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
