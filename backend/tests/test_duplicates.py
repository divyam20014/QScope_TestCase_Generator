from __future__ import annotations

from app.generator.models import Priority, TestCase, TestCategory, TestType
from app.validators.duplicates import find_duplicates, find_exact_duplicates, find_normalized_duplicates


def _test_case(tc_id: str, title: str, expected_result: str, steps: list[str] | None = None) -> TestCase:
    return TestCase(
        id=tc_id,
        project_id="p1",
        batch_id="b1",
        requirement_id="REQ-1",
        scenario_id=f"SC-{tc_id}",
        scenario_description="Login succeeds",
        title=title,
        test_type=TestType.SYSTEM,
        test_category=TestCategory.POSITIVE,
        steps=steps or ["Open login page", "Enter valid credentials", "Submit"],
        expected_result=expected_result,
        priority=Priority.MEDIUM,
        source_document="spec.txt",
    )


def test_find_exact_duplicates_flags_identical_test_cases():
    cases = [
        _test_case("TC-1", "Valid login", "User is redirected to the dashboard."),
        _test_case("TC-2", "Valid login", "User is redirected to the dashboard."),
        _test_case("TC-3", "Something else entirely", "A different result."),
    ]
    groups = find_exact_duplicates(cases)
    assert len(groups) == 1
    assert sorted(groups[0].test_case_ids) == ["TC-1", "TC-2"]
    assert groups[0].method == "exact"


def test_find_normalized_duplicates_ignores_case_and_punctuation():
    cases = [
        _test_case("TC-1", "Valid Login!", "User is redirected to the dashboard."),
        _test_case("TC-2", "valid login", "user is redirected to the dashboard"),
    ]
    assert find_exact_duplicates(cases) == []
    groups = find_normalized_duplicates(cases, exclude_ids=set())
    assert len(groups) == 1
    assert sorted(groups[0].test_case_ids) == ["TC-1", "TC-2"]


def test_find_normalized_duplicates_excludes_already_exact_matched_ids():
    cases = [
        _test_case("TC-1", "Valid login", "User is redirected to the dashboard."),
        _test_case("TC-2", "Valid login", "User is redirected to the dashboard."),
    ]
    groups = find_normalized_duplicates(cases, exclude_ids={"TC-1", "TC-2"})
    assert groups == []


def test_find_duplicates_combined_pipeline_reports_each_case_once():
    cases = [
        _test_case("TC-1", "Valid login", "User is redirected to the dashboard."),
        _test_case("TC-2", "Valid login", "User is redirected to the dashboard."),  # exact dup of TC-1
        _test_case("TC-3", "VALID LOGIN", "user is redirected to the dashboard"),  # normalized dup
        _test_case("TC-4", "Completely unrelated case", "Nothing like the others."),
    ]
    groups = find_duplicates(cases)
    all_grouped_ids = [tid for g in groups for tid in g.test_case_ids]
    assert len(all_grouped_ids) == len(set(all_grouped_ids))  # no id reported twice
    assert "TC-4" not in all_grouped_ids


def test_find_duplicates_semantic_catches_reworded_near_duplicate():
    cases = [
        _test_case(
            "TC-1",
            "User logs in with valid credentials",
            "The user is successfully authenticated and taken to their dashboard.",
        ),
        _test_case(
            "TC-2",
            "Valid credential login",
            "The authenticated user lands on their dashboard successfully.",
        ),
        _test_case(
            "TC-3",
            "Password reset email is sent",
            "An email containing a password reset link arrives in the user's inbox.",
        ),
    ]
    groups = find_duplicates(cases)
    semantic_groups = [g for g in groups if g.method == "semantic"]
    assert len(semantic_groups) == 1
    assert sorted(semantic_groups[0].test_case_ids) == ["TC-1", "TC-2"]
    assert "TC-3" not in semantic_groups[0].test_case_ids
