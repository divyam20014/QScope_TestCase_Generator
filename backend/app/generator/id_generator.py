from __future__ import annotations

import re


class SequentialIdAllocator:
    """Allocates sequential, prefixed, collision-free ids (e.g. TC-0007)
    within a project - used for generated test case and scenario ids, which
    (unlike requirement ids) never originate from source documents, so there
    is no hint to preserve."""

    def __init__(self, prefix: str, existing_ids: set[str]) -> None:
        self._prefix = prefix
        self._used: set[str] = set(existing_ids)
        self._pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")

    def allocate(self) -> str:
        seq = self._max_existing_seq() + 1
        candidate = f"{self._prefix}-{seq:04d}"
        while candidate in self._used:
            seq += 1
            candidate = f"{self._prefix}-{seq:04d}"
        self._used.add(candidate)
        return candidate

    def _max_existing_seq(self) -> int:
        max_seq = 0
        for used in self._used:
            match = self._pattern.match(used)
            if match:
                max_seq = max(max_seq, int(match.group(1)))
        return max_seq
