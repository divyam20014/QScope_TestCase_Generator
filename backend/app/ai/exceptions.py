from __future__ import annotations


class AIProviderError(Exception):
    """Base class for all AI-provider failures, regardless of which provider
    (Gemini, OpenAI, Anthropic) raised it."""


class AIProviderNotConfiguredError(AIProviderError):
    """The active provider's API key is not set in the environment/.env."""


class AIProviderQuotaExceededError(AIProviderError):
    """Rate limit/quota (HTTP 429) exceeded after exhausting retries."""

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class AIProviderRequestError(AIProviderError):
    """Any other non-recoverable error from the active provider's API."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
