from fastapi import APIRouter

from agent_core.domain.models import SectionDraftGenerationResponse, SectionDraftResult
from agent_core.orchestrator import workflows

router = APIRouter()


@router.post(
    "/tasks/{task_id}/generate-section-drafts",
    response_model=SectionDraftGenerationResponse,
)
def generate_task_section_drafts(task_id: str, top_n: int = 3, strategy: str = "rule"):
    return workflows.generate_section_drafts(task_id=task_id, top_n=top_n, strategy=strategy)


@router.get(
    "/tasks/{task_id}/section-drafts",
    response_model=list[SectionDraftResult],
)
def get_task_section_drafts(task_id: str):
    return workflows.list_section_drafts(task_id=task_id)
