from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.repositories import section_draft_repo
from app.services import material_service

DraftStatus = Literal["ready", "risky", "missing"]


class SectionQuery(BaseModel):
    query_text: str
    parent_title: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    expected_unit_types: list[str] = Field(default_factory=lambda: ["text", "table_row"])


class SectionCandidate(BaseModel):
    unit_id: str
    file_id: str
    title: str
    unit_type: str
    score: int
    reason: str


class InlineAsset(BaseModel):
    type: Literal["image"] = "image"
    unit_id: str
    path: Optional[str] = None
    caption: Optional[str] = None
    position: Literal["after_text", "appendix"] = "after_text"


class SectionDraftResult(BaseModel):
    task_id: str
    node_id: str
    node_title: str
    selected_unit_ids: list[str] = Field(default_factory=list)
    query_text: str
    draft_text: str
    inline_assets: list[InlineAsset] = Field(default_factory=list)
    evidence_unit_ids: list[str] = Field(default_factory=list)
    generation_confidence: Optional[float] = None
    llm_trace_id: Optional[str] = None
    draft_status: DraftStatus
    risk_note: Optional[str] = None
    manual_action: Optional[str] = None


class SectionDraftGenerationResponse(BaseModel):
    ok: bool = True
    task_id: str
    result_count: int
    ready_count: int
    risky_count: int
    missing_count: int
    generated_at: str
    results: list[SectionDraftResult]


def get_generate_nodes(task_id: str) -> list[material_service.TemplateNode]:
    nodes = material_service.list_template_nodes(task_id)
    return [
        node
        for node in nodes
        if node.node_type == "section" and node.content_mode == "generate" and node.enabled
    ]


def _tokenize(*parts: Optional[str]) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        raw = str(part).strip()
        if not raw:
            continue
        segments = [raw]
        segments.extend(raw.replace("（", " ").replace("）", " ").replace("/", " ").split(" "))
        for segment in segments:
            token = segment.strip()
            if len(token) < 2:
                continue
            lowered = token.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            keywords.append(token)
    return keywords


def build_section_query(
    node: material_service.TemplateNode, all_nodes: list[material_service.TemplateNode]
) -> SectionQuery:
    node_by_id = {item.node_id: item for item in all_nodes}
    parent_title: Optional[str] = None
    parent_id = node.parent_id
    while parent_id:
        parent = node_by_id.get(parent_id)
        if not parent:
            break
        if parent.node_type == "section":
            parent_title = parent.title
            break
        parent_id = parent.parent_id

    parser_hint = None
    if node.parser_notes and isinstance(node.parser_notes, dict):
        parser_hint = str(node.parser_notes.get("hint") or "").strip() or None

    query_text = node.title if not parent_title else f"{parent_title} / {node.title}"
    keywords = _tokenize(node.title, parent_title, parser_hint, f"level{node.level}")
    return SectionQuery(
        query_text=query_text,
        parent_title=parent_title,
        keywords=keywords,
        expected_unit_types=["text", "table_row"],
    )


def retrieve_section_candidates(task_id: str, section_query: SectionQuery) -> list[material_service.MaterialUnit]:
    units = material_service.list_material_units(task_id)
    if not units:
        return []

    expected = {item.lower() for item in section_query.expected_unit_types}
    recalled: list[material_service.MaterialUnit] = []
    for unit in units:
        title = (unit.title or "").lower()
        content = (unit.content or "").lower()
        unit_type = (unit.unit_type or "text").lower()

        # image units are not prioritized for generate sections.
        if unit_type == "image":
            continue

        hit = False
        for keyword in section_query.keywords:
            lowered = keyword.lower()
            if lowered in title or lowered in content:
                hit = True
                break
        if section_query.parent_title:
            parent_lower = section_query.parent_title.lower()
            if parent_lower in title or parent_lower in content:
                hit = True
        if unit_type in expected:
            hit = True

        if hit:
            recalled.append(unit)

    if not recalled:
        fallback = [unit for unit in units if (unit.unit_type or "text").lower() != "image"]
        return fallback[: min(8, len(fallback))]
    return recalled


def _merge_section_candidates(
    rule_units: list[material_service.MaterialUnit],
    semantic_hits: list[tuple[str, float]],
    all_units_by_id: dict[str, material_service.MaterialUnit],
) -> list[material_service.MaterialUnit]:
    ordered: list[material_service.MaterialUnit] = []
    seen: set[str] = set()
    for unit in rule_units:
        if unit.id in seen:
            continue
        seen.add(unit.id)
        ordered.append(unit)
    for unit_id, _ in semantic_hits:
        unit = all_units_by_id.get(unit_id)
        if not unit or unit.id in seen:
            continue
        if (unit.unit_type or "text").lower() == "image":
            continue
        seen.add(unit.id)
        ordered.append(unit)
    return ordered


def _unit_asset_path(unit: material_service.MaterialUnit) -> Optional[str]:
    if not isinstance(unit.metadata, dict):
        return None
    for key in ("path", "file_path", "asset_path", "url"):
        value = unit.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def retrieve_section_image_candidates(
    task_id: str, section_query: SectionQuery
) -> list[material_service.MaterialUnit]:
    units = material_service.list_material_units(task_id)
    if not units:
        return []

    recalled: list[material_service.MaterialUnit] = []
    for unit in units:
        unit_type = (unit.unit_type or "").lower()
        if unit_type != "image":
            continue

        title = (unit.title or "").lower()
        content = (unit.content or "").lower()
        metadata_text = ""
        if isinstance(unit.metadata, dict):
            metadata_text = " ".join(
                str(item).lower()
                for item in (
                    unit.metadata.get("filename"),
                    unit.metadata.get("path"),
                    unit.metadata.get("caption"),
                )
                if item is not None
            )

        hit = False
        for keyword in section_query.keywords:
            lowered = keyword.lower()
            if lowered in title or lowered in content or lowered in metadata_text:
                hit = True
                break
        if section_query.parent_title and section_query.parent_title.lower() in metadata_text:
            hit = True
        if hit:
            recalled.append(unit)

    if recalled:
        return recalled
    return [unit for unit in units if (unit.unit_type or "").lower() == "image"][:2]


def _rank_image_candidates(
    section_query: SectionQuery,
    candidates: list[material_service.MaterialUnit],
    top_n: int = 2,
) -> list[material_service.MaterialUnit]:
    scored: list[tuple[int, material_service.MaterialUnit]] = []
    for unit in candidates:
        score = 0
        title = (unit.title or "").lower()
        metadata_path = (_unit_asset_path(unit) or "").lower()
        for keyword in section_query.keywords:
            lowered = keyword.lower()
            if lowered in title:
                score += 3
            if lowered in metadata_path:
                score += 2
        if section_query.parent_title and section_query.parent_title.lower() in metadata_path:
            score += 1
        if score <= 0:
            score = 1
        scored.append((score, unit))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [unit for _, unit in scored[: max(0, int(top_n))]]


def attach_images_to_section_draft(
    section_query: SectionQuery,
    image_candidates: list[material_service.MaterialUnit],
    top_n: int = 2,
) -> list[InlineAsset]:
    selected_images = _rank_image_candidates(section_query, image_candidates, top_n=top_n)
    assets: list[InlineAsset] = []
    for unit in selected_images:
        assets.append(
            InlineAsset(
                type="image",
                unit_id=unit.id,
                path=_unit_asset_path(unit),
                caption=(unit.title or "").strip() or None,
                position="after_text",
            )
        )
    return assets


def _rank_section_candidates(
    node: material_service.TemplateNode,
    section_query: SectionQuery,
    candidates: list[material_service.MaterialUnit],
    top_n: int = 3,
) -> list[SectionCandidate]:
    expected = {item.lower() for item in section_query.expected_unit_types}
    parent_lower = (section_query.parent_title or "").lower()
    node_title_lower = node.title.lower()

    ranked: list[SectionCandidate] = []
    for unit in candidates:
        score = 0
        reasons: list[str] = []
        title = unit.title or ""
        content = unit.content or ""
        title_lower = title.lower()
        content_lower = content.lower()
        unit_type = (unit.unit_type or "text").lower()

        if node_title_lower and node_title_lower in title_lower:
            score += 3
            reasons.append("title_hit:+3")
        if node_title_lower and node_title_lower in content_lower:
            score += 2
            reasons.append("content_hit:+2")
        if parent_lower and (parent_lower in title_lower or parent_lower in content_lower):
            score += 2
            reasons.append("parent_hit:+2")
        if expected and unit_type in expected:
            score += 1
            reasons.append("type_pref:+1")
        if title and title.strip().lower() not in {"untitled", "目录"}:
            score += 1
            reasons.append("useful_title:+1")

        if score <= 0:
            continue
        ranked.append(
            SectionCandidate(
                unit_id=unit.id,
                file_id=unit.file_id,
                title=title or "Untitled",
                unit_type=unit.unit_type or "text",
                score=score,
                reason=", ".join(reasons),
            )
        )

    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[: max(1, int(top_n))]


def generate_section_draft(
    node: material_service.TemplateNode,
    section_query: SectionQuery,
    selected_units: list[material_service.MaterialUnit],
) -> tuple[str, DraftStatus, Optional[str], Optional[str], float, Optional[str], list[str]]:
    evidence_unit_ids = [unit.id for unit in selected_units]
    if not selected_units:
        return (
            "",
            "missing",
            "未召回到可用素材，章节草稿无法生成。",
            "请补充与该章节相关的素材后重新生成。",
            0.0,
            None,
            [],
        )

    snippets: list[str] = []
    for unit in selected_units:
        content = (unit.content or "").strip()
        if not content:
            continue
        trimmed = content[:280].strip()
        snippets.append(f"- {unit.title}: {trimmed}")

    if not snippets:
        return (
            "",
            "missing",
            "候选素材内容为空，无法形成可审阅草稿。",
            "请检查素材解析结果或重新上传素材。",
            0.0,
            None,
            evidence_unit_ids,
        )

    from app.services import llm_client

    draft_text = ""
    confidence = 0.0
    llm_trace_id: Optional[str] = None
    if llm_client.llm_client.enabled:
        system_prompt = (
            "你是项目验收文档章节草稿助手。请基于证据生成结构完整、可直接审阅的章节草稿。"
            "输出 JSON: {\"draft_text\":\"...\",\"confidence\":0-1}。"
            "优先完整成文，但不要输出与证据矛盾的事实。"
        )
        user_prompt = (
            f"node_title={node.title}\nquery={section_query.query_text}\n"
            f"evidences:\n" + "\n".join(snippets[:6])
        )
        result = llm_client.llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        llm_trace_id = result.trace_id
        try:
            import json

            payload = json.loads(result.text or "{}")
        except Exception:
            payload = {}
        draft_text = str(payload.get("draft_text") or "").strip()
        try:
            confidence = float(payload.get("confidence"))
        except Exception:
            confidence = result.confidence
        confidence = max(0.0, min(1.0, confidence))

    if not draft_text:
        draft_text = (
            f"{node.title}\n\n"
            f"根据当前任务素材，整理与“{section_query.query_text}”相关的信息如下：\n"
            + "\n".join(snippets[:5])
            + "\n\n"
            "以上内容为自动汇总草稿，请人工复核关键事实与数值后再确认。"
        )
        confidence = max(confidence, 0.55)

    if len(selected_units) >= 2:
        return draft_text, "ready", None, None, confidence, llm_trace_id, evidence_unit_ids
    return (
        draft_text,
        "risky",
        "可用素材较少，草稿覆盖度可能不足。",
        "建议补充同章节素材，或人工扩写草稿内容。",
        confidence,
        llm_trace_id,
        evidence_unit_ids,
    )


def generate_section_drafts(task_id: str, top_n: int = 3, strategy: str = "rule") -> SectionDraftGenerationResponse:
    material_service.get_task(task_id)
    all_nodes = material_service.list_template_nodes(task_id)
    generate_nodes = get_generate_nodes(task_id)
    all_units = material_service.list_material_units(task_id)
    unit_by_id = {unit.id: unit for unit in all_units}

    results: list[SectionDraftResult] = []
    ready_count = 0
    risky_count = 0
    missing_count = 0

    for node in generate_nodes:
        section_query = build_section_query(node, all_nodes)
        recalled = retrieve_section_candidates(task_id, section_query)
        if strategy == "hybrid":
            from app.services import semantic_retrieval_service

            semantic_hits_raw = semantic_retrieval_service.semantic_recall(
                task_id=task_id,
                query_text=section_query.query_text,
                top_k=max(8, int(top_n) * 2),
            )
            semantic_hits = [(item.unit_id, item.score) for item in semantic_hits_raw]
            recalled = _merge_section_candidates(
                rule_units=recalled,
                semantic_hits=semantic_hits,
                all_units_by_id=unit_by_id,
            )

        ranked = _rank_section_candidates(node, section_query, recalled, top_n=top_n)
        selected_unit_ids = [item.unit_id for item in ranked]
        selected_units = [unit_by_id[unit_id] for unit_id in selected_unit_ids if unit_id in unit_by_id]
        image_candidates = retrieve_section_image_candidates(task_id, section_query)
        inline_assets = attach_images_to_section_draft(section_query, image_candidates, top_n=2)

        (
            draft_text,
            draft_status,
            risk_note,
            manual_action,
            generation_confidence,
            llm_trace_id,
            evidence_unit_ids,
        ) = generate_section_draft(
            node=node,
            section_query=section_query,
            selected_units=selected_units,
        )
        if draft_status == "missing" and inline_assets:
            draft_status = "risky"
            if not risk_note:
                risk_note = "仅召回到章节配图，正文证据不足。"
            if not manual_action:
                manual_action = "请补充可用于正文生成的文本素材。"
        if draft_status == "ready":
            ready_count += 1
        elif draft_status == "risky":
            risky_count += 1
        else:
            missing_count += 1

        results.append(
            SectionDraftResult(
                task_id=task_id,
                node_id=node.node_id,
                node_title=node.title,
                selected_unit_ids=selected_unit_ids,
                query_text=section_query.query_text,
                draft_text=draft_text,
                inline_assets=inline_assets,
                evidence_unit_ids=evidence_unit_ids,
                generation_confidence=generation_confidence,
                llm_trace_id=llm_trace_id,
                draft_status=draft_status,
                risk_note=risk_note,
                manual_action=manual_action,
            )
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    section_draft_repo.save_section_draft_results(
        task_id=task_id,
        results=[item.model_dump() for item in results],
        generated_at=generated_at,
    )
    return SectionDraftGenerationResponse(
        ok=True,
        task_id=task_id,
        result_count=len(results),
        ready_count=ready_count,
        risky_count=risky_count,
        missing_count=missing_count,
        generated_at=generated_at,
        results=results,
    )


def list_section_drafts(task_id: str) -> list[SectionDraftResult]:
    raw = section_draft_repo.list_section_draft_results(task_id)
    results: list[SectionDraftResult] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            results.append(SectionDraftResult.model_validate(item))
        except Exception:
            continue
    return results
