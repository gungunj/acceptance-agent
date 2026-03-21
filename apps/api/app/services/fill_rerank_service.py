import json
from typing import Literal, Optional

from pydantic import BaseModel

from app.services import llm_client, material_service

EvidenceStatus = Literal["verified", "weak", "missing"]


class FillRerankResult(BaseModel):
    selected_unit_id: Optional[str] = None
    evidence_status: EvidenceStatus = "missing"
    reason: str = "no_candidate"


def _fallback_pick(candidates: list[material_service.FillNodeMatchCandidate]) -> FillRerankResult:
    if not candidates:
        return FillRerankResult(selected_unit_id=None, evidence_status="missing", reason="no_candidate")
    best = candidates[0]
    confidence = (
        float(best.rerank_score)
        if best.rerank_score is not None
        else max(0.0, min(1.0, 0.5 + (best.score / 10.0)))
    )
    if confidence >= 0.8:
        status: EvidenceStatus = "verified"
    elif confidence >= 0.6:
        status = "weak"
    else:
        status = "missing"
    return FillRerankResult(
        selected_unit_id=best.unit_id,
        evidence_status=status,
        reason="fallback_top1_by_score",
    )


def llm_rerank_fill_candidates(
    node: material_service.TemplateNode,
    node_query: material_service.FillNodeQuery,
    candidates: list[material_service.FillNodeMatchCandidate],
) -> FillRerankResult:
    if not candidates:
        return FillRerankResult(selected_unit_id=None, evidence_status="missing", reason="no_candidate")

    if not llm_client.llm_client.enabled:
        return _fallback_pick(candidates)

    capped_candidates = candidates[:10]
    candidate_payload = [
        {
            "unit_id": item.unit_id,
            "title": item.title,
            "unit_type": item.unit_type,
            "source_type": item.source_type,
            "rule_score": item.score,
            "rerank_score": item.rerank_score,
            "reason": item.reason,
            "retrieval_source": item.retrieval_source,
        }
        for item in capped_candidates
    ]

    system_prompt = (
        "你是项目验收文档的证据重排器。只能从给定 candidates 中选择最合适的一条证据。"
        "输出 JSON: {\"selected_unit_id\":\"...|null\",\"evidence_status\":\"verified|weak|missing\",\"reason\":\"...\"}。"
        "不要输出额外字段，不要编造 candidates 之外的 unit_id。"
    )
    user_prompt = json.dumps(
        {
            "node": {
                "node_id": node.node_id,
                "title": node.title,
                "field_type": node.field_type,
                "requires_screenshot": node.requires_screenshot,
            },
            "node_query": {
                "query_text": node_query.query_text,
                "keywords": node_query.keywords,
                "section_title": node_query.section_title,
                "expected_unit_types": node_query.expected_unit_types,
            },
            "candidates": candidate_payload,
        },
        ensure_ascii=False,
    )

    try:
        result = llm_client.llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        payload = json.loads(result.text or "{}")
    except Exception:
        return _fallback_pick(candidates)

    selected_unit_id_raw = payload.get("selected_unit_id")
    selected_unit_id = str(selected_unit_id_raw).strip() if selected_unit_id_raw is not None else None
    candidate_ids = {item.unit_id for item in capped_candidates}
    if selected_unit_id not in candidate_ids:
        selected_unit_id = None

    evidence_status_raw = str(payload.get("evidence_status") or "").strip().lower()
    if evidence_status_raw not in {"verified", "weak", "missing"}:
        evidence_status_raw = "weak" if selected_unit_id else "missing"
    reason = str(payload.get("reason") or "").strip() or "llm_rerank"

    if selected_unit_id is None and evidence_status_raw != "missing":
        evidence_status_raw = "missing"

    return FillRerankResult(
        selected_unit_id=selected_unit_id,
        evidence_status=evidence_status_raw,  # type: ignore[arg-type]
        reason=reason,
    )
