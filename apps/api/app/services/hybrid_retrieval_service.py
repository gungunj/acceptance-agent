from typing import Optional

from pydantic import BaseModel

from app.services import embedding_service, material_service


class HybridRetrievedCandidate(BaseModel):
    unit_id: str
    file_id: str
    unit_type: str
    source_type: str
    title: str
    content: str
    rule_score: float = 0.0
    vector_score: Optional[float] = None
    retrieval_source: str = "rule"


class HybridRetrieveResult(BaseModel):
    candidates: list[HybridRetrievedCandidate]
    debug: dict[str, object]


def _rule_candidate_score(
    unit: material_service.MaterialUnit,
    node_query: material_service.FillNodeQuery,
) -> float:
    title = (unit.title or "").lower()
    content = (unit.content or "").lower()
    score = 0.0
    for keyword in node_query.keywords:
        lowered = keyword.lower()
        if lowered and lowered in title:
            score += 1.2
        if lowered and lowered in content:
            score += 0.8
    if node_query.section_title:
        section_lower = node_query.section_title.lower()
        if section_lower in title or section_lower in content:
            score += 1.0
    expected = {item.lower() for item in node_query.expected_unit_types}
    if expected and (unit.unit_type or "text").lower() in expected:
        score += 1.0
    return score


def hybrid_retrieve_candidates(
    task_id: str,
    node_query: material_service.FillNodeQuery,
    top_n: int = 12,
) -> HybridRetrieveResult:
    all_units = material_service.list_material_units(task_id)
    all_units_by_id = {unit.id: unit for unit in all_units}

    rule_units = material_service.retrieve_candidates(task_id, node_query)
    expanded_units = material_service._retrieve_rule_expanded_candidates(task_id, node_query)
    semantic_hits = embedding_service.retrieve_by_embeddings(
        task_id=task_id,
        node_query=node_query,
        top_k=max(8, int(top_n)),
    )
    semantic_score_by_id = {hit.unit_id: float(hit.score) for hit in semantic_hits}

    merged_ids: list[str] = []
    seen_ids: set[str] = set()
    for unit in rule_units + expanded_units:
        if unit.id in seen_ids:
            continue
        seen_ids.add(unit.id)
        merged_ids.append(unit.id)
    for hit in semantic_hits:
        if hit.unit_id in seen_ids:
            continue
        seen_ids.add(hit.unit_id)
        merged_ids.append(hit.unit_id)

    candidates: list[HybridRetrievedCandidate] = []
    for unit_id in merged_ids:
        unit = all_units_by_id.get(unit_id)
        if unit is None:
            continue
        in_rule = any(item.id == unit_id for item in rule_units)
        in_expanded = any(item.id == unit_id for item in expanded_units)
        in_embedding = unit_id in semantic_score_by_id
        sources: list[str] = []
        if in_rule:
            sources.append("rule")
        if in_expanded:
            sources.append("rule_expanded")
        if in_embedding:
            sources.append("embedding")
        if not sources:
            sources = ["rule"]

        candidates.append(
            HybridRetrievedCandidate(
                unit_id=unit.id,
                file_id=unit.file_id,
                unit_type=unit.unit_type or "text",
                source_type=unit.source_type or "docx",
                title=unit.title or "Untitled",
                content=unit.content or "",
                rule_score=_rule_candidate_score(unit, node_query),
                vector_score=semantic_score_by_id.get(unit.id),
                retrieval_source="+".join(dict.fromkeys(sources)),
            )
        )

    candidates.sort(
        key=lambda item: (
            item.rule_score + (item.vector_score or 0.0),
            item.vector_score or 0.0,
            item.rule_score,
        ),
        reverse=True,
    )

    return HybridRetrieveResult(
        candidates=candidates[: max(1, int(top_n))],
        debug={
            "rule_count": len(rule_units),
            "expanded_count": len(expanded_units),
            "embedding_count": len(semantic_hits),
            "merged_count": len(candidates),
        },
    )
