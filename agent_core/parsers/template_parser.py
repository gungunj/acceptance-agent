from typing import Optional

from app.services import material_service


def parse_template(task_id: str, file_id: Optional[str] = None):
    return material_service.parse_template_nodes(task_id=task_id, file_id=file_id)


def parse_materials(task_id: str):
    return material_service.parse_materials(task_id=task_id)
