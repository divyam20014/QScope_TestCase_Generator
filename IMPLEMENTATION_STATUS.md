# Implementation Status

Last updated: 2026-11-03

## Current phase: Phase 3 — RAG (complete)

## Summary
Local, database-free Retrieval-Augmented Generation is fully working:
every successfully-parsed document is automatically chunked, embedded
locally, and indexed into a per-project FAISS + BM25 hybrid index, with
hybrid/semantic/keyword search, incremental add/remove, full rebuild, and
corruption recovery. This is the retrieval layer Phase 4 (Gemini) and
Phase 5 (Requirement Analysis) will build on — no document content is sent
anywhere external yet; everything in this phase runs locally.

## Completed
### Backend (`backend/app/rag/`)
- `app/rag/models.py`: `Chunk` (chunk_id, project_id, document_id,
  document_name, page, sheet, section, text, `requirement_id` reserved for
  Phase 5) and `SearchHit` (chunk + blended/semantic/keyword scores).
- `app/rag/chunking.py`: groups `ExtractedBlock`s into semantically
  coherent chunks — tables always become their own chunk, headings start a
  new section context, paragraphs/list items accumulate under the current
  section up to a configurable character cap (default 800, never splitting
  a block mid-text), and exact-duplicate chunk text is dropped.
- `app/rag/embeddings.py`: lazy-loaded, cached `SentenceTransformer`
  (`all-MiniLM-L6-v2`, configurable via `EMBEDDING_MODEL`), L2-normalized
  embeddings so FAISS inner-product search doubles as cosine similarity.
- `app/rag/keyword_index.py` + `index_store.py`: per-project
  `RagProjectIndex` wrapping a FAISS `IndexIDMap2(IndexFlatIP)` (supports
  add/remove by stable integer id, enabling true incremental indexing) and
  an in-memory `rank_bm25.BM25Okapi` rebuilt from the persisted chunk list
  on each load (cheap, avoids persisting a second binary format). Supports:
  - `add_document` — replaces any existing chunks for that document first,
    so re-uploading/re-processing a document is idempotent.
  - `remove_document` — removes both the FAISS vectors and chunk metadata.
  - `rebuild` — full from-scratch rebuild across a project's documents.
  - `search_semantic` / `search_keyword` / `search_hybrid` (min-max score
    normalization + configurable semantic/keyword weight blend) /
    `search` (mode dispatcher).
  - Automatic recovery: if the FAISS binary is missing or corrupt but the
    chunk metadata JSON survived, vectors are recomputed from the stored
    text on load rather than losing the index.
- `app/rag/service.py`: the glue between documents and the index — indexes
  a document right after a successful parse, removes a document's chunks
  when it's deleted, rebuilds a whole project on demand, exposes search and
  stats, and keeps one live `RagProjectIndex` per project in memory
  (dropped on project delete) so repeated searches don't re-read the FAISS
  file from disk every request.
- `app/api/rag.py`: `GET /api/projects/{id}/rag/search?q=&mode=&top_k=&
  semantic_weight=`, `POST /api/projects/{id}/rag/reindex`,
  `GET /api/projects/{id}/rag/stats`.
- `app/api/documents.py` now triggers indexing automatically right after a
  successful upload+parse, and removes the document's chunks on delete.
  `DocumentRecord` gained `indexed`, `index_error`, `indexed_chunk_count`.
- `project_service.duplicate_project` now also rewrites `project_id` inside
  the copied `chunks.json` (same fix pattern as Phase 2's `documents.json`
  fix), so a duplicated project's RAG metadata doesn't point at the
  original project.

### Frontend
- `types/rag.ts`, `types/document.ts` updated with the new indexing fields.
- Documents table shows an "Indexed (N)" / "Not indexed" badge per document
  (tooltip shows the index error if one occurred — indexing failures never
  block the upload itself).
- `RagSearchPanel` (new): a "Test Retrieval (RAG)" panel at the bottom of
  the Documents page — lets a user try hybrid/semantic/keyword search
  against the active project's indexed content and see each hit's source
  document, page/sheet/section, and score. This exists so retrieval
  quality can be verified now, before Phases 4-6 build the generation
  pipeline on top of it.

## Tests executed (all passed, real execution)
- Backend: `pytest` — **57/57 passed** (up from 35 in Phase 2):
  - `tests/test_chunking.py` (6 tests): tables as their own chunk,
    same-section accumulation, max-char splitting, section-change
    flushing, exact-duplicate-text dedup, empty input handling.
  - `tests/test_rag_index.py` (9 tests): add+semantic search, keyword
    search finds true matches, keyword search excludes non-matches, hybrid
    blending, document removal clears only that document's chunks,
    re-adding a document replaces (not duplicates) its old chunks, index
    persists and reloads correctly from disk, **recovery from a corrupt
    FAISS file** (chunk metadata intact, vectors recomputed), and
    cross-project isolation (a second project's index is completely empty
    and returns no hits for content that only exists in the first).
  - `tests/test_rag_api.py` (7 tests): upload triggers indexing, search
    returns relevant results, all 3 search modes work, deleting a document
    removes its chunks from stats, reindex rebuilds from all documents,
    RAG-level project isolation through the API, and 404 on a missing
    project.
  - All Phase 1/2 tests (`test_projects_api.py`, `test_json_store.py`,
    `test_parsers.py`, `test_documents_api.py`) still green, unchanged.
- Frontend: `npx tsc -b`, `npm run lint` (oxlint — same single pre-existing
  acceptable warning as Phase 2), `npm run build` — all clean.
- **Manual/live verification against the real running servers**: uploaded
  real documents to a live project, confirmed automatic indexing (chunk
  counts matched expectations), ran semantic search ("how do I log in"
  correctly surfaced the login requirement chunk ranked above an unrelated
  "Spec" heading chunk) and keyword search ("lock after 5 attempts"
  returned exactly the one matching chunk), confirmed **true project
  isolation live** (a second, empty project returns zero hits and zero
  stats for a query that matches content only in the first project — not
  just an automated-test claim, an actual live HTTP round trip), confirmed
  deleting a document drops exactly its chunks from the live stats
  endpoint, confirmed reindex rebuilds correctly, and re-verified the same
  upload -> index -> search flow through the real Vite dev-server proxy
  (the exact path the browser uses). `local_data/` was confirmed clean
  after every test project was deleted.

## Bugs found and fixed during this phase
1. **BM25 negative-score bug**: with a small corpus (as low as a single
   indexed document — a completely normal state early in a project), BM25's
   IDF term goes negative for any term present in most/all documents,
   making raw score sign meaningless. The original `search_keyword`
   filtered on `score > 0`, which silently dropped genuine matches whenever
   a project had only one or two documents indexed. Fixed by using actual
   query/chunk token overlap to decide relevance, and the raw BM25 score
   only to rank among genuine matches. Caught by `test_keyword_search_finds_exact_terms`
   failing during this phase's own test-writing, not after the fact.
2. **Stale orphaned process during live verification**: a leftover
   `multiprocessing` spawn-child process (from an earlier test run, parent
   already dead) was still holding port 8000 and serving pre-Phase-3 code
   with no RAG endpoints. Identified by exact PID via
   `Get-CimInstance Win32_Process` (command line showed it was a
   `multiprocessing.spawn` worker, not a legitimate server), killed
   specifically, and the real backend was restarted and reverified before
   any live claims were made. (A similar single-stale-process issue in
   Phase 2 is why this was checked for proactively this time.)

## Known limitations / gaps
- BM25 is rebuilt from the full chunk list on every keyword/hybrid search
  rather than being persisted as a serialized structure. This is simple and
  avoids a second binary format to keep in sync, but will become a
  measurable cost once a project has many thousands of chunks — acceptable
  for now, worth revisiting if Phase 5/6 usage shows it matters.
- Chunking is heuristic (character-count-based with section boundaries),
  not driven by sentence/token-aware splitting — adequate for the
  structured documents this app targets (requirement specs), less so for
  dense unstructured prose.
- `requirement_id` on `Chunk` exists but is always `null` until Phase 5
  (Requirement Analysis) assigns real requirement IDs to source locations.
- No UI exists yet to configure RAG settings (top-K, semantic/keyword
  weight, chunk size) per the brief's Section 15 customization
  requirements — the API supports it (`top_k`, `semantic_weight` query
  params), but Settings/AI Configuration screens are later phases.
- As in Phases 1-2, no Playwright/chromium-cli is available in this sandbox
  for a literal screenshot-based check; verification used type-check,
  lint, build, the full backend test suite, and live HTTP round-trips
  through the actual running Vite proxy with real documents and real
  embedding computations (no mocked AI/ML calls in the live checks).

## Next step
Awaiting explicit instruction to begin Phase 4 (Gemini integration): the
official Google Gen AI SDK, a centralized model registry (no model name
hardcoded in business logic), connection testing, structured JSON output,
and rate-limit/quota-aware retry handling — built on top of the hybrid
retrieval this phase now provides.
