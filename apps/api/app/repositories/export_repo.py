from pathlib import Path
from typing import Literal, Optional

API_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = API_ROOT / "data"
EXPORTS_DIR = DATA_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

ExportFormat = Literal["markdown", "html", "word"]


def _extension(fmt: ExportFormat) -> str:
    if fmt == "markdown":
        return "md"
    if fmt == "html":
        return "html"
    return "docx"


def export_path(task_id: str, fmt: ExportFormat) -> Path:
    return EXPORTS_DIR / f"{task_id}.{_extension(fmt)}"


def save_export_content(task_id: str, fmt: ExportFormat, content: str) -> Path:
    path = export_path(task_id, fmt)
    path.write_text(content, encoding="utf-8")
    return path


def load_export_content(task_id: str, fmt: ExportFormat) -> Optional[str]:
    path = export_path(task_id, fmt)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
