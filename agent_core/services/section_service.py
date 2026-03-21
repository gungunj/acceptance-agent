from app.services import section_draft_service


def generate_section_drafts(task_id: str, top_n: int = 3, strategy: str = "rule"):
    return section_draft_service.generate_section_drafts(
        task_id=task_id,
        top_n=top_n,
        strategy=strategy,
    )


def list_section_drafts(task_id: str):
    return section_draft_service.list_section_drafts(task_id=task_id)
