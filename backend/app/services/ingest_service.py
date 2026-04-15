import os
import pickle
import shutil
import logging
import numpy as np
from app.rag.document_loader import load_documents
from app.rag.chunker import chunk_documents
from app.rag.embedder import get_embedder
from app.utils.app_discovery import get_app_data_path, get_vectorstore_path
import faiss

logger = logging.getLogger(__name__)


class IngestService:
    def ingest(self, application: str, force: bool = True) -> dict:
        """
        Ingest all documents for an application.
        Always overwrites existing vectorstore (force=True by default).
        """
        app_path = get_app_data_path(application)
        if not os.path.exists(app_path):
            raise FileNotFoundError(f"Application folder not found: {app_path}")

        logger.info(f"{'='*60}")
        logger.info(f"[INGEST] Starting ingestion for: {application}")
        logger.info(f"[INGEST] Source path: {app_path}")
        logger.info(f"{'='*60}")

        # Log all files detected before loading
        from pathlib import Path as _Path
        detected = [f.name for f in _Path(app_path).rglob("*") if f.is_file()]
        logger.info(f"[INGEST] Files detected: {detected}")

        # ── Step 1: Load documents ────────────────────────────────────────────
        docs = load_documents(app_path)
        if not docs:
            raise FileNotFoundError(
                f"No documents found in '{app_path}'. "
                "Add PDF, DOCX, XLSX, or PPTX files to the application folder."
            )
        logger.info(f"[INGEST] Total documents extracted: {len(docs)}")

        # ── Step 2: Chunk ─────────────────────────────────────────────────────
        chunks = chunk_documents(docs)
        if not chunks:
            raise ValueError(f"Chunking produced 0 chunks for '{application}'. Check document content.")
        logger.info(f"[INGEST] Total chunks created: {len(chunks)}")

        # Log sample chunks
        for i, c in enumerate(chunks[:3]):
            logger.info(f"[INGEST] Sample chunk {i+1}: {c['text'][:120]!r} (source: {c['source']})")

        # ── Step 3: Embed ─────────────────────────────────────────────────────
        logger.info(f"[INGEST] Generating embeddings for {len(chunks)} chunks...")
        embedder = get_embedder()
        texts = [c["text"] for c in chunks]
        embeddings = embedder.encode(texts, show_progress_bar=True, batch_size=32)
        embeddings = np.array(embeddings, dtype=np.float32)
        logger.info(f"[INGEST] Embeddings shape: {embeddings.shape}")

        # ── Step 4: Build FAISS index ─────────────────────────────────────────
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)   # Inner Product (cosine after normalization)
        faiss.normalize_L2(embeddings)   # Normalize for cosine similarity
        index.add(embeddings)
        logger.info(f"[INGEST] FAISS index built: {index.ntotal} vectors (dim={dim})")

        # ── Step 5: Save (always overwrite) ───────────────────────────────────
        vs_path = get_vectorstore_path(application)

        # Wipe existing vectorstore to ensure clean state
        if os.path.exists(vs_path):
            shutil.rmtree(vs_path)
            logger.info(f"[INGEST] Cleared existing vectorstore at {vs_path}")

        os.makedirs(vs_path, exist_ok=True)

        index_file = os.path.join(vs_path, "index.faiss")
        meta_file = os.path.join(vs_path, "metadata.pkl")

        faiss.write_index(index, index_file)
        with open(meta_file, "wb") as f:
            pickle.dump(chunks, f)

        logger.info(f"[INGEST] ✓ FAISS index saved successfully → {index_file}")
        logger.info(f"[INGEST] ✓ Metadata saved → {meta_file}")
        logger.info(f"[INGEST] {'='*60}")

        return {
            "status": "success",
            "application": application,
            "documents_loaded": len(docs),
            "chunks_indexed": len(chunks),
            "vectorstore_path": vs_path,
        }
