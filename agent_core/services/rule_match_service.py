from app.services import material_service


def match_fill_rules(task_id: str, top_n: int = 5):
    # Deterministic-only entry: force rule strategy.
    return material_service.match_fill_nodes(task_id=task_id, top_n=top_n, strategy="rule")
