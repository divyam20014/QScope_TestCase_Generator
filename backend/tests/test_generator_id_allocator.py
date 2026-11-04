from __future__ import annotations

from app.generator.id_generator import SequentialIdAllocator


def test_allocate_starts_at_one():
    allocator = SequentialIdAllocator("TC", set())
    assert allocator.allocate() == "TC-0001"


def test_allocate_increments_sequentially():
    allocator = SequentialIdAllocator("TC", set())
    assert [allocator.allocate() for _ in range(3)] == ["TC-0001", "TC-0002", "TC-0003"]


def test_allocate_resumes_after_existing_ids():
    allocator = SequentialIdAllocator("TC", {"TC-0001", "TC-0002"})
    assert allocator.allocate() == "TC-0003"


def test_allocate_skips_taken_ids_even_with_gaps():
    allocator = SequentialIdAllocator("SC", {"SC-0001", "SC-0003"})
    assert allocator.allocate() == "SC-0004"


def test_different_prefixes_are_independent():
    tc = SequentialIdAllocator("TC", set())
    sc = SequentialIdAllocator("SC", set())
    assert tc.allocate() == "TC-0001"
    assert sc.allocate() == "SC-0001"
