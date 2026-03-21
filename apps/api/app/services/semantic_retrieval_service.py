from typing import Optional

from app.services import embedding_service, material_service

MaterialEmbeddingItem = embedding_service.MaterialEmbeddingItem
EmbeddingBuildResponse = embedding_service.EmbeddingBuildResponse
SemanticRecallHit = embedding_service.SemanticRecallHit


def build_material_embeddings(task_id: str) -> EmbeddingBuildResponse:
    return embedding_service.index_material_embeddings(task_id=task_id)


def semantic_recall(task_id: str, query_text: str, top_k: int = 8) -> list[SemanticRecallHit]:
    query = material_service.FillNodeQuery(
        query_text=query_text,
        section_title=None,
        keywords=[query_text],
        expected_unit_types=["text"],
    )
    return embedding_service.retrieve_by_embeddings(task_id=task_id, node_query=query, top_k=top_k)


def ensure_embeddings(task_id: str) -> Optional[EmbeddingBuildResponse]:
    return embedding_service.ensure_material_embeddings(task_id=task_id)
