import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]  # project root
DATA_PATH = BASE_DIR / "data" / "applications"
VECTORSTORE_PATH = BASE_DIR / "vectorstore"


def get_available_applications() -> list:
    """Scan data/applications/ and return folder names."""
    if not DATA_PATH.exists():
        return []
    return [
        d.name
        for d in DATA_PATH.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ]


def get_app_data_path(application: str) -> str:
    return str(DATA_PATH / application)


def get_vectorstore_path(application: str) -> str:
    return str(VECTORSTORE_PATH / application)
