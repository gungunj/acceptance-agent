import json
import sys
from pathlib import Path
from typing import Optional

import typer

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent_core.orchestrator import workflows
from agent_core.domain import models

app = typer.Typer(help="acceptance-agent core CLI")


def _print_json(payload) -> None:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("parse-template")
def parse_template(
    task_id: str = typer.Option(..., "--task-id"),
    file_id: Optional[str] = typer.Option(None, "--file-id"),
):
    _print_json(workflows.parse_template(task_id=task_id, file_id=file_id))


@app.command("create-task")
def create_task(
    title: str = typer.Option(..., "--title"),
    description: str = typer.Option("", "--description"),
):
    payload = models.CreateTaskRequest(title=title, description=description)
    _print_json(workflows.create_task(payload))


@app.command("parse-materials")
def parse_materials(task_id: str = typer.Option(..., "--task-id")):
    _print_json(workflows.parse_materials(task_id=task_id))


@app.command("match-fill-nodes")
def match_fill_nodes(
    task_id: str = typer.Option(..., "--task-id"),
    top_n: int = typer.Option(5, "--top-n"),
    strategy: str = typer.Option("rule", "--strategy"),
):
    # Deterministic default command; strategy kept only for compatibility.
    if strategy != "rule":
        raise typer.BadParameter("CLI deterministic mode only supports --strategy rule")
    _print_json(workflows.match_fill_rules(task_id=task_id, top_n=top_n))


@app.command("match-fill-rules")
def match_fill_rules(
    task_id: str = typer.Option(..., "--task-id"),
    top_n: int = typer.Option(5, "--top-n"),
):
    _print_json(workflows.match_fill_rules(task_id=task_id, top_n=top_n))


@app.command("show-fill-node-matches")
def show_fill_node_matches(task_id: str = typer.Option(..., "--task-id")):
    _print_json(workflows.list_fill_matches(task_id=task_id))


@app.command("resolve-fill-nodes")
def resolve_fill_nodes(
    task_id: str = typer.Option(..., "--task-id"),
    top_n: int = typer.Option(5, "--top-n"),
    strategy: str = typer.Option("rule", "--strategy"),
):
    if strategy != "rule":
        raise typer.BadParameter("CLI deterministic mode only supports --strategy rule")
    _print_json(workflows.resolve_fill_nodes(task_id=task_id, top_n=top_n, strategy=strategy))


@app.command("generate-section-drafts")
def generate_section_drafts(
    task_id: str = typer.Option(..., "--task-id"),
    top_n: int = typer.Option(3, "--top-n"),
    strategy: str = typer.Option("rule", "--strategy"),
    force_llm_context: bool = typer.Option(False, "--force-llm-context"),
    force_context_local: bool = typer.Option(False, "--force-context-local"),
    llm_remote_only: bool = typer.Option(False, "--llm-remote-only"),
):
    if strategy != "rule":
        raise typer.BadParameter("CLI deterministic mode only supports --strategy rule")
    _print_json(
        workflows.generate_section_drafts(
            task_id=task_id,
            top_n=top_n,
            strategy=strategy,
            force_llm_context=force_llm_context,
            force_context_local=force_context_local,
            llm_remote_only=llm_remote_only,
        )
    )


@app.command("generate-gaps")
def generate_gaps(task_id: str = typer.Option(..., "--task-id")):
    _print_json(workflows.generate_gaps(task_id=task_id))


@app.command("build-resolved-template")
def build_resolved_template(task_id: str = typer.Option(..., "--task-id")):
    _print_json(workflows.build_resolved_template(task_id=task_id))


@app.command("export-markdown")
def export_markdown(
    task_id: str = typer.Option(..., "--task-id"),
    rebuild: bool = typer.Option(True, "--rebuild/--no-rebuild"),
):
    _print_json(workflows.export_markdown(task_id=task_id, rebuild=rebuild))


@app.command("export-docx")
def export_docx(
    task_id: str = typer.Option(..., "--task-id"),
    rebuild: bool = typer.Option(True, "--rebuild/--no-rebuild"),
):
    _print_json(workflows.export_docx(task_id=task_id, rebuild=rebuild))


@app.command("save-fill-results")
def save_fill_results(
    task_id: str = typer.Option(..., "--task-id"),
    input_path: str = typer.Option(..., "--input"),
):
    _print_json(workflows.save_fill_results(task_id=task_id, input_path=input_path))


@app.command("save-section-drafts")
def save_section_drafts(
    task_id: str = typer.Option(..., "--task-id"),
    input_path: str = typer.Option(..., "--input"),
):
    _print_json(workflows.save_section_drafts(task_id=task_id, input_path=input_path))


@app.command("save-template-nodes")
def save_template_nodes(
    task_id: str = typer.Option(..., "--task-id"),
    input_path: str = typer.Option(..., "--input"),
):
    _print_json(workflows.save_template_nodes(task_id=task_id, input_path=input_path))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
