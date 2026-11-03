# Development Plan

Repository was empty at project start (git initialized, zero commits, no
files). No existing work to assess or preserve. Environment verified:
Python 3.11.9, Node v22.16.0, npm 10.9.2, pip 24.0 — all compatible with the
planned stack on Windows.

Phases are implemented strictly in order. A phase is not started until the
previous phase's acceptance criteria pass. Each phase ends with: tests run,
docs updated (this file + IMPLEMENTATION_STATUS.md), summary of completed
work and remaining gaps.

## Phase 0 — Repository assessment (this phase)
- [x] Inspect repository and environment.
- [x] Create ARCHITECTURE.md, DEVELOPMENT_PLAN.md, IMPLEMENTATION_STATUS.md.
- Acceptance: docs present and accurate; no code written yet.

## Phase 1 — Foundation (complete)
- [x] Scaffold `backend/` (FastAPI app, Pydantic settings, Uvicorn entrypoint,
      module skeletons per ARCHITECTURE.md).
- [x] Scaffold `frontend/` (Vite + React + TS + Tailwind, hand-built
      shadcn/ui-style primitives), base layout/navigation (10 nav items),
      light/dark theme.
- [x] `app/storage`: atomic JSON read/write + backup/restore primitives.
- [x] Project CRUD (create/rename/duplicate/archive/delete/restore) backed
      by `local_data/projects/`. (Project-level export deferred to Phase 9,
      which covers export formats generally.)
- [x] `.env.example`, `.gitignore`.
- Acceptance: backend boots, frontend boots, can create/list/delete a
  project end-to-end through the UI, data survives restart. **Met** — see
  IMPLEMENTATION_STATUS.md for test/build evidence.

## Phase 2 — Document processing (complete)
- [x] Parsers for PDF/DOCX/XLSX/PPTX/CSV/TXT/MD preserving page/section/sheet
      refs; scanned-page detection flags "OCR required" (actual OCR execution
      deferred — it's optional per the brief, and no OCR engine is bundled).
- [x] Upload API + status tracking (processing/completed/failed, with
      per-document warnings and error messages).
- [x] Document preview endpoint/UI (extracted blocks with page/section
      attribution).
- [x] Duplicate (exact hash match) and conflicting (same filename, different
      content) document detection.
- [x] "Mark as authoritative" flag per document.
- Acceptance: all 7 formats parse sample fixtures correctly; failures
  reported without crashing; project isolation holds. **Met.**

## Phase 3 — RAG (complete)
- [x] Local Sentence-Transformers embeddings (`all-MiniLM-L6-v2`), FAISS
      (`IndexIDMap2` + `IndexFlatIP`, cosine via normalized vectors) index
      per project.
- [x] Semantic chunking with full metadata (project/doc/page/section/chunk
      id; `requirement_id` field reserved for Phase 5 to populate).
- [x] BM25 (rank_bm25) keyword index + hybrid retrieval with configurable
      semantic/keyword weighting + min-max score normalization + exact-text
      chunk dedup at chunking time.
- [x] Incremental indexing (per-document add/replace/remove), full project
      rebuild, and automatic recovery from a corrupt FAISS file (re-embeds
      from the still-intact chunk metadata).
- Acceptance: retrieval returns correct source-attributed chunks across
  multiple projects with no cross-project leakage. **Met** — verified both
  in automated tests and live, including a true empty-result check for an
  unrelated project.

## Phase 4 — Gemini integration
- Official Google Gen AI SDK client in `app/ai`.
- Model registry (no hardcoded model names in business logic), model
  discovery, connection test endpoint.
- Structured JSON output + schema validation, retry/backoff, rate-limit and
  quota detection, usage tracking.
- Pause/resume behavior on quota exhaustion (preserve partial results).
- Acceptance: connection test passes with a real key; a quota-exceeded
  simulation pauses cleanly and resumes without data loss; unit tests use
  mocked responses.

## Phase 5 — Requirement analysis
- Extraction + classification (functional/business/non-functional/rules/
  validations/workflows/roles/etc.).
- Stable ID generation (preserve existing IDs where present).
- Classification states (clear/partial/ambiguous/conflicting/missing/not
  testable) + clarification register.
- Acceptance: extraction on fixture docs produces requirements with correct
  source refs and classification; no fabricated requirements.

## Phase 6 — Test generation
- Batched generation engine per test type (business/application/system/
  integration/E2E/security) x category (positive/negative/edge/boundary/
  destructive).
- Prompt assembly from retrieved RAG context only (no full-document dumps).
- Pydantic schema validation on all generated output; destructive cases
  flagged, never auto-executed.
- Job state machine (Queued..Completed/Failed/Cancelled) with per-batch
  persistence and resume-on-failure.
- Acceptance: all requested categories generate for a fixture project;
  schema-valid output; interrupted job resumes from last successful batch.

## Phase 7 — Coverage and quality
- Deterministic coverage engine (rule-based, not LLM-estimated) +
  traceability matrix.
- Duplicate detection (exact/normalized/semantic).
- Gemini quality-review pass (gaps, weak expected results, miscategorized
  cases) as a separate, explicit step.
- Acceptance: coverage percentages reproducible without calling the LLM;
  duplicates flagged, not auto-deleted.

## Phase 8 — Repository
- Spreadsheet-style grid (search/filter/sort/paginate/inline+bulk edit).
- Manual add/copy/delete/approve/lock, regeneration that preserves manual
  edits and approved/locked cases, version history/compare.
- Acceptance: manual edits survive a full regeneration; locked cases are
  never overwritten.

## Phase 9 — Reporting
- Excel/Word/PDF/CSV/JSON exporters with selective scope (project/module/
  requirement/category), traceability matrix and clarification register in
  exports.
- Acceptance: all 5 export formats produce valid, correctly formatted files
  from a real generated dataset.

## Phase 10 — Hardening
- Regression pass across phases 1-9, security review (path traversal,
  prompt-injection guards, localhost binding, secret handling), performance
  pass (large documents, large test-case sets), backup/restore drill.
- Acceptance: automated test suite green; manual security/perf checklist
  signed off; documentation complete including Windows install steps.

## Testing strategy (ongoing, every phase)
Backend unit tests (pytest), API integration tests, frontend tests, lint,
type-check, production build — run for real, never reported as passing
without execution. Gemini is mocked only in automated unit tests; the running
app always uses the real configured API.

## Next step
Awaiting explicit instruction to begin Phase 4 (Gemini integration): the
official Google Gen AI SDK, a centralized model registry, connection
testing, structured JSON output, and quota/retry handling.
