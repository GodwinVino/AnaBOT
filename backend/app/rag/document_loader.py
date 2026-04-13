import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Set DEBUG = True to print chunk samples and detailed file info
DEBUG = True


def load_documents(app_path: str) -> list:
    """
    Load ALL documents from an application folder.
    Supports: PDF, DOCX, XLSX/XLS
    Returns list of {"text": str, "source": str}
    """
    docs = []
    path = Path(app_path)

    if not path.exists():
        logger.error(f"[LOADER] Path does not exist: {app_path}")
        return docs

    all_files = [f for f in path.rglob("*") if f.is_file()]
    supported = [f for f in all_files if f.suffix.lower() in (".pdf", ".docx", ".xlsx", ".xls")]
    skipped = [f.name for f in all_files if f.suffix.lower() not in (".pdf", ".docx", ".xlsx", ".xls", "")]

    logger.info(f"[LOADER] Scanning: {app_path}")
    logger.info(f"[LOADER] Total files found: {len(all_files)}")
    logger.info(f"[LOADER] Supported files: {[f.name for f in supported]}")
    if skipped:
        logger.info(f"[LOADER] Skipped (unsupported): {skipped}")

    for file in supported:
        logger.info(f"[LOADER] Processing: {file.name}")
        if file.suffix.lower() == ".pdf":
            result = _load_pdf(file)
        elif file.suffix.lower() == ".docx":
            result = _load_docx(file)
        elif file.suffix.lower() in (".xlsx", ".xls"):
            result = _load_excel(file)
        else:
            result = []

        if result:
            docs.extend(result)
            logger.info(f"[LOADER] ✓ {file.name} → {len(result)} segment(s)")
        else:
            logger.warning(f"[LOADER] ✗ {file.name} → 0 segments (empty or failed)")

    logger.info(f"[LOADER] Total raw segments loaded: {len(docs)}")

    if DEBUG and docs:
        logger.debug(f"[LOADER] Sample segment (first 200 chars): {docs[0]['text'][:200]!r}")

    return docs


def _load_pdf(file: Path) -> list:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(file))
        docs = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                docs.append({"text": text, "source": f"{file.name} [page {i+1}]"})
        logger.info(f"[PDF] {file.name}: {len(reader.pages)} pages, {len(docs)} non-empty")
        return docs
    except Exception as e:
        logger.error(f"[PDF] Failed to load {file.name}: {e}", exc_info=True)
        return []


def _load_docx(file: Path) -> list:
    try:
        from docx import Document
        doc = Document(str(file))
        segments = []

        # Paragraphs
        para_text = "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())

        # Tables
        table_rows = []
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    table_rows.append(row_text)
        table_text = "\n".join(table_rows)

        full_text = "\n\n".join(filter(None, [para_text, table_text])).strip()
        if full_text:
            segments.append({"text": full_text, "source": file.name})

        logger.info(f"[DOCX] {file.name}: {len(doc.paragraphs)} paragraphs, {len(doc.tables)} tables")
        return segments
    except Exception as e:
        logger.error(f"[DOCX] Failed to load {file.name}: {e}", exc_info=True)
        return []


def _load_excel(file: Path) -> list:
    try:
        import pandas as pd
        xl = pd.ExcelFile(str(file))
        docs = []
        for sheet in xl.sheet_names:
            df = xl.parse(sheet)
            df = df.dropna(how="all").fillna("")
            if df.empty:
                logger.info(f"[XLSX] {file.name} sheet '{sheet}': empty, skipping")
                continue

            # Convert each row to readable text: "Col1: val1 | Col2: val2"
            rows = []
            for _, row in df.iterrows():
                row_parts = [f"{col}: {str(val).strip()}" for col, val in row.items() if str(val).strip()]
                if row_parts:
                    rows.append(" | ".join(row_parts))

            text = f"[Sheet: {sheet}]\n" + "\n".join(rows)
            if text.strip():
                docs.append({"text": text, "source": f"{file.name} [{sheet}]"})
                logger.info(f"[XLSX] {file.name} sheet '{sheet}': {len(rows)} rows")

        return docs
    except Exception as e:
        logger.error(f"[XLSX] Failed to load {file.name}: {e}", exc_info=True)
        return []
