from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.repositories import resolved_template_repo
from app.services import fill_review_service, gap_review_service, material_service, section_draft_service

ResolvedStatus = Literal["ready", "risky", "missing", "skipped"]
ExportReadiness = Literal["ready", "risky", "blocked"]


class ResolvedNode(BaseModel):
    task_id: str
    node_id: str
    node_title: str
    node_type: material_service.TemplateNodeType
    content_mode: material_service.ContentMode
    level: int = 1
    parent_id: Optional[str] = None
    resolved_status: ResolvedStatus
    render_payload: dict[str, Any] = Field(default_factory=dict)
    source_result_type: Optional[str] = None
    source_result_id: Optional[str] = None
    gap_count: int = 0


class ResolvedTemplateSummary(BaseModel):
    total_nodes: int
    ready_nodes: int
    risky_nodes: int
    missing_nodes: int
    export_readiness: ExportReadiness


class ResolvedTemplate(BaseModel):
    ok: bool = True
    task_id: str
    built_at: str
    summary: ResolvedTemplateSummary
    node_count: int
    ready_count: int
    risky_count: int
    missing_count: int
    nodes: list[ResolvedNode]
    gaps: list[gap_review_service.GapItem] = Field(default_factory=list)


def _unit_asset_path(unit: Optional[material_service.MaterialUnit]) -> Optional[str]:
    if not unit or not isinstance(unit.metadata, dict):
        return None
    for key in ("path", "file_path", "asset_path", "url"):
        value = unit.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _fill_to_resolved_node(
    node: material_service.TemplateNode,
    fill_result: Optional[fill_review_service.ReviewableFillNodeResult],
    unit_by_id: dict[str, material_service.MaterialUnit],
    gap_count: int,
) -> ResolvedNode:
    if not fill_result:
        return ResolvedNode(
            task_id=node.task_id,
            node_id=node.node_id,
            node_title=node.title,
            node_type=node.node_type,
            content_mode=node.content_mode,
            level=node.level,
            parent_id=node.parent_id,
            resolved_status="missing",
            render_payload={"type": "missing", "reason": "fill_result_not_found"},
            source_result_type="fill_result",
            source_result_id=node.node_id,
            gap_count=gap_count,
        )

    if fill_result.bound_image_unit_id:
        image_unit = unit_by_id.get(fill_result.bound_image_unit_id)
        payload: dict[str, Any] = {
            "type": "image",
            "unit_id": fill_result.bound_image_unit_id,
        }
        path = _unit_asset_path(image_unit)
        if path:
            payload["path"] = path
        if image_unit and image_unit.title:
            payload["title"] = image_unit.title
        return ResolvedNode(
            task_id=node.task_id,
            node_id=node.node_id,
            node_title=node.title,
            node_type=node.node_type,
            content_mode=node.content_mode,
            level=node.level,
            parent_id=node.parent_id,
            resolved_status=fill_result.fill_status,
            render_payload=payload,
            source_result_type="fill_result",
            source_result_id=fill_result.node_id,
            gap_count=gap_count,
        )

    payload = fill_result.render_payload or {
        "type": "text",
        "value": fill_result.fill_value,
    }
    return ResolvedNode(
        task_id=node.task_id,
        node_id=node.node_id,
        node_title=node.title,
        node_type=node.node_type,
        content_mode=node.content_mode,
        level=node.level,
        parent_id=node.parent_id,
        resolved_status=fill_result.fill_status,
        render_payload=payload,
        source_result_type="fill_result",
        source_result_id=fill_result.node_id,
        gap_count=gap_count,
    )


def _section_to_resolved_node(
    node: material_service.TemplateNode,
    draft: Optional[section_draft_service.SectionDraftResult],
    gap_count: int,
) -> ResolvedNode:
    if not draft:
        return ResolvedNode(
            task_id=node.task_id,
            node_id=node.node_id,
            node_title=node.title,
            node_type=node.node_type,
            content_mode=node.content_mode,
            level=node.level,
            parent_id=node.parent_id,
            resolved_status="missing",
            render_payload={"type": "rich_section", "text": "", "images": []},
            source_result_type="section_draft",
            source_result_id=node.node_id,
            gap_count=gap_count,
        )

    payload = {
        "type": "rich_section",
        "text": draft.draft_text,
        "images": [asset.model_dump() for asset in draft.inline_assets],
    }
    return ResolvedNode(
        task_id=node.task_id,
        node_id=node.node_id,
        node_title=node.title,
        node_type=node.node_type,
        content_mode=node.content_mode,
        level=node.level,
        parent_id=node.parent_id,
        resolved_status=draft.draft_status,
        render_payload=payload,
        source_result_type="section_draft",
        source_result_id=draft.node_id,
        gap_count=gap_count,
    )


def _mixed_to_resolved_node(
    node: material_service.TemplateNode,
    draft: Optional[section_draft_service.SectionDraftResult],
    fill_items: list[fill_review_service.ReviewableFillNodeResult],
    gap_count: int,
) -> ResolvedNode:
    text = draft.draft_text if draft else ""
    images = [asset.model_dump() for asset in draft.inline_assets] if draft else []
    fields: list[dict[str, Any]] = []
    for item in fill_items:
        fields.append(
            {
                "node_id": item.node_id,
                "node_title": item.node_title,
                "fill_status": item.fill_status,
                "render_payload": item.render_payload,
                "bound_image_unit_id": item.bound_image_unit_id,
            }
        )

    if draft and draft.draft_status == "ready":
        resolved_status: ResolvedStatus = "ready" if all(
            (field.get("fill_status") in {"ready", "skipped", None}) for field in fields
        ) else "risky"
    elif draft and draft.draft_status == "risky":
        resolved_status = "risky"
    elif fields:
        resolved_status = "risky"
    else:
        resolved_status = "missing"

    payload = {
        "type": "mixed_section",
        "text": text,
        "images": images,
        "fields": fields,
    }
    return ResolvedNode(
        task_id=node.task_id,
        node_id=node.node_id,
        node_title=node.title,
        node_type=node.node_type,
        content_mode=node.content_mode,
        level=node.level,
        parent_id=node.parent_id,
        resolved_status=resolved_status,
        render_payload=payload,
        source_result_type="mixed_result",
        source_result_id=node.node_id,
        gap_count=gap_count,
    )


def _sort_template_nodes(nodes: list[material_service.TemplateNode]) -> list[material_service.TemplateNode]:
    if not nodes:
        return []
    index_by_id = {node.node_id: idx for idx, node in enumerate(nodes)}
    children_by_parent: dict[Optional[str], list[material_service.TemplateNode]] = {}
    for node in nodes:
        parent = node.parent_id if node.parent_id in index_by_id else None
        children_by_parent.setdefault(parent, []).append(node)

    for items in children_by_parent.values():
        items.sort(key=lambda node: index_by_id.get(node.node_id, 0))

    ordered: list[material_service.TemplateNode] = []

    def dfs(parent_id: Optional[str]) -> None:
        for child in children_by_parent.get(parent_id, []):
            ordered.append(child)
            dfs(child.node_id)

    dfs(None)
    missing = [node for node in nodes if node.node_id not in {item.node_id for item in ordered}]
    ordered.extend(sorted(missing, key=lambda node: index_by_id.get(node.node_id, 0)))
    return ordered


def _is_descendant_node(
    node_id: str,
    ancestor_id: str,
    node_by_id: dict[str, material_service.TemplateNode],
) -> bool:
    current = node_by_id.get(node_id)
    while current and current.parent_id:
        if current.parent_id == ancestor_id:
            return True
        current = node_by_id.get(current.parent_id)
    return False


def build_resolved_template(task_id: str) -> ResolvedTemplate:
    material_service.get_task(task_id)
    nodes = _sort_template_nodes(material_service.list_template_nodes(task_id))
    fill_results = fill_review_service.list_reviewable_fill_results(task_id)
    section_drafts = section_draft_service.list_section_drafts(task_id)
    units = material_service.list_material_units(task_id)

    fill_by_node_id = {item.node_id: item for item in fill_results}
    draft_by_node_id = {item.node_id: item for item in section_drafts}
    node_by_id = {item.node_id: item for item in nodes}
    unit_by_id = {unit.id: unit for unit in units}
    gaps = gap_review_service.list_gap_items(task_id)
    gap_count_by_node_id: dict[str, int] = {}
    for gap in gaps:
        gap_count_by_node_id[gap.node_id] = gap_count_by_node_id.get(gap.node_id, 0) + 1

    resolved_nodes: list[ResolvedNode] = []
    ready_count = 0
    risky_count = 0
    missing_count = 0

    for node in nodes:
        if not node.enabled:
            continue

        if node.content_mode == "fill":
            gap_count = gap_count_by_node_id.get(node.node_id, 0)
            resolved = _fill_to_resolved_node(
                node=node,
                fill_result=fill_by_node_id.get(node.node_id),
                unit_by_id=unit_by_id,
                gap_count=gap_count,
            )
        elif node.content_mode == "generate" and node.node_type == "section":
            gap_count = gap_count_by_node_id.get(node.node_id, 0)
            resolved = _section_to_resolved_node(
                node=node,
                draft=draft_by_node_id.get(node.node_id),
                gap_count=gap_count,
            )
        elif node.content_mode == "mixed" and node.node_type == "section":
            gap_count = gap_count_by_node_id.get(node.node_id, 0)
            descendant_fill_items = [
                result
                for result in fill_results
                if _is_descendant_node(result.node_id, node.node_id, node_by_id)
            ]
            resolved = _mixed_to_resolved_node(
                node=node,
                draft=draft_by_node_id.get(node.node_id),
                fill_items=descendant_fill_items,
                gap_count=gap_count,
            )
        else:
            resolved = ResolvedNode(
                task_id=node.task_id,
                node_id=node.node_id,
                node_title=node.title,
                node_type=node.node_type,
                content_mode=node.content_mode,
                level=node.level,
                parent_id=node.parent_id,
                resolved_status="skipped",
                render_payload={"type": "skipped"},
                source_result_type=None,
                source_result_id=None,
                gap_count=gap_count_by_node_id.get(node.node_id, 0),
            )

        if resolved.resolved_status == "ready":
            ready_count += 1
        elif resolved.resolved_status == "risky":
            risky_count += 1
        elif resolved.resolved_status == "missing":
            missing_count += 1
        resolved_nodes.append(resolved)

    built_at = datetime.now(timezone.utc).isoformat()
    if missing_count > 0:
        export_readiness: ExportReadiness = "blocked"
    elif risky_count > 0:
        export_readiness = "risky"
    else:
        export_readiness = "ready"

    summary = {
        "total_nodes": len(resolved_nodes),
        "ready_nodes": ready_count,
        "risky_nodes": risky_count,
        "missing_nodes": missing_count,
        "export_readiness": export_readiness,
    }

    payload = {
        "ok": True,
        "task_id": task_id,
        "built_at": built_at,
        "summary": summary,
        "node_count": len(resolved_nodes),
        "ready_count": ready_count,
        "risky_count": risky_count,
        "missing_count": missing_count,
        "nodes": [node.model_dump() for node in resolved_nodes],
        "gaps": [gap.model_dump() for gap in gaps],
    }
    resolved_template_repo.save_resolved_template(task_id, payload)
    return ResolvedTemplate.model_validate(payload)


def get_resolved_template(task_id: str) -> ResolvedTemplate:
    raw = resolved_template_repo.load_resolved_template(task_id)
    if not raw:
        return ResolvedTemplate(
            ok=True,
            task_id=task_id,
            built_at="",
            summary=ResolvedTemplateSummary(
                total_nodes=0,
                ready_nodes=0,
                risky_nodes=0,
                missing_nodes=0,
                export_readiness="blocked",
            ),
            node_count=0,
            ready_count=0,
            risky_count=0,
            missing_count=0,
            nodes=[],
            gaps=[],
        )
    if "summary" not in raw:
        ready_count = int(raw.get("ready_count") or 0)
        risky_count = int(raw.get("risky_count") or 0)
        missing_count = int(raw.get("missing_count") or 0)
        node_count = int(raw.get("node_count") or 0)
        if missing_count > 0:
            export_readiness: ExportReadiness = "blocked"
        elif risky_count > 0:
            export_readiness = "risky"
        else:
            export_readiness = "ready"
        raw["summary"] = {
            "total_nodes": node_count,
            "ready_nodes": ready_count,
            "risky_nodes": risky_count,
            "missing_nodes": missing_count,
            "export_readiness": export_readiness,
        }
    if "gaps" not in raw or not isinstance(raw.get("gaps"), list):
        raw["gaps"] = []
    nodes = raw.get("nodes")
    if isinstance(nodes, list):
        normalized_nodes: list[dict[str, Any]] = []
        for item in nodes:
            if not isinstance(item, dict):
                continue
            item.setdefault("level", 1)
            item.setdefault("parent_id", None)
            item.setdefault("source_result_type", None)
            item.setdefault("source_result_id", None)
            item.setdefault("gap_count", 0)
            normalized_nodes.append(item)
        raw["nodes"] = normalized_nodes
    return ResolvedTemplate.model_validate(raw)
