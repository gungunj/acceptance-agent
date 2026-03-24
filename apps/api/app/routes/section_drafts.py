from fastapi import APIRouter

from agent_core.domain.models import SectionDraftGenerationResponse, SectionDraftResult
from agent_core.orchestrator import workflows

router = APIRouter()


@router.post(
    "/tasks/{task_id}/generate-section-drafts",
    response_model=SectionDraftGenerationResponse,
)
def generate_task_section_drafts(
    task_id: str,
    top_n: int = 3,
    strategy: str = "rule",
    force_llm_context: bool = False,
    force_context_local: bool = False,
    llm_remote_only: bool = False,
):
    return workflows.generate_section_drafts(
        task_id=task_id,
        top_n=top_n,
        strategy=strategy,
        force_llm_context=force_llm_context,
        force_context_local=force_context_local,
        llm_remote_only=llm_remote_only,
    )


@router.get(
    "/tasks/{task_id}/section-drafts",
    response_model=list[SectionDraftResult],
)
def get_task_section_drafts(task_id: str):
    return workflows.list_section_drafts(task_id=task_id)
