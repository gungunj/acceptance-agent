from fastapi import APIRouter

from agent_core.domain.models import GapGenerationResponse, GapItem
from agent_core.orchestrator import workflows

router = APIRouter()


@router.post(
    "/tasks/{task_id}/generate-gaps",
    response_model=GapGenerationResponse,
)
def generate_gaps(task_id: str):
    return workflows.generate_gaps(task_id=task_id)


@router.get(
    "/tasks/{task_id}/gap-items",
    response_model=list[GapItem],
)
def list_gap_items(task_id: str):
    return workflows.list_gaps(task_id=task_id)
