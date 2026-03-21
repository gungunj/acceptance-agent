import json
from pathlib import Path
from typing import Any, Optional

from app.services import material_service

API_ROOT = Path(__file__).resolve().parents[2] / "apps" / "api"
DATA_DIR = API_ROOT / "data"
TEMPLATE_NODES_DIR = DATA_DIR / "template_nodes"
TEMPLATE_NODES_DIR.mkdir(parents=True, exist_ok=True)


def _path(task_id: str) -> Path:
    return TEMPLATE_NODES_DIR / f"{task_id}.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_template_nodes(
    task_id: str,
    nodes: list[dict[str, Any]],
    template_file_id: Optional[str] = None,
) -> dict[str, Any]:
    parsed = [material_service.TemplateNode.model_validate(item) for item in nodes]
    path = _path(task_id)
    if template_file_id is None:
        existing = _read_json(path, {})
        if isinstance(existing, dict):
            template_file_id = existing.get("template_file_id")
    payload = {
        "task_id": task_id,
        "template_file_id": template_file_id,
        "nodes": [item.model_dump() for item in parsed],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
