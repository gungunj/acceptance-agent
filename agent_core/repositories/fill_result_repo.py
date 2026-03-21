import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import material_service

API_ROOT = Path(__file__).resolve().parents[2] / "apps" / "api"
DATA_DIR = API_ROOT / "data"
FILL_RESULTS_DIR = DATA_DIR / "fill_results"
FILL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _path(task_id: str) -> Path:
    return FILL_RESULTS_DIR / f"{task_id}.json"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_fill_results(task_id: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    parsed_results = [material_service.FillNodeResult.model_validate(item) for item in results]
    verified_count = sum(1 for item in parsed_results if item.evidence_status == "verified")
    weak_count = sum(1 for item in parsed_results if item.evidence_status == "weak")
    missing_count = sum(1 for item in parsed_results if item.evidence_status == "missing")
    payload = {
        "task_id": task_id,
        "summary": {
            "result_count": len(parsed_results),
            "verified_count": verified_count,
            "weak_count": weak_count,
            "missing_count": missing_count,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "strategy": "external_writeback",
        },
        "results": [item.model_dump() for item in parsed_results],
    }
    _write_json(_path(task_id), payload)
    return payload
