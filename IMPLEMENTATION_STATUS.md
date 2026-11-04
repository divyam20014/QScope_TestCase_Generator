# Implementation Status

Last updated: 2026-11-04

## Current phase: Phase 10 — Hardening (complete). All 10 planned phases done.

## Summary
Phase 9 added Excel/Word/PDF/CSV/JSON exporters with selective scope and
persisted export history. Phase 10 is the regression/security/performance/
documentation pass across everything built in Phases 1-9: it found and
fixed one real O(n^2) performance bug, added security tests that didn't
exist before (path traversal, secret handling, upload limits, a live
backup/restore drill), and added the Windows install documentation the
project was missing. With this, every phase in DEVELOPMENT_PLAN.md is
complete.

## Phase 9 — Reporting

### Backend (`backend/app/exporters/`)
- `data.py`: one shared, format-agnostic layer defining the 17-column
  test-case schema, the traceability-matrix columns, and the clarification-
  register columns exactly once (`TEST_CASE_COLUMNS` / `TRACEABILITY_COLUMNS`
  / `CLARIFICATION_COLUMNS` + `*_to_row()` functions) - every writer below
  consumes the same shaped rows, so the schema can't drift between formats.
  `ExportScope` (`requirement_ids` / `test_types` / `test_categories`):
  `requirement_ids` scopes the traceability matrix and clarification
  register to the same requirements, not just which test-case rows appear;
  `test_types`/`test_categories` only filter test-case rows.
- `xlsx_writer.py` (openpyxl): 3 sheets - Test Cases, Traceability Matrix,
  Clarification Register.
- `docx_writer.py` (python-docx): a heading + table per section, same 3
  sections.
- `pdf_writer.py` (reportlab, landscape letter): same 3 sections as
  `Paragraph`-wrapped table cells so long text wraps instead of overflowing.
- `csv_writer.py`: **Test Cases only** - CSV is inherently single-table, so
  there's no sheet/section for the other two to live in. Documented as a
  deliberate limitation, not worked around with a zip-of-CSVs.
- `json_writer.py`: one JSON object with all three as top-level keys.
- `service.py`: `create_export` persists the generated file to
  `local_data/reports/<project_id>/<export_id>.<ext>` and an `ExportRecord`
  (format, filename, size, scope, test_case_count) to that project's
  `reports/_index.json`; `get_export_content` reads it back for download.
- `app/api/exports.py`: `POST /exports` (creates + persists),
  `GET /exports` (history), `GET /exports/{id}/download` (streams the file
  with the correct content-type and `Content-Disposition: attachment`).

### Tests
- `tests/test_exporters.py` (7 tests): every writer re-opened and verified
  with its own real parser - `openpyxl.load_workbook`, `docx.Document`, PDF
  magic-byte + size check, `csv.reader`, `json.loads` - confirming each
  format is not just "bytes were produced" but **actually valid, reopenable
  output** containing the right data in the right place. Plus an
  empty-dataset case for all five.
- `tests/test_exports_api.py` (6 tests): full pipeline through the real API
  (extract -> generate -> coverage-stamp -> export); all 5 formats via one
  loop test; requirement-scoped export correctly narrows the traceability
  matrix too; export history listing; unknown project/export 404s.

## Phase 10 — Hardening

### Security review
- **Path traversal**: `safe_join` (the primitive every `app/core/paths.py`
  helper is built on) now has direct unit tests against real `..`/absolute
  escape attempts - it was never actually tested before, only used. Added a
  global `PathTraversalError` -> `400 {"detail": "Invalid id"}` exception
  handler in `app/main.py`; previously an escape attempt fell through to an
  unhandled exception (Starlette's default 500, not information-leaking,
  but untested and opaque). The exception message itself embeds a resolved
  absolute filesystem path - the handler deliberately never echoes it.
- **Prompt-injection guards**: re-verified (not re-built) that every
  LLM-facing prompt - requirement extraction, test generation, quality
  review - explicitly frames source document/test-case content as
  untrusted data, never instructions. This was already true from Phases
  5-7; this phase's contribution is confirming it holds across all three
  prompt modules at once, in one pass.
- **Secrets**: confirmed (with a new test) that `GEMINI_API_KEY` never
  appears in any API response, including `/api/system/info`, which only
  ever returns a boolean.
- **Upload limits**: confirmed `max_upload_size_mb` is actually enforced
  (it was, since Phase 2) - it just had no test before; added one (413 on
  an oversized file).

### Performance pass
Ran a synthetic 300-requirement / 1800-test-case project (no real documents
needed - test cases were written directly as JSON to exercise the data
layer at scale) through every read-heavy endpoint. Findings:
- `GET /requirements`, `/test-cases`, `/coverage`, `/coverage/traceability`:
  all well under a second to ~1.3s even cold.
- **Found and fixed a real bug**: `GET /coverage/duplicates` took **88
  seconds**. Root cause: `find_semantic_duplicates` computed every pairwise
  cosine similarity with an individual `float(np.dot(vectors[i],
  vectors[j]))` call inside a Python double loop - ~1.6M individual calls
  for 1800 candidates. Fixed by computing the full similarity matrix with
  one vectorized `vectors @ vectors.T` (BLAS) call instead; the grouping
  loop then just indexes the precomputed matrix. **The loop itself dropped
  from ~88s to ~0.1s** - verified by direct profiling, and the existing
  `test_duplicates.py` suite re-run to confirm identical grouping results
  (same bug class as any "accidentally quadratic" code: correct, just
  needlessly slow - not caught by any test because none of the existing
  tests used more than a handful of test cases).
- At that same 1800-row scale, two further costs remain and are
  **library/hardware-inherent, not algorithmic bugs**, so they're
  documented rather than "fixed" with disproportionate effort:
  - CPU-based sentence-transformer embedding of 1800 texts takes ~59s on
    its own (profiled directly) - this is now essentially the entire cost
    of `/coverage/duplicates` at that scale, with the actual comparison
    logic negligible after the fix above.
  - DOCX/PDF export of 1800 rows took 15-40s in different runs, profiled to
    python-docx's/reportlab's own per-cell XML/object construction
    overhead (confirmed via `cProfile` - dominated by `docx.oxml`
    attribute/child-element machinery, not anything in this project's own
    code). XLSX/CSV/JSON export of the same 1800 rows took well under 4s.
- **Recommendation for very large projects** (recorded here rather than
  silently left for a user to discover): prefer XLSX/CSV/JSON over DOCX/PDF
  for exports once a project has on the order of 1000+ test cases, and
  expect `/coverage/duplicates` to take real time (tens of seconds) at
  similar scale, since it must re-embed every test case fresh on every
  call - no caching layer exists for that path today.

### Backup/restore drill
- Phase 1 already unit-tested the storage primitive itself
  (`test_json_store.py`: corrupt-file -> backup recovery). This phase adds
  an end-to-end drill through the real API: create two test cases (so a
  rotated backup exists), corrupt the live `test_cases.json` on disk mid-
  session, then confirm `GET /test-cases` transparently recovers the
  correct prior state from the automatic backup rather than erroring or
  returning an empty/wrong list - and that the corrupt file is repaired in
  place as a side effect of the recovery read.

### Documentation
- Added a root `README.md` (previously the repo had none) with: Windows
  setup steps (Python venv, `pip install`, `.env` key setup, `npm install`),
  how to run both dev servers, how to run both test suites, where user data
  lives (`local_data/`, gitignored) and how to back it up/reset it.

## Tests executed (all passed, real execution)
- Backend: `pytest` — **160/160 passed** (up from 141 before Phase 9):
  - Phase 9: `test_exporters.py` (7), `test_exports_api.py` (6).
  - Phase 10: `test_security.py` (7) - the only new test file; the
    duplicate-detection fix was verified against the **existing**
    `test_duplicates.py` suite (still 5/5 passing, confirming the
    vectorized rewrite produces identical results) plus the standalone
    profiling run described above.
  - All Phase 1-8 tests unchanged and still green.
- Frontend: `npx tsc -b`, `npm run lint`, `npm run build` — all clean
  (no frontend changes in Phases 9-10; re-verified anyway as part of the
  regression pass).
- **Live verification**: every new Phase 9 endpoint exercised through a
  real running instance (temporary data dir, cleaned up after); the
  performance findings above come from real profiled runs against a real
  running app instance with real synthetic data, not estimates.

## Known limitations / gaps (project-wide, as of all 10 phases)
- **No real Gemini API key was available in this environment at any point**
  in this project's development. Every phase that calls Gemini (4, 5, 6,
  7's quality-review pass) has its plumbing fully tested against mocked
  responses and the real SDK's verified shapes/error classes, but actual
  generation *quality* (does it avoid fabrication in practice, pick sensible
  classifications/priorities, write genuinely useful test cases) has never
  been observed against a real model. This is the single most important
  thing to check before trusting this app's output: put a real key in
  `.env` and run extraction + generation + quality-review against a real
  fixture document.
- The frontend covers Projects, Documents (+ RAG search), and the Test Case
  Repository (Phase 8) end-to-end. It does **not** yet have UI for: running
  requirement extraction or test generation jobs (Phases 5-6 - API-only
  today), viewing coverage/traceability/duplicates (Phase 7 - API-only),
  triggering the quality-review pass (Phase 7 - API-only), AI model/config
  settings (Phase 4 - API-only), or browsing/downloading exports (Phase 9 -
  API-only). All of that functionality exists and is tested at the API
  layer; wiring it into the UI is the natural next increment of work if
  wanted.
- `/coverage/duplicates` has no caching - it re-embeds every test case on
  every call. Fine at normal project scale; noticeably slow (tens of
  seconds) in the thousands-of-test-cases range, per the performance pass
  above.
- DOCX/PDF export similarly has no obvious further speedup available
  without a deeper rewrite of how those libraries build documents; XLSX/
  CSV/JSON are the fast path for large exports.
- As in every prior phase, there is no Playwright/chromium-cli in this
  sandbox for a literal screenshot-based UI check - frontend verification
  is type-check + lint + build + manual HTTP-level checks through the real
  Vite proxy, consistent with every phase since Phase 1.

## Post-completion: frontend wiring, a real-key bug fix, and multi-provider support (2026-11-04)

After all 10 phases were marked complete, the user pointed out that most nav
items still showed Phase 1's placeholder pages despite Phases 4-7/9's
backend being fully built - that frontend wiring had been skipped. This
triggered three further rounds of work:

1. **Built the 5 missing frontend pages**: AI Configuration, Requirement
   Analysis, Test Case Generator, Coverage Analysis (tabbed: coverage/
   traceability/duplicates/quality-review), and Reports. Every nav item is
   now a real page backed by the APIs built in Phases 4-7/9, not a
   placeholder. `npx tsc -b` / `npm run lint` / `npm run build` all clean.

2. **Found and fixed a real, previously-undetected bug using the user's own
   real Gemini API key** - the thing every prior phase's docs flagged as
   impossible to verify without one. The first live extraction call failed
   with a `pydantic.ValidationError` deep inside the `google-genai` SDK:
   `t_schema` builds Gemini's request schema by calling a Pydantic class's
   `model_json_schema()` directly and never resolves `$ref`/`$defs` - so
   every one of this app's structured-output schemas (all three are
   "container holding `list[NestedModel]`") was broken against the real
   API, despite 160+ passing tests, because no test had ever exercised the
   real SDK's schema-conversion path (by design - Gemini is mocked in
   automated tests). Root-caused by reading the installed SDK's own source
   (`google/genai/_transformers.py`), not guessed. Fixed with
   `app/ai/schema.py`'s `GeminiSchemaModel` base class, which inlines
   `$ref`s and converts Pydantic's `anyOf: [...,{"type":"null"}]` nullable
   form into Gemini's `nullable: true` flag. Verified fixed by re-running
   the same live call and watching the error change (and eventually
   disappear) - not just that the code compiled.
3. Also hit, and correctly diagnosed rather than papering over, a second issue: `gemini-2.0-
   flash` (the model this whole project was built against) has been
   retired by Google - the live API's own error named the replacement
   (`gemini-3.8-flash`), confirming how far real-world model lineups had
   moved since this registry was written. Updated the default and the
   one confirmed-working registry entry to match; deliberately removed the
   other three stale 1.x/2.x entries rather than guessing at unverified
   replacement names for them.
4. **Added OpenAI and Anthropic as additional providers**, at the user's
   request, turning the previously-aspirational "single `AIProvider`
   interface" (ARCHITECTURE.md section 9) into a real one: `app/ai/
   provider.py` (the `Protocol`), `app/ai/openai_client.py` (Responses API,
   `.parse(text_format=...)`), `app/ai/anthropic_client.py` (Messages API,
   `.parse(output_format=...)`). Both verified against the actually-
   installed SDK versions (`openai==3.45.0`, `anthropic==2.4.0`) by
   inspecting real method signatures/exception constructors directly -
   same rigor as the Gemini fix, not assumed from training-data knowledge
   of older SDK versions. `app/ai/model_registry.py` now tags every model
   with its provider; `app/ai/service.py` routes to the right client and
   caches one instance per provider. The old `Gemini*Error` exception names
   were renamed to provider-generic `AIProvider*Error` across the codebase
   (client, routers, services, tests) since they're no longer Gemini-
   specific. 18 new tests (`test_openai_client.py`, `test_anthropic_client.py`,
   `test_ai_service_routing.py`) using the **real** SDK exception classes
   (constructed via real `httpx2.Response` objects) rather than faked stand-
   ins - 178/178 passing.
5. **Fixed a latent test-isolation bug this surfaced**: `Settings.model_config`
   hardcodes `env_file=<repo root>/.env`, so once a real `.env` with a real
   key existed (added this session so the user could test live), several
   tests that used `monkeypatch.delenv("GEMINI_API_KEY")` silently started
   reading the *real* key back out of the `.env` file, because `delenv`
   only removes an `os.environ` override - it doesn't hide a value that
   exists in the lower-priority dotenv file pydantic-settings also reads.
   Fixed by changing those tests (and the shared `client` fixture) to
   `monkeypatch.setenv(..., "")` instead, which always wins. This was a
   real gap in a file previously untested - it was invisible for the
   entire project history because no `.env` file existed in this
   environment until this session.

**Not yet live-verified**: the OpenAI model id (`gpt-5-mini`) and the entire
Anthropic client are unverified against a real key in this environment - no
Anthropic key was available, and the live Gemini check's free-tier quota and
a `503 UNAVAILABLE` ("high demand") response from Google interrupted
verifying a full real Gemini generation end-to-end before the user asked to
pause that and build multi-provider support instead. Both model ids are
flagged as unverified directly in the registry's `description` field so
this is visible in the AI Configuration UI, not just in this file.

## Post-completion, round 2: fixed a frontend error-display bug, added a free local provider, and automatic cross-model failover (2026-11-04)

Prompted by the user hitting a real `503 UNAVAILABLE` from Gemini (Google's
own infrastructure under "high demand" - not a bug) rendered in the UI as
the unhelpful literal string `[object Object]`.

1. **Fixed the `[object Object]` bug** (a real frontend bug, separate from
   the 503 itself): several backend endpoints raise `HTTPException(detail=
   {"message": ..., "retry_after_seconds": ...})` for a 429 - an *object*,
   not a string. `frontend/src/lib/api.ts` passed that object straight into
   `new Error(detail)`, and JS's `Error` constructor silently stringifies a
   non-string message to the literal text `"[object Object]"`. Rewrote the
   shared error-handling path (`detailToMessage` + `readErrorAndThrow`, used
   by `request`/`upload`/`downloadBlob` instead of three duplicated
   try/catch blocks) to always extract a real string - `.message` when
   `detail` is an object shaped like ours, `JSON.stringify` as a fallback
   for anything else.
2. **Added Ollama as a fourth, free, fully open-source provider**
   (`app/ai/ollama_client.py`) - runs entirely on the user's own machine via
   https://ollama.com, no API key, no external rate limits. Verified against
   the actually-installed `ollama` package (0.6.3) by inspecting its real
   `Client.chat()` signature and exception classes (`ResponseError` has
   `.status_code`; a genuinely unreachable server raises a plain Python
   `ConnectionError`, mapped to `AIProviderNotConfiguredError` since there's
   no "key" to misconfigure, just a server to have running). Two model
   entries added (`llama3.2`, `qwen2.5`) - both **unverified live** since no
   Ollama server was running in this environment; flagged as such directly
   in the registry description.
3. **Built automatic cross-model failover**, at the user's explicit request
   ("switch between models when too much load, do not stop execution").
   `app.ai.service.generate_json` now tries the selected model first, and on
   *any* `AIProviderError` (not configured, quota exceeded, or a
   503-class overload - exactly what the user had just hit) automatically
   tries every other registered model, across every provider, in registry
   order, before giving up. Each fallback attempt uses `max_retries=0`
   (`FAILOVER_MAX_RETRIES_PER_MODEL`) rather than each client's normal
   up-to-3-attempt backoff - the whole point is to abandon a struggling
   model quickly and move on, not spend minutes retrying the same one (this
   is exactly what made the original 503 so slow to surface: ~170s of
   in-client backoff before the error even reached the user). If every
   candidate fails, the *originally selected* model's own error is what
   gets raised - not whichever fallback happened to be tried last - since
   that's the most actionable one for the caller. Required threading a new
   `max_retries` parameter through every client's `generate_json` (Gemini,
   OpenAI, Anthropic, Ollama) and the shared `AIProvider` Protocol.
   `generator/service.py`'s existing "pause the job on quota exceeded"
   handling is unchanged in code but now only actually triggers once every
   model has failed, not just the selected one - "do not stop execution"
   now means something stronger than it did when there was only Gemini.
4. 21 new tests (`test_ollama_client.py` and `test_ai_failover.py`, plus
   updates to `test_ai_service_routing.py` for the 4th provider) -
   189/189 passing. The failover tests mock at the `get_client_for_model`
   level to simulate quota-exceeded, not-configured, and overload failures
   in combination, and confirm: the result comes from whichever model
   actually succeeded; usage is only ever credited to that model, never a
   failed one; and the *first* (preferred) model's error surfaces if
   everything fails, not an arbitrary fallback's.

**Not yet live-verified**: `gpt-5-mini`, `claude-haiku-5-5`, `llama3.2`, and
`qwen2.5` are all unverified against a real account/server in this
environment (no OpenAI/Anthropic keys were added here, and no Ollama server
was running) - each is flagged as unverified directly in its registry
`description`. The *mechanism* (failover itself, the Ollama client's
request/error handling) is tested thoroughly; the *specific model ids*
could turn out to be wrong the same way `gemini-2.0-flash` did, and would
need the same live-correction treatment once a real key/server is
available.

## Next step
The user has an OpenAI key to add manually. Recommended next actions, in
order: (1) add `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` to `.env`, and/or
install Ollama + `ollama pull llama3.2`, then use **Test Connection** in AI
Configuration for each - correct `app/ai/model_registry.py`'s model ids if
any come back wrong, the same way the Gemini entry was corrected; (2) retry
a real generation run now that both the schema bug and failover are in
place, to finally get a live read on *generation quality* (not just
plumbing/resilience), which no amount of automated testing in this
environment can substitute for. Nothing has been committed to git by this
session - review the working tree and commit when ready.
