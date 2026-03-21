"""Stable workflow entrypoints consumed by API and CLI."""
from typing import Optional

from app.services import material_service
from app.services.semantic_retrieval_service import build_material_embeddings

from agent_core.renderers import exporter
from agent_core.services import (
    fill_service,
    gap_service,
    resolved_service,
    rule_match_service,
    section_service,
    template_service,
    writeback_service,
)


def create_task(payload):
    return material_service.create_task(payload)


def list_tasks():
    return material_service.list_tasks()


def get_task(task_id: str):
    return material_service.get_task(task_id)


def upload_files(task_id: str, files):
    return material_service.upload_files_async(task_id=task_id, files=files)


def update_file_role(task_id: str, file_id: str, payload):
    return material_service.update_file_role(task_id=task_id, file_id=file_id, payload=payload)


def parse_template(task_id: str, file_id: Optional[str] = None):
    return template_service.parse_template(task_id=task_id, file_id=file_id)


def list_template_nodes(task_id: str):
    return template_service.list_template_nodes(task_id=task_id)


def update_template_node(task_id: str, node_id: str, payload):
    return template_service.update_template_node(task_id=task_id, node_id=node_id, payload=payload)


def confirm_template(task_id: str):
    return template_service.confirm_template(task_id=task_id)


def normalize_template_semantics(task_id: str):
    return template_service.normalize_template_semantics(task_id=task_id)


def parse_materials(task_id: str):
    return material_service.parse_materials(task_id=task_id)


def list_material_units(task_id: str):
    return material_service.list_material_units(task_id=task_id)


def build_embeddings(task_id: str):
    return build_material_embeddings(task_id=task_id)


def match_fill_nodes(task_id: str, top_n: int = 5, strategy: str = "rule"):
    return fill_service.match_fill_nodes(task_id=task_id, top_n=top_n, strategy=strategy)


def match_fill_rules(task_id: str, top_n: int = 5):
    return rule_match_service.match_fill_rules(task_id=task_id, top_n=top_n)


def list_fill_matches(task_id: str):
    return fill_service.list_fill_matches(task_id=task_id)


def resolve_fill_nodes(task_id: str, top_n: int = 5, strategy: str = "rule"):
    return fill_service.resolve_fill_nodes(task_id=task_id, top_n=top_n, strategy=strategy)


def list_fill_results(task_id: str):
    return fill_service.list_fill_results(task_id=task_id)


def generate_section_drafts(task_id: str, top_n: int = 3, strategy: str = "rule"):
    return section_service.generate_section_drafts(task_id=task_id, top_n=top_n, strategy=strategy)


def list_section_drafts(task_id: str):
    return section_service.list_section_drafts(task_id=task_id)


def generate_gaps(task_id: str):
    return gap_service.generate_gaps(task_id=task_id)


def list_gaps(task_id: str):
    return gap_service.list_gaps(task_id=task_id)


def build_resolved_template(task_id: str):
    return resolved_service.build_resolved_template(task_id=task_id)


def get_resolved_template(task_id: str):
    return resolved_service.get_resolved_template(task_id=task_id)


def export_markdown(task_id: str, rebuild: bool = True):
    return exporter.export_markdown(task_id=task_id, rebuild=rebuild)


def get_markdown_export(task_id: str):
    return exporter.get_markdown_export(task_id=task_id)


def export_html(task_id: str, rebuild: bool = False):
    return exporter.export_html(task_id=task_id, rebuild=rebuild)


def get_html_export(task_id: str):
    return exporter.get_html_export(task_id=task_id)


def export_docx(task_id: str, rebuild: bool = True):
    return exporter.export_docx(task_id=task_id, rebuild=rebuild)


def get_docx_export(task_id: str):
    return exporter.get_docx_export(task_id=task_id)


def save_fill_results(task_id: str, input_path: str):
    return writeback_service.save_fill_results(task_id=task_id, input_path=input_path)


def save_section_drafts(task_id: str, input_path: str):
    return writeback_service.save_section_drafts(task_id=task_id, input_path=input_path)


def save_template_nodes(task_id: str, input_path: str):
    return writeback_service.save_template_nodes(task_id=task_id, input_path=input_path)
