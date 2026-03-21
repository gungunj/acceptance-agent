from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel

from app.repositories import gap_repo
from app.services import fill_review_service

GapSeverity = Literal["low", "medium", "high"]


class GapItem(BaseModel):
    task_id: str
    node_id: str
    node_title: str
    severity: GapSeverity
    gap_type: str
    description: str
    manual_action: Optional[str] = None


class GapGenerationResponse(BaseModel):
    ok: bool = True
    task_id: str
    generated_count: int
    high_count: int
    medium_count: int
    low_count: int
    generated_at: str
    items: list[GapItem]


def _to_gap_item(result: fill_review_service.ReviewableFillNodeResult) -> Optional[GapItem]:
    if result.fill_status == "ready":
        return None

    if result.fill_status == "risky":
        severity: GapSeverity = "medium"
        gap_type = "weak_evidence"
        description = (
            f"字段“{result.node_title}”已有候选证据，但置信度不足（{result.evidence_status}）。"
        )
        manual_action = result.manual_action or "人工核验候选证据后确认填充值。"
        return GapItem(
            task_id=result.task_id,
            node_id=result.node_id,
            node_title=result.node_title,
            severity=severity,
            gap_type=gap_type,
            description=description,
            manual_action=manual_action,
        )

    severity = "high"
    gap_type = "missing_evidence"
    description = f"字段“{result.node_title}”缺少可用证据，无法自动填充。"
    manual_action = result.manual_action or "补充素材并重新匹配；或直接人工填写该字段。"
    return GapItem(
        task_id=result.task_id,
        node_id=result.node_id,
        node_title=result.node_title,
        severity=severity,
        gap_type=gap_type,
        description=description,
        manual_action=manual_action,
    )


def generate_gap_items(task_id: str) -> GapGenerationResponse:
    reviewable_results = fill_review_service.list_reviewable_fill_results(task_id)
    items: list[GapItem] = []
    for result in reviewable_results:
        gap_item = _to_gap_item(result)
        if gap_item:
            items.append(gap_item)

    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "task_id": task_id,
        "generated_at": generated_at,
        "items": [item.model_dump() for item in items],
    }
    gap_repo.save_gap_items(task_id, payload["items"], generated_at=generated_at)

    high_count = sum(1 for item in items if item.severity == "high")
    medium_count = sum(1 for item in items if item.severity == "medium")
    low_count = sum(1 for item in items if item.severity == "low")

    return GapGenerationResponse(
        ok=True,
        task_id=task_id,
        generated_count=len(items),
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        generated_at=payload["generated_at"],
        items=items,
    )


def list_gap_items(task_id: str) -> list[GapItem]:
    raw_items = gap_repo.list_gap_items(task_id)
    items: list[GapItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        try:
            items.append(GapItem.model_validate(raw))
        except Exception:
            continue
    return items
