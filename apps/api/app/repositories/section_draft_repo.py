import json
from pathlib import Path
from typing import Any, Optional

API_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = API_ROOT / "data"
SECTION_DRAFTS_DIR = DATA_DIR / "section_drafts"
SECTION_DRAFTS_DIR.mkdir(parents=True, exist_ok=True)


def _section_drafts_path(task_id: str) -> Path:
    return SECTION_DRAFTS_DIR / f"{task_id}.json"


def _write_json_atomic(path: Path, payload: Any) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_section_draft_results(
    task_id: str, results: list[dict[str, Any]], generated_at: Optional[str] = None
) -> dict[str, Any]:
    payload = {
        "task_id": task_id,
        "results": results,
    }
    if generated_at:
        payload["generated_at"] = generated_at
    _write_json_atomic(_section_drafts_path(task_id), payload)
    return payload


def list_section_draft_results(task_id: str) -> list[dict[str, Any]]:
    raw = _read_json(_section_drafts_path(task_id), {"results": []})
    results = raw.get("results", []) if isinstance(raw, dict) else []
    return results if isinstance(results, list) else []

