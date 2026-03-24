from app.services import section_draft_service


def generate_section_drafts(
    task_id: str,
    top_n: int = 3,
    strategy: str = "rule",
    force_llm_context: bool = False,
    force_context_local: bool = False,
    llm_remote_only: bool = False,
):
    return section_draft_service.generate_section_drafts(
        task_id=task_id,
        top_n=top_n,
        strategy=strategy,
        force_llm_context=force_llm_context,
        force_context_local=force_context_local,
        llm_remote_only=llm_remote_only,
    )


def list_section_drafts(task_id: str):
    return section_draft_service.list_section_drafts(task_id=task_id)
