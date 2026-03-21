import math
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

from app.repositories import embedding_repo
from app.services import llm_client, material_service


class MaterialEmbeddingItem(BaseModel):
    unit_id: str
    file_id: str
    unit_type: str
    title: str
    embedding_text: str
    vector: list[float]
    created_at: str


class EmbeddingBuildResponse(BaseModel):
    ok: bool = True
    task_id: str
    unit_count: int
    vector_dim: int
    generated_at: str


class SemanticRecallHit(BaseModel):
    unit_id: str
    file_id: str
    score: float
    retrieval_source: str = "embedding"


def build_material_unit_embedding_text(unit: material_service.MaterialUnit) -> str:
    unit_type = (unit.unit_type or "text").lower()
    title = (unit.title or "").strip()
    content = (unit.content or "").strip()
    metadata = unit.metadata if isinstance(unit.metadata, dict) else {}
    filename = str(metadata.get("filename") or "").strip()
    path = str(metadata.get("path") or "").strip()
    caption = str(metadata.get("caption") or "").strip()
    source_type = (unit.source_type or "docx").strip()

    if unit_type == "image":
        return "\n".join(
            [
                f"source_type: {source_type}",
                f"unit_type: {unit_type}",
                f"title: {title}",
                f"filename: {filename}",
                f"path: {path}",
                f"caption: {caption}",
            ]
        ).strip()

    return "\n".join(
        [
            f"source_type: {source_type}",
            f"unit_type: {unit_type}",
            f"title: {title}",
            f"filename: {filename}",
            f"content: {content[:6000]}",
        ]
    ).strip()


def build_node_query_embedding_text(node_query: material_service.FillNodeQuery) -> str:
    return "\n".join(
        [
            f"query: {node_query.query_text}",
            f"parent_section: {node_query.section_title or ''}",
            f"keywords: {', '.join(node_query.keywords)}",
            f"expected_unit_types: {', '.join(node_query.expected_unit_types)}",
        ]
    ).strip()


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for idx in range(size):
        lv = float(left[idx])
        rv = float(right[idx])
        dot += lv * rv
        left_norm += lv * lv
        right_norm += rv * rv
    denominator = math.sqrt(left_norm) * math.sqrt(right_norm)
    if denominator <= 0:
        return 0.0
    return float(dot / denominator)


def _load_index_items(task_id: str) -> list[MaterialEmbeddingItem]:
    raw = embedding_repo.load_embeddings(task_id)
    items = raw.get("items", [])
    if not isinstance(items, list):
        return []
    loaded: list[MaterialEmbeddingItem] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            loaded.append(MaterialEmbeddingItem.model_validate(item))
        except Exception:
            continue
    return loaded


def index_material_embeddings(task_id: str) -> EmbeddingBuildResponse:
    material_service.get_task(task_id)
    units = material_service.list_material_units(task_id)
    generated_at = datetime.now(timezone.utc).isoformat()
    items: list[dict] = []
    vector_dim = 0
    for unit in units:
        embedding_text = build_material_unit_embedding_text(unit)
        vector = llm_client.llm_client.embed_text(embedding_text[:8000])
        if vector:
            vector_dim = len(vector)
        items.append(
            MaterialEmbeddingItem(
                unit_id=unit.id,
                file_id=unit.file_id,
                unit_type=unit.unit_type or "text",
                title=unit.title or "Untitled",
                embedding_text=embedding_text[:4000],
                vector=vector,
                created_at=generated_at,
            ).model_dump()
        )

    embedding_repo.save_embeddings(
        task_id,
        {
            "task_id": task_id,
            "generated_at": generated_at,
            "vector_dim": vector_dim,
            "items": items,
        },
    )
    return EmbeddingBuildResponse(
        ok=True,
        task_id=task_id,
        unit_count=len(items),
        vector_dim=vector_dim,
        generated_at=generated_at,
    )


def ensure_material_embeddings(task_id: str) -> Optional[EmbeddingBuildResponse]:
    if _load_index_items(task_id):
        return None
    return index_material_embeddings(task_id)


def retrieve_by_embeddings(
    task_id: str,
    node_query: material_service.FillNodeQuery,
    top_k: int = 10,
) -> list[SemanticRecallHit]:
    items = _load_index_items(task_id)
    if not items:
        index_material_embeddings(task_id)
        items = _load_index_items(task_id)
    if not items:
        return []

    query_text = build_node_query_embedding_text(node_query)
    query_vector = llm_client.llm_client.embed_text(query_text[:8000])
    scored: list[tuple[float, MaterialEmbeddingItem]] = []
    for item in items:
        score = _cosine_similarity(query_vector, item.vector)
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    hits: list[SemanticRecallHit] = []
    for score, item in scored[: max(1, int(top_k))]:
        hits.append(
            SemanticRecallHit(
                unit_id=item.unit_id,
                file_id=item.file_id,
                score=float(score),
                retrieval_source="embedding",
            )
        )
    return hits
