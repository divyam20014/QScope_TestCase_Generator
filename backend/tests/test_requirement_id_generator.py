from __future__ import annotations

from app.requirements.id_generator import RequirementIdAllocator, normalize_hint
from app.requirements.models import RequirementType


def test_normalize_hint_strips_and_uppercases():
    assert normalize_hint(" req-12 ") == "REQ-12"
    assert normalize_hint("FR 3!!") == "FR3"


def test_allocate_uses_source_hint_when_available():
    allocator = RequirementIdAllocator(set())
    assigned = allocator.allocate(RequirementType.FUNCTIONAL, "REQ-12")
    assert assigned == "REQ-12"


def test_allocate_generates_sequential_type_prefixed_id_when_no_hint():
    allocator = RequirementIdAllocator(set())
    first = allocator.allocate(RequirementType.FUNCTIONAL, None)
    second = allocator.allocate(RequirementType.FUNCTIONAL, None)
    assert first == "FR-001"
    assert second == "FR-002"


def test_allocate_falls_back_to_generated_id_on_hint_collision():
    allocator = RequirementIdAllocator({"REQ-12"})
    assigned = allocator.allocate(RequirementType.OTHER, "REQ-12")
    assert assigned != "REQ-12"
    assert assigned.startswith("REQ-")


def test_allocate_resumes_sequence_after_existing_ids():
    allocator = RequirementIdAllocator({"BR-001", "BR-002"})
    assigned = allocator.allocate(RequirementType.BUSINESS, None)
    assert assigned == "BR-003"


def test_different_types_get_different_prefixes():
    allocator = RequirementIdAllocator(set())
    assert allocator.allocate(RequirementType.NON_FUNCTIONAL, None) == "NFR-001"
    assert allocator.allocate(RequirementType.RULE, None) == "RULE-001"
    assert allocator.allocate(RequirementType.VALIDATION, None) == "VAL-001"
    assert allocator.allocate(RequirementType.WORKFLOW, None) == "WF-001"
    assert allocator.allocate(RequirementType.ROLE, None) == "ROLE-001"
