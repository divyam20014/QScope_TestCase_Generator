"""Duplicate detection across generated test cases - escalating from exact
text match to normalized (case/punctuation/whitespace-insensitive) match to
semantic (embedding similarity) match. Every tier only looks at test cases
not already caught by a stronger, cheaper tier, so a given test case is
never reported in two groups. This only reports groups - nothing here
deletes or merges a test case; that decision is left to a human (Phase 8's
repository), per the brief ("duplicates flagged, not auto-deleted")."""

from __future__ import annotations

import re
from collections import defaultdict

from app.generator.models import TestCase
from app.validators.models import DuplicateGroup

SEMANTIC_SIMILARITY_THRESHOLD = 0.92
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def _test_case_text(test_case: TestCase) -> str:
    return " ".join([test_case.title, test_case.scenario_description, " ".join(test_case.steps), test_case.expected_result])


def _normalize(text: str) -> str:
    text = _NON_ALNUM_RE.sub("", text.lower())
    return _WHITESPACE_RE.sub(" ", text).strip()


def find_exact_duplicates(test_cases: list[TestCase]) -> list[DuplicateGroup]:
    groups: dict[str, list[str]] = defaultdict(list)
    for test_case in test_cases:
        groups[_test_case_text(test_case)].append(test_case.id)
    return [DuplicateGroup(method="exact", test_case_ids=ids) for ids in groups.values() if len(ids) > 1]


def find_normalized_duplicates(test_cases: list[TestCase], exclude_ids: set[str]) -> list[DuplicateGroup]:
    groups: dict[str, list[str]] = defaultdict(list)
    for test_case in test_cases:
        if test_case.id in exclude_ids:
            continue
        groups[_normalize(_test_case_text(test_case))].append(test_case.id)
    return [DuplicateGroup(method="normalized", test_case_ids=ids) for ids in groups.values() if len(ids) > 1]


def find_semantic_duplicates(
    test_cases: list[TestCase], exclude_ids: set[str], threshold: float = SEMANTIC_SIMILARITY_THRESHOLD
) -> list[DuplicateGroup]:
    candidates = [t for t in test_cases if t.id not in exclude_ids]
    if len(candidates) < 2:
        return []

    from app.rag.embeddings import embed_texts

    vectors = embed_texts([_test_case_text(t) for t in candidates])
    # One BLAS matmul instead of a Python-level double loop calling np.dot
    # per pair - at ~1800 candidates the loop form took ~90s, this takes
    # well under a second (vectors are already L2-normalized, so this is
    # cosine similarity).
    similarity_matrix = vectors @ vectors.T

    groups: list[DuplicateGroup] = []
    grouped: set[str] = set()
    for i, left in enumerate(candidates):
        if left.id in grouped:
            continue
        group_ids = [left.id]
        for j in range(i + 1, len(candidates)):
            right = candidates[j]
            if right.id in grouped:
                continue
            similarity = float(similarity_matrix[i, j])
            if similarity >= threshold:
                group_ids.append(right.id)
        if len(group_ids) > 1:
            grouped.update(group_ids)
            groups.append(DuplicateGroup(method="semantic", test_case_ids=group_ids, similarity=threshold))
    return groups


def find_duplicates(test_cases: list[TestCase]) -> list[DuplicateGroup]:
    exact = find_exact_duplicates(test_cases)
    exact_ids = {tid for group in exact for tid in group.test_case_ids}

    normalized = find_normalized_duplicates(test_cases, exact_ids)
    normalized_ids = {tid for group in normalized for tid in group.test_case_ids}

    semantic = find_semantic_duplicates(test_cases, exact_ids | normalized_ids)

    return exact + normalized + semantic
