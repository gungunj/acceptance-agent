import json
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

API_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = API_ROOT / "data"
RESOLVED_TEMPLATES_DIR = DATA_DIR / "resolved_templates"
RESOLVED_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def _resolved_template_path(task_id: str) -> Path:
    return RESOLVED_TEMPLATES_DIR / f"{task_id}.json"


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".{uuid4().hex}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_resolved_template(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _write_json_atomic(_resolved_template_path(task_id), payload)
    return payload


def load_resolved_template(task_id: str) -> Optional[dict[str, Any]]:
    raw = _read_json(_resolved_template_path(task_id), None)
    return raw if isinstance(raw, dict) else None
