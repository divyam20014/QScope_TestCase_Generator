"""The interface every AI provider client implements, per ARCHITECTURE.md
section 9 ("AI provider access goes through a single AIProvider interface").
`app.ai.service` resolves which concrete client to call based on the
provider tagged on the selected model in `app.ai.model_registry` - nothing
in `app/requirements`, `app/generator`, or `app/validators` ever imports a
concrete client directly.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AIProvider(Protocol):
    def test_connection(self, model: str) -> tuple[bool, int, str | None]:
        """Returns (success, latency_ms, error_message)."""
        ...

    def generate_json(
        self,
        *,
        model: str,
        prompt: str,
        response_schema: type[T],
        temperature: float,
        max_output_tokens: int,
    ) -> tuple[T, dict]:
        """Returns (parsed_response, usage_dict) where usage_dict has
        prompt_tokens/completion_tokens/total_tokens keys. Raises
        AIProviderNotConfiguredError / AIProviderQuotaExceededError /
        AIProviderRequestError on failure - never a provider-SDK-specific
        exception type."""
        ...
