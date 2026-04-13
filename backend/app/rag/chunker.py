import re
import logging

logger = logging.getLogger(__name__)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

# Natural split boundaries — try to break at these first
_SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "]


def chunk_documents(docs: list) -> list:
    """
    Split documents into overlapping chunks using RecursiveCharacterTextSplitter logic.
    Removes empty and duplicate chunks.
    """
    all_chunks = []
    seen_hashes = set()

    for doc in docs:
        text = doc.get("text", "").strip()
        source = doc.get("source", "unknown")
        if not text:
            continue

        raw_chunks = _recursive_split(text, CHUNK_SIZE, CHUNK_OVERLAP)

        for chunk_text in raw_chunks:
            chunk_text = chunk_text.strip()
            if not chunk_text or len(chunk_text) < 20:   # skip trivially short chunks
                continue
            # Deduplicate by normalized content hash
            normalized = re.sub(r"\s+", " ", chunk_text).lower()
            if normalized in seen_hashes:
                continue
            seen_hashes.add(normalized)
            all_chunks.append({"text": chunk_text, "source": source})

    logger.info(f"[CHUNKER] Input segments: {len(docs)} → Output chunks: {len(all_chunks)}")

    if all_chunks:
        logger.debug(f"[CHUNKER] Sample chunk (first 200 chars): {all_chunks[0]['text'][:200]!r}")

    return all_chunks


def _recursive_split(text: str, chunk_size: int, overlap: int) -> list:
    """Recursively split text using natural separators, falling back to hard split."""
    if len(text) <= chunk_size:
        return [text]

    # Try each separator
    for sep in _SEPARATORS:
        if sep in text:
            parts = text.split(sep)
            chunks = []
            current = ""
            for part in parts:
                candidate = current + (sep if current else "") + part
                if len(candidate) <= chunk_size:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    # If single part is too big, recurse
                    if len(part) > chunk_size:
                        chunks.extend(_recursive_split(part, chunk_size, overlap))
                        current = ""
                    else:
                        current = part
            if current:
                chunks.append(current)

            # Apply overlap: prepend tail of previous chunk to next
            if overlap > 0 and len(chunks) > 1:
                overlapped = [chunks[0]]
                for i in range(1, len(chunks)):
                    tail = overlapped[-1][-overlap:]
                    overlapped.append(tail + chunks[i])
                return overlapped
            return chunks

    # Hard split fallback
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start += chunk_size - overlap
    return chunks
