import os
import pickle
import logging
import numpy as np
from app.rag.embedder import get_embedder
from app.services.aicafe_service import AICafeService
from app.utils.app_discovery import get_vectorstore_path
import faiss

logger = logging.getLogger(__name__)

DEBUG = True

# In-memory cache: {application: (index, chunks)}
# Cache is invalidated on every load_index call (fresh load always)
_index_cache: dict = {}


class RAGService:
    def __init__(self):
        self.aicafe = AICafeService()

    def vectorstore_exists(self, application: str) -> bool:
        vs_path = get_vectorstore_path(application)
        return (
            os.path.exists(os.path.join(vs_path, "index.faiss"))
            and os.path.exists(os.path.join(vs_path, "metadata.pkl"))
        )

    def load_index(self, application: str, force_reload: bool = False) -> dict:
        """Load FAISS index from disk. force_reload=True always re-reads from disk."""
        if application in _index_cache and not force_reload:
            logger.info(f"[RAG] Index for '{application}' served from cache")
            _, chunks = _index_cache[application]
            return {
                "status": "loaded",
                "application": application,
                "source": "cache",
                "vectors": len(chunks),
            }

        vs_path = get_vectorstore_path(application)
        index_file = os.path.join(vs_path, "index.faiss")
        meta_file = os.path.join(vs_path, "metadata.pkl")

        if not os.path.exists(index_file) or not os.path.exists(meta_file):
            raise FileNotFoundError(
                f"Vectorstore not found for '{application}'. "
                "Please run ingestion first (click 'Load KB' or 'Refresh document')."
            )

        logger.info(f"[RAG] Loading index from disk: {vs_path}")
        index = faiss.read_index(index_file)
        with open(meta_file, "rb") as f:
            chunks = pickle.load(f)

        _index_cache[application] = (index, chunks)
        logger.info(f"[RAG] ✓ Index loaded: {index.ntotal} vectors, {len(chunks)} chunks")
        return {
            "status": "loaded",
            "application": application,
            "source": "disk",
            "vectors": index.ntotal,
            "chunks": len(chunks),
        }

    def evict_cache(self, application: str):
        """Remove application from cache so next load reads fresh from disk."""
        if application in _index_cache:
            del _index_cache[application]
            logger.info(f"[RAG] Cache evicted for '{application}'")

    def _retrieve(self, application: str, question: str, top_k: int = 5) -> list:
        """
        Hybrid retrieval: semantic (FAISS cosine) + keyword match.
        Always loads fresh from disk — no stale cache.
        """
        # Always reload fresh for every query to avoid stale results
        self.load_index(application, force_reload=False)
        index, chunks = _index_cache[application]

        embedder = get_embedder()
        q_vec = embedder.encode([question])
        q_vec = np.array(q_vec, dtype=np.float32)
        faiss.normalize_L2(q_vec)   # normalize for cosine similarity

        # ── Semantic search ───────────────────────────────────────────────────
        k = min(top_k * 2, index.ntotal)   # fetch more, then re-rank
        distances, indices = index.search(q_vec, k)

        semantic_results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(chunks):
                continue
            semantic_results.append({
                "chunk": chunks[idx],
                "score": float(dist),
                "method": "semantic",
            })

        if DEBUG:
            logger.info(f"[RETRIEVAL] Question: {question!r}")
            logger.info(f"[RETRIEVAL] Semantic results ({len(semantic_results)}):")
            for r in semantic_results[:3]:
                logger.info(f"  score={r['score']:.4f} | source={r['chunk']['source']} | text={r['chunk']['text'][:100]!r}")

        # ── Keyword match ─────────────────────────────────────────────────────
        keywords = [w.lower() for w in question.split() if len(w) > 3]
        keyword_results = []
        if keywords:
            for i, chunk in enumerate(chunks):
                text_lower = chunk["text"].lower()
                hits = sum(1 for kw in keywords if kw in text_lower)
                if hits > 0:
                    keyword_results.append({
                        "chunk": chunk,
                        "score": hits / len(keywords),
                        "method": "keyword",
                    })
            keyword_results.sort(key=lambda x: x["score"], reverse=True)
            keyword_results = keyword_results[:top_k]

            if DEBUG:
                logger.info(f"[RETRIEVAL] Keyword results ({len(keyword_results)}):")
                for r in keyword_results[:3]:
                    logger.info(f"  hits={r['score']:.2f} | source={r['chunk']['source']} | text={r['chunk']['text'][:100]!r}")

        # ── Merge & deduplicate ───────────────────────────────────────────────
        seen_texts = set()
        merged = []
        for r in semantic_results + keyword_results:
            key = r["chunk"]["text"][:80]
            if key not in seen_texts:
                seen_texts.add(key)
                merged.append(r)

        # Sort by semantic score first, then keyword score
        merged.sort(key=lambda x: x["score"], reverse=True)
        final = [r["chunk"] for r in merged[:top_k]]

        logger.info(f"[RETRIEVAL] Final chunks returned: {len(final)}")
        return final

    async def chat(self, application: str, question: str) -> dict:
        if not self.vectorstore_exists(application):
            raise FileNotFoundError(
                f"Knowledge base not found for '{application}'. Please load KB first."
            )

        retrieved = self._retrieve(application, question)

        if not retrieved:
            logger.warning(f"[RAG] No chunks retrieved for question: {question!r}")
            return {
                "answer": "Not available in knowledge base",
                "sources": [],
                "chunks_used": 0,
                "application": application,
            }

        context = "\n\n---\n\n".join([c["text"] for c in retrieved])
        sources = list(dict.fromkeys(c.get("source", "") for c in retrieved if c.get("source")))

        if DEBUG:
            logger.info(f"[RAG] Context length: {len(context)} chars from {len(retrieved)} chunks")
            logger.info(f"[RAG] Sources: {sources}")
            logger.info(f"[RAG] Prompt preview (first 300 chars): {context[:300]!r}")

        answer = await self.aicafe.complete(question, context)

        return {
            "answer": answer,
            "sources": sources,
            "chunks_used": len(retrieved),
            "application": application,
        }
