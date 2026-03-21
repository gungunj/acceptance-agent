from typing import Optional

from fastapi import APIRouter, File, Form, Request, UploadFile

from agent_core.domain import models
from agent_core.orchestrator import workflows
from app.services import material_service

router = APIRouter()


@router.get("/health")
def health(request: Request):
    preflight = getattr(request.app.state, "preflight", None)
    warning_count = len(preflight.get("warnings", [])) if isinstance(preflight, dict) else 0
    error_count = len(preflight.get("errors", [])) if isinstance(preflight, dict) else 0
    return {
        "ok": error_count == 0,
        "service": "api",
        "status": "healthy" if error_count == 0 else "degraded",
        "preflight": {
            "provider": preflight.get("provider") if isinstance(preflight, dict) else None,
            "warning_count": warning_count,
            "error_count": error_count,
        },
    }


@router.get("/hello")
def hello():
    return {"message": "Hello from FastAPI", "service": "api", "ok": True}


@router.post("/tasks", response_model=models.Task)
def create_task(payload: models.CreateTaskRequest):
    return workflows.create_task(payload)


@router.get("/tasks", response_model=list[models.Task])
def list_tasks():
    return workflows.list_tasks()


@router.get("/tasks/{task_id}", response_model=models.Task)
def get_task(task_id: str):
    return workflows.get_task(task_id)


@router.post("/files/upload")
async def upload_files(task_id: str = Form(...), files: list[UploadFile] = File(...)):
    uploaded = await workflows.upload_files(task_id=task_id, files=files)
    return {
        "ok": True,
        "task_id": task_id,
        "uploaded_count": len(uploaded),
        "files": [record.model_dump() for record in uploaded],
    }


@router.patch("/tasks/{task_id}/files/{file_id}", response_model=models.Task)
def update_task_file_role(
    task_id: str, file_id: str, payload: models.UpdateFileRoleRequest
):
    return workflows.update_file_role(task_id, file_id, payload)


@router.post(
    "/tasks/{task_id}/files/{file_id}/parse-template",
    response_model=models.Task,
)
def parse_task_template(task_id: str, file_id: str):
    return workflows.parse_template(task_id=task_id, file_id=file_id)


@router.post(
    "/tasks/{task_id}/parse-template",
    response_model=models.ParseTemplateResponse,
)
def parse_task_template_nodes(task_id: str, file_id: Optional[str] = None):
    return workflows.parse_template(task_id=task_id, file_id=file_id)


@router.post("/tasks/{task_id}/normalize-template-semantics")
def normalize_task_template_semantics(task_id: str):
    return workflows.normalize_template_semantics(task_id)


@router.post("/tasks/{task_id}/build-material-embeddings")
def build_task_material_embeddings(task_id: str):
    return workflows.build_embeddings(task_id)


@router.get("/tasks/{task_id}/build-material-embeddings")
def build_task_material_embeddings_via_get(task_id: str):
    # Compatibility shortcut for browser/manual URL access.
    return workflows.build_embeddings(task_id)


@router.post("/tasks/{task_id}/index-material-embeddings")
def index_task_material_embeddings(task_id: str):
    return workflows.build_embeddings(task_id)


@router.get(
    "/tasks/{task_id}/template-nodes",
    response_model=list[models.TemplateNode],
)
def list_template_nodes(task_id: str):
    return workflows.list_template_nodes(task_id)


@router.patch(
    "/tasks/{task_id}/template-nodes/{node_id}",
    response_model=models.TemplateNode,
)
def patch_template_node(
    task_id: str, node_id: str, payload: models.UpdateTemplateNodeRequest
):
    return workflows.update_template_node(task_id, node_id, payload)


@router.post(
    "/tasks/{task_id}/confirm-template",
    response_model=models.Task,
)
def confirm_task_template(task_id: str):
    return workflows.confirm_template(task_id)


@router.post("/tasks/{task_id}/parse-materials", response_model=models.Task)
def parse_materials(task_id: str):
    return workflows.parse_materials(task_id)


@router.get(
    "/tasks/{task_id}/material-units",
    response_model=list[models.MaterialUnit],
)
def list_material_units(task_id: str):
    return workflows.list_material_units(task_id)


@router.post("/tasks/{task_id}/match-fields")
def match_fields(task_id: str, top_n: int = 5):
    return material_service.match_fields(task_id, top_n=top_n)


@router.post(
    "/tasks/{task_id}/match-fill-nodes",
    response_model=models.FillNodeMatchResponse,
)
def match_fill_nodes(task_id: str, top_n: int = 5, strategy: str = "hybrid"):
    return workflows.match_fill_nodes(task_id=task_id, top_n=top_n, strategy=strategy)


@router.get(
    "/tasks/{task_id}/fill-node-matches",
    response_model=list[models.FillNodeMatch],
)
def list_fill_node_matches(task_id: str):
    return workflows.list_fill_matches(task_id)


@router.post(
    "/tasks/{task_id}/resolve-fill-nodes",
    response_model=models.FillNodeResolveResponse,
)
def resolve_fill_nodes(task_id: str, top_n: int = 5, strategy: str = "hybrid"):
    return workflows.resolve_fill_nodes(task_id=task_id, top_n=top_n, strategy=strategy)


@router.get(
    "/tasks/{task_id}/fields",
    response_model=list[models.FieldSpec],
)
def list_fields(task_id: str):
    return material_service.list_fields(task_id)


@router.patch(
    "/tasks/{task_id}/fields/{field_id}",
    response_model=models.FieldSpec,
)
def update_field(task_id: str, field_id: str, payload: models.UpdateFieldRequest):
    return material_service.update_field(task_id, field_id, payload)
