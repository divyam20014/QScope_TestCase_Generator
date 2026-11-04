"""Works around a real limitation in the installed `google-genai` SDK
(2.34.0): when a Pydantic class is passed as `response_schema`, the SDK
builds Gemini's request-time JSON schema by calling `model_json_schema()`
directly and validating the raw result - it never resolves `$ref`/`$defs`
(see `google.genai._transformers.t_schema`). Any model with a *nested*
BaseModel field (e.g. a batch container holding `items: list[SomeModel]` -
exactly the shape every structured-output schema in this app uses) produces
a schema with `$defs`/`$ref`, which crashes with a pydantic
`ValidationError` deep inside the SDK before any network call is made.
Confirmed against the real installed SDK, not assumed.

`GeminiSchemaModel` overrides `model_json_schema()` to inline every `$ref`
so the SDK always sees a fully flat schema. This only affects schema
*generation* for the request - `.parsed` still validates the real response
JSON against the real (unmodified) Pydantic class, since the SDK does that
separately via `model_validate_json`, not via `model_json_schema()`.
"""

from __future__ import annotations

import copy
from typing import Any

from pydantic import BaseModel


def _inline_refs(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            return _inline_refs(copy.deepcopy(defs[name]), defs)
        return {key: _inline_refs(value, defs) for key, value in node.items() if key != "$defs"}
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    return node


def _simplify_nullable(node: Any) -> Any:
    """Pydantic represents `X | None` as `anyOf: [{...X}, {type: "null"}]`.
    Gemini's schema has no "null" type at all - nullability is a separate
    `nullable: true` flag alongside the real type. Collapse the two-branch
    anyOf form into that shape; anything else passes through unchanged."""
    if isinstance(node, dict):
        if "anyOf" in node and isinstance(node["anyOf"], list):
            options = node["anyOf"]
            non_null = [o for o in options if o.get("type") != "null"]
            if len(non_null) == 1 and len(non_null) < len(options):
                merged = {k: _simplify_nullable(v) for k, v in node.items() if k != "anyOf"}
                merged.update(_simplify_nullable(non_null[0]))
                merged["nullable"] = True
                return merged
        return {key: _simplify_nullable(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_simplify_nullable(item) for item in node]
    return node


class GeminiSchemaModel(BaseModel):
    """Base for any Pydantic model passed directly as a Gemini `response_schema`."""

    @classmethod
    def model_json_schema(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        schema = super().model_json_schema(*args, **kwargs)
        defs = schema.pop("$defs", {})
        return _simplify_nullable(_inline_refs(schema, defs))
