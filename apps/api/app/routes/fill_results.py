from fastapi import APIRouter

from agent_core.domain.models import ReviewableFillNodeResult
from agent_core.orchestrator import workflows

router = APIRouter()


@router.get(
    "/tasks/{task_id}/fill-node-results",
    response_model=list[ReviewableFillNodeResult],
)
def get_fill_node_results(task_id: str):
    return workflows.list_fill_results(task_id=task_id)
