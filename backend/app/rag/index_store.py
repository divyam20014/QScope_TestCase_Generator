from __future__ import annotations

import numpy as np

from app.core.paths import vector_index_chunks_file, vector_index_faiss_file, vector_index_meta_file
from app.parsers.models import ExtractedBlock
from app.rag.chunking import chunk_blocks
from app.rag.embeddings import embed_query, embed_texts, embedding_dim
from app.rag.keyword_index import tokenize
from app.rag.models import Chunk, SearchHit
from app.storage.json_store import read_json, write_json

CANDIDATE_MULTIPLIER = 4


class RagProjectIndex:
    """Per-project hybrid (FAISS + BM25) retrieval index, isolated under
    `local_data/vector_indexes/<project_id>/`. Never shares state across
    projects."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self.chunks: list[Chunk] = []
        self.next_id = 0
        self._faiss_index = None
        self._load()

    # -- persistence -----------------------------------------------------

    def _load(self) -> None:
        import faiss

        raw_chunks = read_json(vector_index_chunks_file(self.project_id), default=[])
        self.chunks = [Chunk.model_validate(c) for c in raw_chunks]

        meta = read_json(vector_index_meta_file(self.project_id), default={"next_id": 0})
        self.next_id = meta.get("next_id", 0)

        faiss_path = vector_index_faiss_file(self.project_id)
        if faiss_path.exists():
            try:
                self._faiss_index = faiss.read_index(str(faiss_path))
                return
            except Exception:  # noqa: BLE001 - corrupt index file, rebuild from chunks below
                pass

        self._faiss_index = faiss.IndexIDMap2(faiss.IndexFlatIP(embedding_dim()))
        if self.chunks:
            self._reembed_all_into_faiss()

    def _reembed_all_into_faiss(self) -> None:
        """Recovery path: chunk metadata survived but the FAISS binary
        didn't (or was corrupt) — recompute vectors from the stored text."""
        vectors = embed_texts([c.text for c in self.chunks])
        ids = np.array([c.chunk_id for c in self.chunks], dtype="int64")
        if len(ids):
            self._faiss_index.add_with_ids(vectors, ids)

    def _save(self) -> None:
        import faiss

        write_json(vector_index_chunks_file(self.project_id), [c.model_dump(mode="json") for c in self.chunks])
        write_json(vector_index_meta_file(self.project_id), {"next_id": self.next_id})
        faiss.write_index(self._faiss_index, str(vector_index_faiss_file(self.project_id)))

    # -- mutation ----------------------------------------------------------

    def add_document(self, document_id: str, document_name: str, blocks: list[ExtractedBlock]) -> int:
        self._remove_document_chunks(document_id)

        chunk_dicts = chunk_blocks(blocks)
        if not chunk_dicts:
            self._save()
            return 0

        texts = [c["text"] for c in chunk_dicts]
        vectors = embed_texts(texts)
        ids = list(range(self.next_id, self.next_id + len(chunk_dicts)))
        self.next_id += len(chunk_dicts)

        new_chunks = [
            Chunk(
                chunk_id=chunk_id,
                project_id=self.project_id,
                document_id=document_id,
                document_name=document_name,
                page=c["page"],
                sheet=c["sheet"],
                section=c["section"],
                text=c["text"],
            )
            for chunk_id, c in zip(ids, chunk_dicts, strict=True)
        ]
        self.chunks.extend(new_chunks)
        self._faiss_index.add_with_ids(vectors, np.array(ids, dtype="int64"))
        self._save()
        return len(new_chunks)

    def remove_document(self, document_id: str) -> None:
        self._remove_document_chunks(document_id)
        self._save()

    def _remove_document_chunks(self, document_id: str) -> None:
        stale_ids = [c.chunk_id for c in self.chunks if c.document_id == document_id]
        if stale_ids:
            self._faiss_index.remove_ids(np.array(stale_ids, dtype="int64"))
        self.chunks = [c for c in self.chunks if c.document_id != document_id]

    def rebuild(self, documents: list[tuple[str, str, list[ExtractedBlock]]]) -> int:
        """Full rebuild from scratch — used for index recovery or after a
        config change (e.g. a different embedding model)."""
        import faiss

        self.chunks = []
        self.next_id = 0
        self._faiss_index = faiss.IndexIDMap2(faiss.IndexFlatIP(embedding_dim()))
        total = 0
        for document_id, document_name, blocks in documents:
            total += self.add_document(document_id, document_name, blocks)
        return total

    # -- retrieval -----------------------------------------------------

    def chunk_count(self) -> int:
        return len(self.chunks)

    def _chunk_by_id(self, chunk_id: int) -> Chunk | None:
        for c in self.chunks:
            if c.chunk_id == chunk_id:
                return c
        return None

    def search_semantic(self, query: str, top_k: int) -> list[tuple[int, float]]:
        if not self.chunks:
            return []
        query_vector = embed_query(query).reshape(1, -1)
        k = min(top_k, len(self.chunks))
        scores, ids = self._faiss_index.search(query_vector, k)
        results = []
        for score, chunk_id in zip(scores[0], ids[0], strict=True):
            if chunk_id == -1:
                continue
            results.append((int(chunk_id), float(score)))
        return results

    def search_keyword(self, query: str, top_k: int) -> list[tuple[int, float]]:
        if not self.chunks:
            return []
        from rank_bm25 import BM25Okapi

        tokenized_corpus = [tokenize(c.text) for c in self.chunks]
        bm25 = BM25Okapi(tokenized_corpus)
        query_tokens = tokenize(query)
        scores = bm25.get_scores(query_tokens)

        # BM25's IDF term goes negative for words present in most/all of a
        # small corpus (trivially true with only 1-2 documents indexed,
        # which is common early in a project) - raw score sign is then
        # meaningless. Use actual token overlap to decide relevance, and
        # the raw score only to rank among genuine matches.
        query_token_set = set(query_tokens)
        candidates = [
            (chunk.chunk_id, float(score))
            for chunk, score in zip(self.chunks, scores, strict=True)
            if query_token_set & set(tokenize(chunk.text))
        ]
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]

    @staticmethod
    def _normalize(scores: dict[int, float]) -> dict[int, float]:
        if not scores:
            return {}
        values = list(scores.values())
        lo, hi = min(values), max(values)
        if hi - lo < 1e-9:
            return {k: 1.0 for k in scores}
        return {k: (v - lo) / (hi - lo) for k, v in scores.items()}

    def search_hybrid(self, query: str, top_k: int, semantic_weight: float = 0.5) -> list[SearchHit]:
        candidate_k = max(top_k * CANDIDATE_MULTIPLIER, top_k)
        semantic_raw = dict(self.search_semantic(query, candidate_k))
        keyword_raw = dict(self.search_keyword(query, candidate_k))

        semantic_norm = self._normalize(semantic_raw)
        keyword_norm = self._normalize(keyword_raw)

        all_ids = set(semantic_norm) | set(keyword_norm)
        blended: list[SearchHit] = []
        for chunk_id in all_ids:
            chunk = self._chunk_by_id(chunk_id)
            if chunk is None:
                continue
            s_score = semantic_norm.get(chunk_id, 0.0)
            k_score = keyword_norm.get(chunk_id, 0.0)
            combined = semantic_weight * s_score + (1 - semantic_weight) * k_score
            blended.append(
                SearchHit(
                    chunk=chunk,
                    score=combined,
                    semantic_score=semantic_raw.get(chunk_id),
                    keyword_score=keyword_raw.get(chunk_id),
                )
            )
        blended.sort(key=lambda h: h.score, reverse=True)
        return blended[:top_k]

    def search(self, query: str, top_k: int, mode: str = "hybrid", semantic_weight: float = 0.5) -> list[SearchHit]:
        if mode == "semantic":
            return [
                SearchHit(chunk=self._chunk_by_id(cid), score=score, semantic_score=score)
                for cid, score in self.search_semantic(query, top_k)
                if self._chunk_by_id(cid) is not None
            ]
        if mode == "keyword":
            return [
                SearchHit(chunk=self._chunk_by_id(cid), score=score, keyword_score=score)
                for cid, score in self.search_keyword(query, top_k)
                if self._chunk_by_id(cid) is not None
            ]
        return self.search_hybrid(query, top_k, semantic_weight)
