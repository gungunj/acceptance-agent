from app.services import material_service, semantic_retrieval_service


def build_material_embeddings(task_id: str):
    return semantic_retrieval_service.build_material_embeddings(task_id=task_id)


def match_fill_nodes(task_id: str, top_n: int = 5, strategy: str = "rule"):
    return material_service.match_fill_nodes(task_id=task_id, top_n=top_n, strategy=strategy)
