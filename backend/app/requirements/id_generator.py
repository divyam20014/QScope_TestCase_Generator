"""Stable requirement-id allocation.

If the source document already carries an explicit identifier next to a
requirement (e.g. "REQ-12:", "FR-3"), that id is preserved verbatim rather
than replaced with a generated one - matching how analysts already reference
these requirements elsewhere (traceability docs, bug reports). Only when no
such id exists (or it collides with one already taken) does this fall back
to a sequential, type-prefixed id.
"""

from __future__ import annotations

import re

from app.requirements.models import RequirementType

_TYPE_PREFIX: dict[RequirementType, str] = {
    RequirementType.FUNCTIONAL: "FR",
    RequirementType.BUSINESS: "BR",
    RequirementType.NON_FUNCTIONAL: "NFR",
    RequirementType.RULE: "RULE",
    RequirementType.VALIDATION: "VAL",
    RequirementType.WORKFLOW: "WF",
    RequirementType.ROLE: "ROLE",
    RequirementType.OTHER: "REQ",
}

_HINT_STRIP_RE = re.compile(r"[^A-Za-z0-9\-.]")


def normalize_hint(hint: str) -> str:
    return _HINT_STRIP_RE.sub("", hint.strip()).upper()


class RequirementIdAllocator:
    def __init__(self, existing_ids: set[str]) -> None:
        self._used: set[str] = set(existing_ids)

    def allocate(self, requirement_type: RequirementType, source_id_hint: str | None) -> str:
        if source_id_hint:
            candidate = normalize_hint(source_id_hint)
            if candidate and candidate not in self._used:
                self._used.add(candidate)
                return candidate
            # Hint present but already taken (duplicate id in the source, or
            # a collision with another document) - fall back to a generated
            # id; the hint itself is still kept on the requirement record.

        prefix = _TYPE_PREFIX[requirement_type]
        seq = self._scan_max_seq(prefix) + 1
        candidate = f"{prefix}-{seq:03d}"
        while candidate in self._used:
            seq += 1
            candidate = f"{prefix}-{seq:03d}"
        self._used.add(candidate)
        return candidate

    def _scan_max_seq(self, prefix: str) -> int:
        pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
        max_seq = 0
        for used in self._used:
            match = pattern.match(used)
            if match:
                max_seq = max(max_seq, int(match.group(1)))
        return max_seq
