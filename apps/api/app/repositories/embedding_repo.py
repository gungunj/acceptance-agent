import json
from pathlib import Path
from typing import Any
from uuid import uuid4

API_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = API_ROOT / "data"
EMBEDDINGS_DIR = DATA_DIR / "material_embeddings"
LEGACY_EMBEDDINGS_DIR = DATA_DIR / "embeddings"
EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
LEGACY_EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)


def _path(task_id: str) -> Path:
    return EMBEDDINGS_DIR / f"{task_id}.json"


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".{uuid4().hex}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def save_embeddings(task_id: str, payload: dict[str, Any]) -> None:
    _write_json_atomic(_path(task_id), payload)


def load_embeddings(task_id: str) -> dict[str, Any]:
    path = _path(task_id)
    if not path.exists():
        legacy = LEGACY_EMBEDDINGS_DIR / f"{task_id}.json"
        if legacy.exists():
            path = legacy
        else:
            return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except json.JSONDecodeError:
        return {}
