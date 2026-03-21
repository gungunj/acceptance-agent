from typing import Optional

from app.services import material_service, semantic_normalizer_service


def parse_template(task_id: str, file_id: Optional[str] = None):
    return material_service.parse_template_nodes(task_id=task_id, file_id=file_id)


def list_template_nodes(task_id: str):
    return material_service.list_template_nodes(task_id=task_id)


def update_template_node(task_id: str, node_id: str, payload):
    return material_service.update_template_node(task_id=task_id, node_id=node_id, payload=payload)


def confirm_template(task_id: str):
    return material_service.confirm_template(task_id=task_id)


def normalize_template_semantics(task_id: str):
    return semantic_normalizer_service.normalize_template_semantics(task_id=task_id)
