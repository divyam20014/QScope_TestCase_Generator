# QScope Test Case Generator — Architecture

## 1. Overview

QScope is a locally-run, database-free QA platform that ingests requirement
documents (BRD/FRD/SRS/specs), extracts requirements via local parsing +
RAG-assisted analysis, and generates traceable, categorized test cases using
Google Gemini (free tier). All persistent state lives on the local filesystem
as JSON (+ FAISS index files) — no RDBMS, no mandatory cloud services.

Primary quality bars: requirement traceability, deterministic coverage
calculation (not LLM-estimated), low Gemini token consumption, and zero
fabricated requirements/results (unsupported details are flagged
"Clarification Required" rather than invented).

## 2. High-level component map

```
React/TS (Vite) SPA  <-- HTTP/JSON (localhost only) -->  FastAPI backend
                                                              |
                        +-------------------------------------+-------------------------------------+
                        |                |                 |                  |                      |
                   parsers/         rag/              requirements/      generator/              exporters/
                 (PyMuPDF,       (SentenceTransf.,    (extraction,      (Gemini-driven,         (openpyxl, docx,
                  docx, xlsx,     FAISS, BM25,         classification,   batch jobs,              ReportLab,
                  pptx, csv,      hybrid retrieval)    clarification     coverage/dup             csv/json)
                  md parsers)                          register)         detection)
                        |                |                 |                  |
                        +----------------+-----------------+------------------+
                                              |
                                        storage/ (atomic JSON read/write, backups)
                                              |
                                     local_data/ (per-project trees)
                                              |
                                        ai/ (Gemini client, model registry,
                                             quota/retry handling)
```

## 3. Backend module responsibilities

- `app/api/` — FastAPI routers (projects, documents, requirements, generation,
  coverage, repository, exports, ai-config, settings). Thin controllers only;
  no business logic.
- `app/core/` — app config, path resolution/sandboxing (prevents path
  traversal, restricts file ops to `local_data/<project>`), job/queue
  orchestration, logging (no secrets/content in logs).
- `app/ai/` — Gemini client wrapper over the official Google Gen AI SDK.
  Centralized model registry (no hardcoded model names in business logic),
  structured-JSON generation helpers, retry/backoff, rate-limit + quota
  detection, usage tracking. Optional local-only adapter stub (Ollama) behind
  the same interface for future use.
- `app/rag/` — chunking, local Sentence-Transformers embeddings, FAISS index
  management (per-project, isolated), BM25 index, hybrid retrieval + ranking,
  incremental indexing/rebuild/recovery.
- `app/parsers/` — per-format extraction (PDF/DOCX/XLSX/PPTX/CSV/TXT/MD) that
  preserves source document/page/section/sheet metadata; optional OCR hook.
- `app/requirements/` — requirement extraction/classification engine,
  stable ID generation, clarification register.
- `app/generator/` — batched test-case generation orchestration per
  test type/category, prompt assembly from RAG context, structured output
  validation against Pydantic schemas, job state machine.
- `app/coverage/` — deterministic (non-LLM) coverage engine + traceability
  matrix.
- `app/validators/` — duplicate detection (exact/normalized/semantic) and
  rule-based quality checks; a separate Gemini "review pass" lives in
  `app/ai` and is invoked from here.
- `app/exporters/` — Excel/Word/PDF/CSV/JSON report generation.
- `app/storage/` — JSON persistence layer: atomic writes (write-temp +
  rename), versioning, backup/restore, schema migration hooks.

## 4. Data layout (`local_data/`)

```
local_data/
  projects/<project_id>/project.json
  documents/<project_id>/<document_id>.{original ext}
  extracted_content/<project_id>/<document_id>.json
  vector_indexes/<project_id>/{faiss.index, bm25.pkl, chunks.json}
  requirements/<project_id>/requirements.json
  test_cases/<project_id>/test_cases.json
  templates/<project_id or "global">/*.json
  reports/<project_id>/<export_id>.{xlsx,docx,pdf,csv,json}
  configurations/{ai.json, settings.json}   (API key stored via env/.env, never in JSON)
  history/<project_id>/{generation_jobs.json, version_history.json}
```

All projects are isolated by `project_id` directory; no cross-project reads.
Every write goes through `app/storage` atomic-write helpers with backup
rotation.

## 5. RAG pipeline

Upload -> parse/extract -> structural parsing -> semantic chunking (with
project/document/page/section/chunk/requirement-id metadata) -> local
embedding (Sentence-Transformers) -> FAISS upsert -> BM25 upsert -> hybrid
retrieval (configurable top-K, score blending) -> dedup -> Gemini call with
only the retrieved context -> structured JSON -> Pydantic validation.

## 6. Test case schema (summary)

Pydantic models enforce the 17-column schema (Requirement ID, Scenario ID,
Scenario Description, Test Case ID, Test Case, Test Type, Test Category,
Preconditions, Test Data, Test Steps, Expected Result, Priority, Source
Document, Source Page, Source Section, Coverage Status, Assumption Status),
with configurable columns/prefixes layered on top for export only — the
canonical stored record always carries the full schema.

## 7. Frontend

React + TypeScript + Vite + Tailwind + shadcn/ui, Recharts for dashboard/
coverage charts. The repository grid (search/filter/sort/paginate/select) is
hand-rolled plain React state over the in-memory test case array, matching
the Documents page's existing table pattern — not TanStack Table: the
`@tanstack/react-table` dependency installed in Phase 1 turned out to be
v9, which replaced the familiar `useReactTable`/`getXRowModel()` hook API
with an atoms/feature-registration architecture (`useTable`, `tableFeatures`,
`table.atoms.*`); given the grid's modest scale (one project's test cases,
client-side pagination), hand-rolling was simpler and lower-risk than
adopting that architecture, so the dependency was removed. API client talks
only to the local FastAPI server (`localhost` by default); no API keys ever
reach the browser — Gemini calls are backend-only.

## 8. Security/isolation notes

- Backend binds to `127.0.0.1` by default.
- All file paths resolved against a sandbox root; traversal rejected.
- Uploaded document content is treated as untrusted data in all prompts
  (never as instructions) — explicit prompt-injection guard in `app/ai`.
- Secrets (Gemini/OpenAI/Anthropic API keys) read from `.env`/environment
  only, excluded from backups and exports, never logged.

## 9. Extensibility

AI provider access goes through a single `AIProvider` interface
(`app/ai/provider.py`) - a `Protocol` with `generate_json`/`test_connection`.
Gemini (`app/ai/client.py`), OpenAI (`app/ai/openai_client.py`), and
Anthropic (`app/ai/anthropic_client.py`) each implement it. `app/ai/
model_registry.py` tags every model with its `provider`; `app/ai/service.py`
resolves the right client from the user's selected model id and caches one
client instance per provider. `app/requirements`, `app/generator`, and
`app/validators` only ever call `app.ai.service.generate_json`/
`test_connection` - never a concrete client - so adding a fourth provider
means adding one new client file plus registry entries, nothing else.

Each provider's SDK has real, materially different quirks the client layer
absorbs so callers never see them:
- **Gemini** (`google-genai`): `response_schema` as a Pydantic class does
  not resolve `$ref`/`$defs` for nested models, and has no JSON "null"
  type - `app/ai/schema.py`'s `GeminiSchemaModel` base class (used by every
  LLM-facing *container* response model: `ExtractionBatchLLM`,
  `GeneratedTestBatchLLM`, `QualityReviewBatchLLM`) flattens the schema
  before it reaches the SDK. This was a real, confirmed bug - found via a
  live call with a real API key, not a guess - that silently broke every
  structured-output call in Phases 5-7 despite 160+ passing mocked tests,
  since no test exercised the real SDK's schema-conversion path.
- **OpenAI** (`openai`, Responses API) and **Anthropic** (`anthropic`,
  Messages API) both ship their own `.parse(..., text_format=/output_format=
  Model)` convenience methods that resolve nested schemas internally, so no
  flattening wrapper is needed for either.
