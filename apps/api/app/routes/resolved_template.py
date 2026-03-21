from fastapi import APIRouter

from agent_core.domain.models import ResolvedTemplate
from agent_core.orchestrator import workflows

router = APIRouter()


@router.post(
    "/tasks/{task_id}/build-resolved-template",
    response_model=ResolvedTemplate,
)
def build_resolved_template(task_id: str):
    return workflows.build_resolved_template(task_id=task_id)


@router.get(
    "/tasks/{task_id}/resolved-template",
    response_model=ResolvedTemplate,
)
def get_resolved_template(task_id: str):
    return workflows.get_resolved_template(task_id=task_id)
