from pathlib import Path
from typing import Literal, Optional
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI()
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


class Task(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: Literal["pending"] = "pending"
    files: list["UploadedFileRecord"] = Field(default_factory=list)


class UploadedFileRecord(BaseModel):
    file_id: str
    task_id: str
    filename: Optional[str] = None
    content_type: Optional[str] = None
    size: int
    path: str


TASKS: list[Task] = []


def find_task(task_id: str) -> Task:
    for task in TASKS:
        if task.id == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True, "service": "api", "status": "healthy"}


@app.get("/hello")
def hello():
    return {
        "message": "Hello from FastAPI",
        "service": "api",
        "ok": True,
    }


@app.post("/tasks", response_model=Task)
def create_task(payload: CreateTaskRequest):
    task = Task(
        id=str(uuid4()),
        title=payload.title,
        description=payload.description,
    )
    TASKS.append(task)
    return task


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: str):
    return find_task(task_id)


@app.post("/files/upload")
async def upload_file(task_id: str = Form(...), file: UploadFile = File(...)):
    task = find_task(task_id)
    file_id = str(uuid4())
    suffix = Path(file.filename or "").suffix
    stored_name = f"{file_id}{suffix}"
    stored_path = UPLOAD_DIR / stored_name
    content = await file.read()
    stored_path.write_bytes(content)

    uploaded_file = UploadedFileRecord(
        file_id=file_id,
        task_id=task_id,
        filename=file.filename,
        content_type=file.content_type,
        size=len(content),
        path=f"uploads/{stored_name}",
    )
    task.files.append(uploaded_file)

    return {
        "ok": True,
        "task_id": task_id,
        "file": uploaded_file.model_dump(),
    }
