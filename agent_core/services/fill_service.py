from app.services import fill_review_service, material_service


def match_fill_nodes(task_id: str, top_n: int = 5, strategy: str = "rule"):
    return material_service.match_fill_nodes(task_id=task_id, top_n=top_n, strategy=strategy)


def resolve_fill_nodes(task_id: str, top_n: int = 5, strategy: str = "rule"):
    return material_service.resolve_fill_nodes(task_id=task_id, top_n=top_n, strategy=strategy)


def list_fill_matches(task_id: str):
    return material_service.list_fill_node_matches(task_id=task_id)


def list_fill_results(task_id: str):
    return fill_review_service.list_reviewable_fill_results(task_id=task_id)
