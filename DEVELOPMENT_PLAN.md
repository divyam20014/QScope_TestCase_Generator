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

## Phase 4 — Gemini integration (complete)
- [x] Official Google Gen AI SDK (`google-genai` 2.34.0) client in `app/ai`.
- [x] Model registry (no hardcoded model names in business logic), model
      listing endpoint, connection test endpoint.
- [x] Structured JSON output (Pydantic `response_schema`) + retry/backoff,
      rate-limit (429) and quota detection (`GeminiQuotaExceededError` with
      `retry_after_seconds`), usage tracking persisted per model.
- [x] Request-level pause hook on quota exhaustion (the exception a future
      job runner catches); job-level pause/resume with preserved partial
      results is Phase 6's batch job state machine, built on this hook.
- Acceptance: unit tests use mocked responses (57->72 passing) and the real
  SDK's client/error shapes were verified against the installed package.
  **Partially met** — no real Gemini API key was available in this
  environment, so a live connection test and a live quota-exceeded
  simulation against Google's servers are still outstanding; everything else
  is met. See IMPLEMENTATION_STATUS.md.

## Phase 5 — Requirement analysis (complete)
- [x] Extraction + classification (functional/business/non_functional/rule/
      validation/workflow/role/other) via `app.ai.service.generate_json`,
      batched per document from RAG-indexed chunks (never raw re-reads).
- [x] Stable ID generation: an identifier already present in the source text
      (e.g. "REQ-12:") is preserved verbatim; otherwise a sequential,
      type-prefixed id (FR-/BR-/NFR-/RULE-/VAL-/WF-/ROLE-/REQ-) is assigned,
      never colliding with an id already in use in the project.
- [x] Classification states (clear/partial/ambiguous/conflicting/missing/
      not_testable) + a clarification register (one open item per
      non-"clear" requirement, with resolve/resolution-note support).
- Acceptance: unit + mocked-API tests on fixture docs produce requirements
  with correct source refs (document/page/section down to the exact source
  chunk) and classification (91 tests passing, up from 72). **Partially
  met** — no real Gemini API key was available in this environment, so the
  "no fabricated requirements" guarantee rests on the extraction prompt's
  explicit anti-fabrication instructions plus lossless mocked-response
  plumbing, not a live extraction run against a real document. See
  IMPLEMENTATION_STATUS.md.

## Phase 6 — Test generation (complete)
- [x] Batched generation engine: one batch = one (requirement, test_type,
      test_category) triple, covering all 6 test types (business/
      application/system/integration/e2e/security) x 5 categories
      (positive/negative/edge/boundary/destructive).
- [x] Prompt assembly from retrieved RAG context only (`gather_context`:
      the requirement's own source chunk + top hybrid-search hits for its
      text) - never a full-document dump.
- [x] Pydantic schema validation on all generated output (`GeneratedTestBatchLLM`
      via `app.ai.service.generate_json`); destructive-category cases are
      flagged (`destructive: true`) on the stored record - the system only
      ever generates a description of such a test, never executes anything.
- [x] Job state machine (Queued->Running->Paused/Completed/Failed/Cancelled)
      with per-batch persistence: both the job's progress and that batch's
      test cases are saved immediately after every batch, so `resume_job`
      always continues from exactly the next unfinished batch, and retrying
      a batch replaces (never duplicates) its own prior output.
- Acceptance: all requested type x category combinations generate for a
  fixture project with mocked responses; schema-valid output; a job
  interrupted by a simulated failure resumes from the last successful batch
  with no duplicated test cases (109 tests passing, up from 91).
  **Partially met** — no real Gemini API key was available in this
  environment, so generation *quality* (does the model actually avoid
  fabricating product behavior, pick sensible priorities) rests on the
  prompt's instructions plus fully-mocked-response tests, not a live run.
  See IMPLEMENTATION_STATUS.md.

## Phase 7 — Coverage and quality (complete)
- [x] Deterministic coverage engine (rule-based, zero LLM calls) +
      traceability matrix: a requirement is "covered" once it has both a
      positive and a negative test case, "partial" with some but not both,
      "not_covered" with none - computed fresh from requirements/test cases
      every time, so it is always reproducible and never drifts.
- [x] Duplicate detection, escalating exact -> normalized -> semantic
      (embedding similarity via the existing RAG embedding model), each test
      case reported in at most one group. Read-only report - nothing here
      deletes or merges anything.
- [x] Gemini quality-review pass (weak expected results, miscategorized
      cases, unclear steps) as a separate, explicit step from generation -
      narrower than originally scoped to gap detection, since gaps/missing
      categories are already exact and LLM-free via the coverage engine;
      the LLM pass only judges things that actually need judgment.
- Acceptance: coverage percentages are deterministic and reproducible
  without any LLM call (unit-tested directly against the engine, including
  re-running the same computation twice and asserting bit-identical
  output); duplicates are flagged via a read-only endpoint, never
  auto-deleted (131 tests passing, up from 109). **Partially met** for the
  quality-review pass specifically — no real Gemini API key was available
  in this environment, so its judgment quality rests on the prompt's
  instructions plus mocked-response tests, not a live review of real
  generated test cases. See IMPLEMENTATION_STATUS.md.

## Phase 8 — Repository (complete)
- [x] Spreadsheet-style grid: search, type/category filters, sortable
      columns, pagination, row selection + bulk toolbar (approve/lock/
      delete), inline row actions (edit/copy/approve/lock/delete). Built as
      hand-rolled React state (see ARCHITECTURE.md section 7 for why, not
      TanStack Table as originally planned).
- [x] Manual add/copy/delete/approve/lock, scoped by (requirement, test_type,
      test_category) so a later generation job covering the same scope adds
      alongside - never replaces - protected cases.
- [x] Regeneration preserves manual edits/approved/locked cases: any test
      case that is locked, approved, or manually edited is excluded from
      the "replace this scope's output" step a fresh batch run performs.
- [x] Version history: every edit snapshots the pre-edit record; a per-test-
      case history endpoint/dialog lists them (no diff/compare view - raw
      snapshots only, kept simple).
- Acceptance: manual edits survive a full regeneration and locked cases are
  never overwritten - both verified by an automated test that generates a
  batch, locks one of its test cases, re-runs the identical
  requirement/type/category combination, and asserts the locked case is
  unchanged while new cases are added alongside it (141 backend tests
  passing, up from 131). Frontend build/typecheck/lint all clean; verified
  live through the real Vite dev-server proxy (manual create/approve/edit/
  lock/history/delete-blocked-by-lock), not just automated tests.

## Phase 9 — Reporting (complete)
- [x] Excel/Word/PDF/CSV/JSON exporters, all built from one shared,
      format-agnostic dataset/row-shaping layer (`app/exporters/data.py`)
      so the 17-column test-case schema is defined exactly once.
- [x] Selective scope: `requirement_ids` (also scopes the traceability
      matrix/clarification register to the same requirements, not just the
      test-case rows) and `test_types`/`test_categories` (filter which
      test-case rows appear, without narrowing which requirements are in
      scope).
- [x] Traceability matrix + clarification register included as extra sheets
      (xlsx), sections (docx/pdf), or JSON keys (json). CSV is the one
      exception by necessity - it's inherently single-table, so a CSV
      export is test cases only (documented, not worked around).
- [x] Every export is persisted to `local_data/reports/<project_id>/` and
      listed/downloadable via the API, not just returned once and
      discarded.
- Acceptance: all 5 formats produce valid, parseable files from a real
  generated dataset (xlsx reopened with openpyxl, docx reopened with
  python-docx, pdf verified as real PDF bytes, csv/json parsed back) - 153
  tests passing, up from 141. **Met**, with the one documented CSV
  limitation above.

## Phase 10 — Hardening (complete)
- [x] Regression pass across phases 1-9: full suite re-run clean after every
      change in this phase (160/160).
- [x] Security review:
      - Path traversal: `safe_join` unit-tested directly against real `..`
        escape attempts (wasn't tested before this phase); a global
        `PathTraversalError` -> HTTP 400 handler added to `app/main.py` so
        an escape attempt can never surface a resolved filesystem path in
        an error response (the previous behavior was an unhandled 500 -
        safe, but opaque and un-tested).
      - Prompt-injection guards: confirmed every LLM-facing prompt
        (requirements extraction, test generation, quality review)
        explicitly frames source content as untrusted data, never
        instructions - already true since Phases 5-7, re-verified here.
      - Localhost binding / secrets: confirmed `127.0.0.1` default bind,
        CORS restricted to the Vite dev origins, `GEMINI_API_KEY` never
        read from or written to any JSON file or API response (new test:
        `/api/system/info` never leaks it even when set).
      - Upload size limit: confirmed enforced (was already implemented in
        Phase 2) but had no test - added one.
- [x] Performance pass with a synthetic 300-requirement / 1800-test-case
      project: found and fixed a real O(n^2) bug (duplicate detection's
      semantic-similarity pass did ~1.6M individual Python-level `np.dot`
      calls - 88s at this scale; replaced with one vectorized matrix
      multiply - the loop itself is now ~0.1s). The remaining cost at that
      scale (~1 minute, dominated by CPU embedding of 1800 texts) and DOCX/
      PDF export time (15-40s, dominated by python-docx/reportlab's
      per-cell XML object overhead for ~32,000 cells) are library/hardware-
      inherent, not algorithmic bugs - documented rather than papered over.
- [x] Backup/restore drill: added an end-to-end test that corrupts a live
      project's `test_cases.json` mid-session through the real API surface
      (not just the storage primitive, which Phase 1 already covered) and
      confirms a subsequent read transparently recovers the correct prior
      state from the automatic backup.
- [x] Root `README.md` added with Windows setup steps (backend venv, `.env`
      key setup, frontend install, running both dev servers, running the
      test suites) - the one documentation gap this phase's acceptance
      criteria call out by name.
- Acceptance: automated test suite green (160/160); security/perf checklist
  above completed with one real bug found and fixed, two real but
  library-inherent scaling characteristics found and documented rather than
  masked; Windows install steps now exist. **Met.**

## Testing strategy (ongoing, every phase)
Backend unit tests (pytest), API integration tests, frontend tests, lint,
type-check, production build — run for real, never reported as passing
without execution. Gemini is mocked only in automated unit tests; the running
app always uses the real configured API.

## Next step
All 10 planned phases are now complete. See IMPLEMENTATION_STATUS.md for
the current known-limitations list (mostly: no real Gemini API key was
available in this environment to verify live generation *quality*, and the
frontend covers documents/RAG/repository but not every backend capability
built in Phases 4-7/9 yet). Remaining work from here is user-driven:
real-key verification, any additional frontend screens wanted, and ordinary
feature requests/bug reports against this baseline.
