import json
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.repositories import template_semantic_repo
from app.services import llm_client, material_service


class NodeSemanticRecord(BaseModel):
    node_id: str
    normalized_title: str
    canonical_label: Optional[str] = None
    semantic_tags: list[str] = Field(default_factory=list)
    normalized_section: Optional[str] = None
    llm_confidence: float = 0.0
    llm_trace_id: Optional[str] = None


class SemanticNormalizeResponse(BaseModel):
    ok: bool = True
    task_id: str
    node_count: int
    normalized_count: int
    generated_at: str
    provider: str
    model: str
    records: list[NodeSemanticRecord]


def _fallback_record(node: material_service.TemplateNode) -> NodeSemanticRecord:
    title = node.title.strip() or "Untitled"
    tags: list[str] = [node.node_type, node.content_mode]
    if node.field_type and node.field_type != "unknown":
        tags.append(node.field_type)
    return NodeSemanticRecord(
        node_id=node.node_id,
        normalized_title=title,
        canonical_label=title,
        semantic_tags=tags,
        normalized_section=None,
        llm_confidence=0.0,
        llm_trace_id=None,
    )


def _normalize_with_llm(
    node: material_service.TemplateNode,
    section_title: Optional[str],
) -> NodeSemanticRecord:
    fallback = _fallback_record(node)
    if not llm_client.llm_client.enabled:
        return fallback

    system_prompt = (
        "你是项目验收模板节点语义标准化器。"
        "请输出严格 JSON，字段：normalized_title, canonical_label, semantic_tags, normalized_section, llm_confidence。"
        "semantic_tags 为字符串数组，最多 6 项。llm_confidence 范围 0 到 1。"
    )
    user_prompt = json.dumps(
        {
            "node_title": node.title,
            "node_type": node.node_type,
            "content_mode": node.content_mode,
            "field_type": node.field_type,
            "section_title": section_title,
            "parser_notes": node.parser_notes,
        },
        ensure_ascii=False,
    )
    result = llm_client.llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
    try:
        payload = json.loads(result.text or "{}")
    except json.JSONDecodeError:
        payload = {}
    tags = payload.get("semantic_tags")
    if not isinstance(tags, list):
        tags = fallback.semantic_tags
    tags = [str(item).strip() for item in tags if str(item).strip()][:6]
    confidence_raw = payload.get("llm_confidence")
    try:
        confidence = float(confidence_raw)
    except Exception:
        confidence = result.confidence
    confidence = max(0.0, min(1.0, confidence))
    return NodeSemanticRecord(
        node_id=node.node_id,
        normalized_title=str(payload.get("normalized_title") or fallback.normalized_title).strip()
        or fallback.normalized_title,
        canonical_label=str(payload.get("canonical_label") or fallback.canonical_label).strip()
        or fallback.canonical_label,
        semantic_tags=tags,
        normalized_section=(
            str(payload.get("normalized_section")).strip()
            if payload.get("normalized_section") is not None
            else section_title
        ),
        llm_confidence=confidence,
        llm_trace_id=result.trace_id,
    )


def normalize_template_semantics(task_id: str) -> SemanticNormalizeResponse:
    material_service.get_task(task_id)
    nodes = material_service.list_template_nodes(task_id)
    node_by_id = {node.node_id: node for node in nodes}
    records: list[NodeSemanticRecord] = []

    for node in nodes:
        section_title = None
        parent_id = node.parent_id
        while parent_id:
            parent = node_by_id.get(parent_id)
            if not parent:
                break
            if parent.node_type == "section":
                section_title = parent.title
                break
            parent_id = parent.parent_id

        records.append(_normalize_with_llm(node=node, section_title=section_title))

    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "task_id": task_id,
        "generated_at": generated_at,
        "provider": llm_client.llm_client.provider if llm_client.llm_client.enabled else "fallback",
        "model": (
            llm_client.llm_client.bigmodel_chat_model
            if llm_client.llm_client.enabled and llm_client.llm_client.provider == "bigmodel"
            else llm_client.llm_client.chat_model
            if llm_client.llm_client.enabled
            else "none"
        ),
        "records": [item.model_dump() for item in records],
    }
    template_semantic_repo.save_template_semantic(task_id, payload)
    material_service.apply_template_node_semantics(
        task_id,
        {item.node_id: item.model_dump() for item in records},
    )

    return SemanticNormalizeResponse(
        ok=True,
        task_id=task_id,
        node_count=len(nodes),
        normalized_count=len(records),
        generated_at=generated_at,
        provider=payload["provider"],
        model=payload["model"],
        records=records,
    )
