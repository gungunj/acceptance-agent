import json
from pathlib import Path
from typing import Any

from app.services import material_service

from agent_core.repositories import fill_result_repo, section_draft_repo, template_node_repo


def _load_input_payload(input_path: str) -> Any:
    path = Path(input_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw


def _extract_results(payload: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        items = payload.get(key, [])
        return items if isinstance(items, list) else []
    return []


def save_fill_results(task_id: str, input_path: str) -> dict[str, Any]:
    material_service.get_task(task_id)
    payload = _load_input_payload(input_path)
    results = _extract_results(payload, "results")
    saved = fill_result_repo.save_fill_results(task_id=task_id, results=results)
    return {"ok": True, "task_id": task_id, "result_count": len(saved.get("results", []))}


def save_section_drafts(task_id: str, input_path: str) -> dict[str, Any]:
    material_service.get_task(task_id)
    payload = _load_input_payload(input_path)
    results = _extract_results(payload, "results")
    saved = section_draft_repo.save_section_drafts(task_id=task_id, results=results)
    return {"ok": True, "task_id": task_id, "result_count": len(saved.get("results", []))}


def save_template_nodes(task_id: str, input_path: str) -> dict[str, Any]:
    material_service.get_task(task_id)
    payload = _load_input_payload(input_path)
    if isinstance(payload, dict):
        nodes = payload.get("nodes", [])
        template_file_id = payload.get("template_file_id")
    elif isinstance(payload, list):
        nodes = payload
        template_file_id = None
    else:
        nodes = []
        template_file_id = None
    if not isinstance(nodes, list):
        nodes = []
    saved = template_node_repo.save_template_nodes(
        task_id=task_id,
        nodes=[item for item in nodes if isinstance(item, dict)],
        template_file_id=template_file_id if isinstance(template_file_id, str) else None,
    )
    return {"ok": True, "task_id": task_id, "node_count": len(saved.get("nodes", []))}
