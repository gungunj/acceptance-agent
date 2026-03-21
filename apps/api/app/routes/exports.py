from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from agent_core.domain.models import ExportDocument
from agent_core.orchestrator import workflows

router = APIRouter()


@router.post(
    "/tasks/{task_id}/export-markdown",
    response_model=ExportDocument,
)
def export_task_markdown(task_id: str, rebuild: bool = True):
    return workflows.export_markdown(task_id=task_id, rebuild=rebuild)


@router.get(
    "/tasks/{task_id}/export-markdown",
    response_model=ExportDocument,
)
def get_task_markdown_export(task_id: str):
    try:
        return workflows.get_markdown_export(task_id=task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/tasks/{task_id}/export-html",
    response_model=ExportDocument,
)
def export_task_html(task_id: str, rebuild: bool = False):
    return workflows.export_html(task_id=task_id, rebuild=rebuild)


@router.get(
    "/tasks/{task_id}/export-html",
    response_model=ExportDocument,
)
def get_task_html_export(task_id: str):
    try:
        return workflows.get_html_export(task_id=task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/tasks/{task_id}/export-word",
    response_model=ExportDocument,
)
def export_task_word(task_id: str, rebuild: bool = True):
    return workflows.export_docx(task_id=task_id, rebuild=rebuild)


@router.get(
    "/tasks/{task_id}/export-word",
    response_model=ExportDocument,
)
def get_task_word_export(task_id: str):
    try:
        return workflows.get_docx_export(task_id=task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/export-word/download")
def download_task_word_export(task_id: str):
    try:
        result = workflows.get_docx_export(task_id=task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        path=result.file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=result.filename,
    )


# Backward-compatible alias: /export-docx
@router.post(
    "/tasks/{task_id}/export-docx",
    response_model=ExportDocument,
)
def export_task_docx_alias(task_id: str, rebuild: bool = True):
    return workflows.export_docx(task_id=task_id, rebuild=rebuild)


@router.get(
    "/tasks/{task_id}/export-docx",
    response_model=ExportDocument,
)
def get_task_docx_alias(task_id: str):
    try:
        return workflows.get_docx_export(task_id=task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/export-docx/download")
def download_task_docx_alias(task_id: str):
    try:
        result = workflows.get_docx_export(task_id=task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        path=result.file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=result.filename,
    )
