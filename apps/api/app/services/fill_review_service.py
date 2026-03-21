from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.services import material_service

FillStatus = Literal["ready", "risky", "missing"]


class ReviewableFillNodeResult(BaseModel):
    task_id: str
    node_id: str
    node_title: str
    field_type: material_service.NodeFieldType
    selected_unit_id: Optional[str] = None
    evidence_status: material_service.EvidenceStatus
    fill_status: FillStatus
    fill_value: Optional[Any] = None
    bound_image_unit_id: Optional[str] = None
    render_payload: Optional[dict[str, Any]] = None
    risk_note: Optional[str] = None
    manual_action: Optional[str] = None
    selected_candidate: Optional[material_service.FillNodeMatchCandidate] = None
    generation_confidence: Optional[float] = None
    pending_review: bool = False
    applied_by_policy: bool = False
    llm_trace_id: Optional[str] = None
    evidence_unit_ids: list[str] = Field(default_factory=list)


def _derive_fill_status(result: material_service.FillNodeResult) -> FillStatus:
    if result.pending_review:
        return "risky"
    if result.field_type == "image":
        return "ready" if result.bound_image_unit_id else "missing"
    evidence_status = result.evidence_status
    if evidence_status == "verified":
        return "ready"
    if evidence_status == "weak":
        return "risky"
    return "missing"


def _derive_risk_note(fill_status: FillStatus) -> Optional[str]:
    if fill_status == "risky":
        return "候选证据分值偏低，建议人工复核后再确认填充。"
    if fill_status == "missing":
        return "未找到可用证据，需要补充素材或人工填写。"
    return None


def _derive_manual_action(fill_status: FillStatus) -> Optional[str]:
    if fill_status == "risky":
        return "请在候选列表中人工确认最优证据。"
    if fill_status == "missing":
        return "请补充相关素材文件并重新执行匹配与解析。"
    return None


def list_reviewable_fill_results(task_id: str) -> list[ReviewableFillNodeResult]:
    results = material_service.list_fill_node_results(task_id)
    reviewable: list[ReviewableFillNodeResult] = []
    for result in results:
        fill_status = _derive_fill_status(result)
        selected_unit_id = (
            result.bound_image_unit_id
            or (result.selected_candidate.unit_id if result.selected_candidate else None)
        )
        reviewable.append(
            ReviewableFillNodeResult(
                task_id=result.task_id,
                node_id=result.node_id,
                node_title=result.node_title,
                field_type=result.field_type,
                selected_unit_id=selected_unit_id,
                evidence_status=result.evidence_status,
                fill_status=fill_status,
                fill_value=result.fill_value,
                bound_image_unit_id=result.bound_image_unit_id,
                render_payload=result.render_payload,
                risk_note=_derive_risk_note(fill_status),
                manual_action=_derive_manual_action(fill_status),
                selected_candidate=result.selected_candidate,
                generation_confidence=result.generation_confidence,
                pending_review=result.pending_review,
                applied_by_policy=result.applied_by_policy,
                llm_trace_id=result.llm_trace_id,
                evidence_unit_ids=result.evidence_unit_ids,
            )
        )
    return reviewable
