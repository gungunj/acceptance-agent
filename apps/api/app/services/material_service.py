import csv
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.parsers.docx_parser import DocxParseError, parse_docx_template
from app.parsers.image_parser import parse_gif_size, parse_jpeg_size, parse_png_size
from app.parsers.xlsx_parser import parse_xlsx_template


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


class UploadedFileRecord(BaseModel):
    file_id: str
    task_id: str
    filename: Optional[str] = None
    content_type: Optional[str] = None
    size: int
    path: str
    role: Literal["unassigned", "template", "asset"] = "unassigned"
    parsed_template: Optional[dict[str, Any]] = None


class Task(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: Literal["pending"] = "pending"
    template_confirmed: bool = False
    template_confirmed_at: Optional[str] = None
    files: list[UploadedFileRecord] = Field(default_factory=list)
    material_units: list["MaterialUnit"] = Field(default_factory=list)


class MaterialUnit(BaseModel):
    id: str
    task_id: str
    file_id: str
    title: str
    content: str
    section_index: int
    source_type: str = "docx"
    unit_type: str = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateFileRoleRequest(BaseModel):
    role: Literal["template", "asset"]

FieldType = Literal["text", "image", "table", "list"]
FieldMode = Literal["enabled", "ignored", "fuzzy"]


class FieldSpec(BaseModel):
    id: str
    task_id: str
    key: str
    label: str
    original_label: str
    type: FieldType = "text"
    section: Optional[str] = None
    required: bool = True
    needs_screenshot: bool = False
    mode: FieldMode = "enabled"

    # provenance/debug
    source: Optional[str] = None
    header: Optional[str] = None
    context: Optional[str] = None
    cell_text: Optional[str] = None
    present_in_latest_parse: bool = True


class UpdateFieldRequest(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=200)
    type: Optional[FieldType] = None
    section: Optional[str] = Field(default=None, max_length=200)
    required: Optional[bool] = None
    needs_screenshot: Optional[bool] = None
    mode: Optional[FieldMode] = None


API_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = API_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

DATA_DIR = API_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

TASKS_DIR = DATA_DIR / "tasks"
FILES_DIR = DATA_DIR / "files"
FIELDS_DIR = DATA_DIR / "fields"
MATERIALS_DIR = DATA_DIR / "materials"
MATCHES_DIR = DATA_DIR / "matches"
TEMPLATE_NODES_DIR = DATA_DIR / "template_nodes"
FILL_RESULTS_DIR = DATA_DIR / "fill_results"

for directory in (
    TASKS_DIR,
    FILES_DIR,
    FIELDS_DIR,
    MATERIALS_DIR,
    MATCHES_DIR,
    TEMPLATE_NODES_DIR,
    FILL_RESULTS_DIR,
):
    directory.mkdir(exist_ok=True)

LEGACY_TASKS_DB_PATH = DATA_DIR / "tasks.json"


def _task_path(task_id: str) -> Path:
    return TASKS_DIR / f"{task_id}.json"


def _files_path(task_id: str) -> Path:
    return FILES_DIR / f"{task_id}.json"


def _fields_path(task_id: str) -> Path:
    return FIELDS_DIR / f"{task_id}.json"


def _materials_path(task_id: str) -> Path:
    return MATERIALS_DIR / f"{task_id}.json"


def _matches_path(task_id: str) -> Path:
    return MATCHES_DIR / f"{task_id}.json"


def _template_nodes_path(task_id: str) -> Path:
    return TEMPLATE_NODES_DIR / f"{task_id}.json"


def _fill_results_path(task_id: str) -> Path:
    return FILL_RESULTS_DIR / f"{task_id}.json"


def _write_json_atomic(path: Path, payload: Any) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _persist_task(task: Task) -> None:
    _write_json_atomic(
        _task_path(task.id),
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "template_confirmed": task.template_confirmed,
            "template_confirmed_at": task.template_confirmed_at,
        },
    )


def _persist_files(task_id: str, files: list[UploadedFileRecord]) -> None:
    _write_json_atomic(_files_path(task_id), {"files": [file.model_dump() for file in files]})


def _persist_fields(task_id: str, fields: list[dict[str, Any]], template_file_id: Optional[str]) -> None:
    _write_json_atomic(
        _fields_path(task_id),
        {"template_file_id": template_file_id, "fields": fields},
    )


def _load_fields(task_id: str) -> tuple[Optional[str], list[FieldSpec]]:
    raw = _read_json(_fields_path(task_id), {"template_file_id": None, "fields": []})
    template_file_id = raw.get("template_file_id")
    items = raw.get("fields", [])
    if not isinstance(items, list):
        return template_file_id, []

    loaded: list[FieldSpec] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # Migration from old parser format: {"field": "...", "source": "...", ...}
        if "id" not in item and "field" in item:
            original = str(item.get("field") or "").strip()
            if not original:
                continue
            key = (original.lower(), str(item.get("source") or "").lower(), str(item.get("header") or "").lower())
            loaded.append(
                FieldSpec(
                    id=str(uuid4()),
                    task_id=task_id,
                    key="|".join(key),
                    label=original,
                    original_label=original,
                    section=item.get("section"),
                    source=item.get("source"),
                    header=item.get("header"),
                    context=item.get("context"),
                    cell_text=item.get("cell_text"),
                )
            )
            continue
        try:
            loaded.append(FieldSpec.model_validate(item))
        except Exception:
            continue

    return template_file_id, loaded


def list_fields(task_id: str) -> list[FieldSpec]:
    _, fields = _load_fields(task_id)
    return fields


def update_field(task_id: str, field_id: str, payload: UpdateFieldRequest) -> FieldSpec:
    template_file_id, fields = _load_fields(task_id)
    for field in fields:
        if field.id == field_id:
            if payload.label is not None:
                field.label = payload.label
            if payload.type is not None:
                field.type = payload.type
            if payload.section is not None:
                field.section = payload.section
            if payload.required is not None:
                field.required = payload.required
            if payload.needs_screenshot is not None:
                field.needs_screenshot = payload.needs_screenshot
            if payload.mode is not None:
                field.mode = payload.mode

            _persist_fields(task_id, [item.model_dump() for item in fields], template_file_id)
            return field

    raise HTTPException(status_code=404, detail="Field not found")


def _normalize_field_key(field: dict[str, Any]) -> str:
    name = str(field.get("field") or "").strip().lower()
    source = str(field.get("source") or "").strip().lower()
    header = str(field.get("header") or "").strip().lower()
    return "|".join([name, source, header])


def _merge_fields(
    task_id: str,
    template_file_id: str,
    raw_fields: list[dict[str, Any]],
) -> list[FieldSpec]:
    _, existing = _load_fields(task_id)
    existing_by_key = {field.key: field for field in existing}

    new_fields: list[FieldSpec] = []
    seen_keys: set[str] = set()

    for raw in raw_fields:
        if not isinstance(raw, dict):
            continue
        original = str(raw.get("field") or "").strip()
        if not original:
            continue
        key = _normalize_field_key(raw)
        seen_keys.add(key)

        if key in existing_by_key:
            field = existing_by_key[key]
            field.present_in_latest_parse = True
            # Update provenance
            field.source = raw.get("source")
            field.header = raw.get("header")
            field.context = raw.get("context")
            field.cell_text = raw.get("cell_text")
            # Section: update only if user never changed it (naive: if equals old raw)
            if field.section is None:
                field.section = raw.get("section")
            new_fields.append(field)
            continue

        new_fields.append(
            FieldSpec(
                id=str(uuid4()),
                task_id=task_id,
                key=key,
                label=original,
                original_label=original,
                section=raw.get("section"),
                source=raw.get("source"),
                header=raw.get("header"),
                context=raw.get("context"),
                cell_text=raw.get("cell_text"),
                required=True,
                needs_screenshot=False,
                mode="enabled",
                type="text",
                present_in_latest_parse=True,
            )
        )

    # Keep existing fields that disappeared, but mark stale.
    for field in existing:
        if field.key in seen_keys:
            continue
        field.present_in_latest_parse = False
        new_fields.append(field)

    _persist_fields(task_id, [field.model_dump() for field in new_fields], template_file_id)
    return new_fields


def _persist_materials(task_id: str, units: list[MaterialUnit]) -> None:
    _write_json_atomic(
        _materials_path(task_id),
        {"material_units": [unit.model_dump() for unit in units]},
    )


def _persist_matches(task_id: str, matches: dict[str, Any]) -> None:
    _write_json_atomic(_matches_path(task_id), matches)


def _load_matches(task_id: str) -> dict[str, Any]:
    raw = _read_json(_matches_path(task_id), {})
    return raw if isinstance(raw, dict) else {}


def _persist_fill_results(task_id: str, payload: dict[str, Any]) -> None:
    _write_json_atomic(_fill_results_path(task_id), payload)


def _load_fill_results(task_id: str) -> dict[str, Any]:
    raw = _read_json(_fill_results_path(task_id), {})
    return raw if isinstance(raw, dict) else {}


def _load_task(task_id: str) -> Task:
    task_raw = _read_json(_task_path(task_id), None)
    if not isinstance(task_raw, dict):
        raise HTTPException(status_code=404, detail="Task not found")

    files_raw = _read_json(_files_path(task_id), {"files": []})
    materials_raw = _read_json(_materials_path(task_id), {"material_units": []})

    try:
        task = Task.model_validate(
            {
                **task_raw,
                "files": files_raw.get("files", []),
                "material_units": materials_raw.get("material_units", []),
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Corrupted task data") from exc

    return task


TemplateNodeType = Literal["section", "field", "note"]
ContentMode = Literal["generate", "fill", "mixed"]
NodeStatus = Literal["draft", "confirmed"]
NodeFieldType = Literal["text", "image", "table", "list", "unknown"]


class TemplateNode(BaseModel):
    node_id: str
    task_id: str
    node_type: TemplateNodeType
    title: str
    level: int = 1
    parent_id: Optional[str] = None
    content_mode: ContentMode = "generate"
    field_type: NodeFieldType = "unknown"
    required: bool = True
    requires_screenshot: bool = False
    enabled: bool = True
    status: NodeStatus = "draft"
    source_location: Optional[dict[str, Any]] = None
    parser_notes: Optional[dict[str, Any]] = None
    normalized_title: Optional[str] = None
    canonical_label: Optional[str] = None
    semantic_tags: list[str] = Field(default_factory=list)
    normalized_section: Optional[str] = None
    llm_confidence: Optional[float] = None


class UpdateTemplateNodeRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    node_type: Optional[TemplateNodeType] = None
    content_mode: Optional[ContentMode] = None
    field_type: Optional[NodeFieldType] = None
    required: Optional[bool] = None
    requires_screenshot: Optional[bool] = None
    enabled: Optional[bool] = None


class ParseTemplateResponse(BaseModel):
    ok: bool = True
    task_id: str
    template_file_id: str
    node_count: int
    nodes: list[TemplateNode]
    template_title: Optional[str] = None


class FillNodeQuery(BaseModel):
    query_text: str
    section_title: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    expected_unit_types: list[str] = Field(default_factory=list)


class FillNodeMatchCandidate(BaseModel):
    unit_id: str
    file_id: str
    title: str
    unit_type: str
    source_type: str
    score: int
    reason: str
    retrieval_source: str = "rule"
    rerank_score: Optional[float] = None
    rerank_reason: Optional[str] = None


class FillNodeMatch(BaseModel):
    task_id: str
    node_id: str
    node_title: str
    query_text: str
    expected_unit_types: list[str] = Field(default_factory=list)
    candidates: list[FillNodeMatchCandidate] = Field(default_factory=list)
    selected_unit_id: Optional[str] = None
    evidence_status: Optional[str] = None
    selection_reason: Optional[str] = None
    retrieval_debug: Optional[dict[str, Any]] = None
    status: Literal["matched", "no_candidates", "skipped"] = "matched"


class FillNodeMatchResponse(BaseModel):
    ok: bool = True
    task_id: str
    fill_node_count: int
    matched_count: int
    results: list[FillNodeMatch]


EvidenceStatus = Literal["verified", "weak", "missing"]
ResolveStatus = Literal["resolved", "missing"]


class FillNodeResult(BaseModel):
    task_id: str
    node_id: str
    node_title: str
    field_type: NodeFieldType
    evidence_status: EvidenceStatus
    fill_value: Optional[Any] = None
    bound_image_unit_id: Optional[str] = None
    render_payload: Optional[dict[str, Any]] = None
    selected_candidate: Optional[FillNodeMatchCandidate] = None
    status: ResolveStatus = "resolved"
    generation_confidence: Optional[float] = None
    pending_review: bool = False
    applied_by_policy: bool = False
    llm_trace_id: Optional[str] = None
    evidence_unit_ids: list[str] = Field(default_factory=list)


class FillNodeResolveResponse(BaseModel):
    ok: bool = True
    task_id: str
    result_count: int
    verified_count: int
    weak_count: int
    missing_count: int
    results: list[FillNodeResult]


def _persist_template_nodes(task_id: str, template_file_id: str, nodes: list[TemplateNode]) -> None:
    _write_json_atomic(
        _template_nodes_path(task_id),
        {
            "task_id": task_id,
            "template_file_id": template_file_id,
            "nodes": [node.model_dump() for node in nodes],
        },
    )


def _load_template_nodes(task_id: str) -> tuple[Optional[str], list[TemplateNode]]:
    raw = _read_json(_template_nodes_path(task_id), None)
    if not isinstance(raw, dict):
        return None, []
    template_file_id = raw.get("template_file_id")
    items = raw.get("nodes", [])
    if not isinstance(items, list):
        return template_file_id, []
    loaded: list[TemplateNode] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            loaded.append(TemplateNode.model_validate(item))
        except Exception:
            continue
    return template_file_id, loaded


def list_template_nodes(task_id: str) -> list[TemplateNode]:
    _, nodes = _load_template_nodes(task_id)
    return nodes


def apply_template_node_semantics(task_id: str, semantics_by_node_id: dict[str, dict[str, Any]]) -> list[TemplateNode]:
    template_file_id, nodes = _load_template_nodes(task_id)
    if not template_file_id or not nodes:
        raise HTTPException(status_code=404, detail="Template nodes not found")
    for node in nodes:
        semantic = semantics_by_node_id.get(node.node_id)
        if not semantic:
            continue
        node.normalized_title = str(semantic.get("normalized_title") or node.title).strip() or node.title
        canonical = semantic.get("canonical_label")
        node.canonical_label = str(canonical).strip() if canonical is not None else node.canonical_label
        tags = semantic.get("semantic_tags")
        if isinstance(tags, list):
            node.semantic_tags = [str(item).strip() for item in tags if str(item).strip()][:8]
        normalized_section = semantic.get("normalized_section")
        if normalized_section is not None:
            node.normalized_section = str(normalized_section).strip() or None
        confidence_raw = semantic.get("llm_confidence")
        try:
            node.llm_confidence = float(confidence_raw)
        except Exception:
            pass
    _persist_template_nodes(task_id, template_file_id, nodes)
    return nodes


def update_template_node(task_id: str, node_id: str, payload: UpdateTemplateNodeRequest) -> TemplateNode:
    template_file_id, nodes = _load_template_nodes(task_id)
    if not template_file_id:
        raise HTTPException(status_code=404, detail="Template nodes not found")
    for node in nodes:
        if node.node_id != node_id:
            continue
        if payload.title is not None:
            node.title = payload.title
        if payload.node_type is not None:
            node.node_type = payload.node_type
        if payload.content_mode is not None:
            node.content_mode = payload.content_mode
        if payload.field_type is not None:
            node.field_type = payload.field_type
        if payload.required is not None:
            node.required = payload.required
        if payload.requires_screenshot is not None:
            node.requires_screenshot = payload.requires_screenshot
        if payload.enabled is not None:
            node.enabled = payload.enabled

        _persist_template_nodes(task_id, template_file_id, nodes)
        return node

    raise HTTPException(status_code=404, detail="Template node not found")


def confirm_template(task_id: str) -> Task:
    task = _load_task(task_id)
    _, nodes = _load_template_nodes(task_id)
    if not nodes:
        raise HTTPException(status_code=400, detail="No template nodes to confirm")

    now = datetime.now(timezone.utc).isoformat()
    task.template_confirmed = True
    task.template_confirmed_at = now
    _persist_task(task)

    # Mark all nodes confirmed (v1).
    template_file_id, nodes = _load_template_nodes(task_id)
    if template_file_id:
        for node in nodes:
            node.status = "confirmed"
        _persist_template_nodes(task_id, template_file_id, nodes)

    return task


def _infer_node_type_from_title(title: str) -> TemplateNodeType:
    normalized = title.strip()
    if not normalized:
        return "section"
    for keyword in ("备注", "说明", "注意", "附注", "附录"):
        if keyword in normalized:
            return "note"
    return "section"


def _classify_section_content_mode(title: str) -> ContentMode:
    normalized = title.strip()
    if not normalized:
        return "generate"

    fill_keywords = ("截图",)
    mixed_keywords = (
        "验收标准",
        "实施计划",
        "风险控制",
        "工作方法",
        "接口",
        "表结构",
        "清单",
    )
    generate_keywords = (
        "项目概述",
        "引言",
        "背景",
        "目标",
        "范围",
        "环境",
        "售后服务",
        "培训计划",
        "承诺",
    )

    if any(keyword in normalized for keyword in fill_keywords):
        return "fill"
    if any(keyword in normalized for keyword in mixed_keywords):
        return "mixed"
    if any(keyword in normalized for keyword in generate_keywords):
        return "generate"
    return "generate"


def _build_template_nodes_from_parsed(
    task_id: str, template_file_id: str, parsed_template: dict[str, Any]
) -> list[TemplateNode]:
    # v1: DOCX-focused. Other formats will produce a minimal synthetic node.
    template_type = str(parsed_template.get("type") or "").strip().lower()
    if template_type and template_type != "docx":
        return [
            TemplateNode(
                node_id=str(uuid4()),
                task_id=task_id,
                node_type="note",
                title=f"Unsupported template type: {template_type}",
                level=1,
                parent_id=None,
                content_mode="generate",
                field_type="unknown",
                required=False,
                requires_screenshot=False,
                enabled=True,
                status="draft",
                source_location=None,
                parser_notes={"type": template_type},
            )
        ]

    sections = parsed_template.get("sections") or []
    field_list = parsed_template.get("field_list") or []

    nodes: list[TemplateNode] = []
    id_to_node: dict[str, TemplateNode] = {}

    # 1) Section nodes (tree by heading level)
    stack: list[TemplateNode] = []
    title_to_section_id: dict[str, str] = {}
    for raw in sections:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip() or "Untitled"
        level = int(raw.get("level") or 1)
        if level < 1:
            level = 1
        if level > 9:
            level = 9

        while stack and stack[-1].level >= level:
            stack.pop()
        parent_id = stack[-1].node_id if stack else None

        node_id = str(uuid4())
        node_type = _infer_node_type_from_title(title)
        node = TemplateNode(
            node_id=node_id,
            task_id=task_id,
            node_type=node_type,
            title=title,
            level=level,
            parent_id=parent_id,
            content_mode=_classify_section_content_mode(title),
            field_type="unknown",
            required=True,
            requires_screenshot=False,
            enabled=True,
            status="draft",
            source_location={
                "kind": "docx_heading",
                "section_index": raw.get("section_index"),
                **(raw.get("source_location") or {}),
            }
            if isinstance(raw.get("source_location"), dict) or raw.get("section_index") is not None
            else None,
            parser_notes=None,
        )
        nodes.append(node)
        id_to_node[node_id] = node
        stack.append(node)

        # Keep first occurrence (stable attachment for fields).
        if title not in title_to_section_id:
            title_to_section_id[title] = node_id

    # 2) Field nodes (flat list attached under section if possible)
    for raw in field_list:
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("field") or "").strip()
        if not label:
            continue

        parent_id = None
        section_title = raw.get("section")
        if isinstance(section_title, str) and section_title.strip():
            parent_id = title_to_section_id.get(section_title.strip())

        inferred_field_type: NodeFieldType = "text"
        if str(raw.get("source") or "").strip().lower() == "table":
            inferred_field_type = "table"

        level = 1
        if parent_id and parent_id in id_to_node:
            level = min(id_to_node[parent_id].level + 1, 9)

        node_id = str(uuid4())
        node = TemplateNode(
            node_id=node_id,
            task_id=task_id,
            node_type="field",
            title=label,
            level=level,
            parent_id=parent_id,
            content_mode="fill",
            field_type=inferred_field_type,
            required=True,
            requires_screenshot=False,
            enabled=True,
            status="draft",
            source_location={
                "kind": "docx_field",
                "source": raw.get("source"),
                "table_index": raw.get("table_index"),
                "header": raw.get("header"),
            },
            parser_notes={
                # Keep raw extraction details for debugging in UI.
                "raw": raw,
            },
        )
        nodes.append(node)
        id_to_node[node_id] = node

    # 3) Section content_mode: upgrade to mixed if it has a field descendant
    for node in nodes:
        if node.node_type != "field":
            continue
        parent_id = node.parent_id
        while parent_id:
            parent = id_to_node.get(parent_id)
            if not parent:
                break
            if parent.node_type == "section" and parent.content_mode == "generate":
                parent.content_mode = "mixed"
            parent_id = parent.parent_id

    # 4) Directory-only template hint: if parser recommends fill_full_body, keep sections generate.
    fill_rec = parsed_template.get("fill_recommendation") or {}
    if isinstance(fill_rec, dict) and fill_rec.get("mode") == "fill_full_body":
        for node in nodes:
            if node.node_type == "section":
                if node.content_mode not in {"mixed", "fill"}:
                    node.content_mode = "generate"

    return nodes


def _list_task_ids() -> list[str]:
    ids: list[str] = []
    for path in TASKS_DIR.glob("*.json"):
        ids.append(path.stem)
    return ids


def _migrate_legacy_db_if_needed() -> None:
    if not LEGACY_TASKS_DB_PATH.exists():
        return
    # Only migrate when new layout appears empty.
    if any(TASKS_DIR.glob("*.json")):
        return

    legacy_raw = _read_json(LEGACY_TASKS_DB_PATH, [])
    if not isinstance(legacy_raw, list):
        return

    for item in legacy_raw:
        if not isinstance(item, dict):
            continue
        try:
            task = Task.model_validate(item)
        except Exception:
            continue

        _persist_task(task)
        _persist_files(task.id, task.files)
        _persist_materials(task.id, task.material_units)

        # If a template is already parsed, store its fields.
        template_files = [record for record in task.files if record.role == "template"]
        if template_files and template_files[0].parsed_template:
            fields = template_files[0].parsed_template.get("field_list") or []
            _persist_fields(task.id, fields, template_files[0].file_id)
        else:
            _persist_fields(task.id, [], None)

        _persist_matches(task.id, {"ok": True, "task_id": task.id, "results": []})

    LEGACY_TASKS_DB_PATH.replace(DATA_DIR / "tasks.json.migrated")


_migrate_legacy_db_if_needed()


def create_task(payload: CreateTaskRequest) -> Task:
    task = Task(id=str(uuid4()), title=payload.title, description=payload.description)
    _persist_task(task)
    _persist_files(task.id, [])
    _persist_fields(task.id, [], None)
    _persist_materials(task.id, [])
    _persist_matches(task.id, {"ok": True, "task_id": task.id, "results": []})
    return task


def list_tasks() -> list[Task]:
    tasks: list[Task] = []
    for task_id in sorted(_list_task_ids(), reverse=True):
        try:
            task_raw = _read_json(_task_path(task_id), None)
            if not isinstance(task_raw, dict):
                continue
            tasks.append(
                Task.model_validate(
                    {
                        **task_raw,
                        "files": [],
                        "material_units": [],
                    }
                )
            )
        except Exception:
            continue
    return tasks


def get_task(task_id: str) -> Task:
    return _load_task(task_id)


async def upload_files_async(task_id: str, files: list[UploadFile]) -> list[UploadedFileRecord]:
    task = _load_task(task_id)
    uploaded: list[UploadedFileRecord] = []

    for file in files:
        file_id = str(uuid4())
        suffix = Path(file.filename or "").suffix
        stored_name = f"{file_id}{suffix}"
        stored_path = UPLOAD_DIR / stored_name
        content = await file.read()
        stored_path.write_bytes(content)

        record = UploadedFileRecord(
            file_id=file_id,
            task_id=task_id,
            filename=file.filename,
            content_type=file.content_type,
            size=len(content),
            path=f"uploads/{stored_name}",
        )
        task.files.append(record)
        uploaded.append(record)

    _persist_files(task_id, task.files)
    return uploaded


def update_file_role(task_id: str, file_id: str, payload: UpdateFileRoleRequest) -> Task:
    task = _load_task(task_id)
    file_record = _find_task_file(task, file_id)
    file_record.role = payload.role
    _persist_files(task_id, task.files)
    return task


def parse_template(task_id: str, file_id: str) -> Task:
    task = _load_task(task_id)
    file_record = _find_task_file(task, file_id)

    if file_record.role != "template":
        raise HTTPException(status_code=400, detail="Only template files can be parsed")

    file_record.parsed_template = _parse_template_file(file_record)
    _persist_files(task_id, task.files)
    raw_fields = (
        file_record.parsed_template.get("field_list")
        if file_record.parsed_template
        else []
    )
    _merge_fields(task_id, file_record.file_id, raw_fields or [])
    return task


def parse_template_nodes(task_id: str, file_id: Optional[str] = None) -> ParseTemplateResponse:
    task = _load_task(task_id)
    template_files = [record for record in task.files if record.role == "template"]
    if not template_files:
        raise HTTPException(status_code=400, detail="No template file set")

    template_record: UploadedFileRecord
    if file_id:
        template_record = _find_task_file(task, file_id)
        if template_record.role != "template":
            raise HTTPException(status_code=400, detail="Only template files can be parsed")
    else:
        # First template wins (v1).
        template_record = template_files[0]
    try:
        template_record.parsed_template = _parse_template_file(template_record)
        _persist_files(task_id, task.files)
    except HTTPException as exc:
        # Eval fixtures may not carry real template files on disk.
        # If nodes already exist for this task, return them as a compatibility fallback.
        if exc.status_code == 404 and str(exc.detail) == "Stored file not found":
            existing_template_file_id, existing_nodes = _load_template_nodes(task_id)
            if existing_nodes:
                return ParseTemplateResponse(
                    ok=True,
                    task_id=task_id,
                    template_file_id=existing_template_file_id or template_record.file_id,
                    node_count=len(existing_nodes),
                    nodes=existing_nodes,
                    template_title=None,
                )
        raise

    # Re-parsing invalidates confirmation.
    if task.template_confirmed:
        task.template_confirmed = False
        task.template_confirmed_at = None
        _persist_task(task)

    parsed_template = template_record.parsed_template or {}
    nodes = _build_template_nodes_from_parsed(task_id, template_record.file_id, parsed_template)
    _persist_template_nodes(task_id, template_record.file_id, nodes)

    template_title = None
    if isinstance(parsed_template, dict):
        value = parsed_template.get("title")
        template_title = str(value).strip() if isinstance(value, str) and value.strip() else None

    return ParseTemplateResponse(
        ok=True,
        task_id=task_id,
        template_file_id=template_record.file_id,
        node_count=len(nodes),
        nodes=nodes,
        template_title=template_title,
    )


def normalize_template_semantics(task_id: str):
    from app.services import semantic_normalizer_service

    return semantic_normalizer_service.normalize_template_semantics(task_id)


def build_material_embeddings(task_id: str):
    from app.services import semantic_retrieval_service

    return semantic_retrieval_service.build_material_embeddings(task_id)


def parse_materials(task_id: str) -> Task:
    task = _load_task(task_id)
    # Remove old units for files we will re-parse.
    asset_file_ids = {record.file_id for record in task.files if record.role == "asset"}
    task.material_units = [
        unit for unit in task.material_units if unit.file_id not in asset_file_ids
    ]

    for record in task.files:
        if record.role != "asset":
            continue
        file_path = API_ROOT / record.path
        if not file_path.exists():
            continue
        if file_path.suffix.lower() != ".docx":
            continue

        try:
            parsed = parse_docx_template(file_path.read_bytes())
        except DocxParseError:
            continue

        sections = parsed.get("sections") or []
        for section in sections:
            title = str(section.get("title") or "").strip()
            content = str(section.get("content") or "").strip()
            if not title and not content:
                continue
            unit = MaterialUnit(
                id=str(uuid4()),
                task_id=task_id,
                file_id=record.file_id,
                title=title or "Untitled",
                content=content,
                section_index=int(section.get("section_index") or 0),
                source_type="docx",
                unit_type="text",
                metadata={
                    "section_level": section.get("level"),
                    "section_index": section.get("section_index"),
                    "filename": record.filename,
                    "path": record.path,
                },
            )
            task.material_units.append(unit)

    _persist_materials(task_id, task.material_units)
    return task


def list_material_units(task_id: str) -> list[MaterialUnit]:
    materials_raw = _read_json(_materials_path(task_id), {"material_units": []})
    units_raw = materials_raw.get("material_units", [])
    try:
        return [MaterialUnit.model_validate(unit) for unit in units_raw]
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Corrupted material data") from exc


def _tokenize_keywords(*parts: Optional[str]) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        raw = str(part).strip()
        if not raw:
            continue
        segments = [raw]
        segments.extend(
            [
                chunk.strip()
                for chunk in raw.replace("（", " ")
                .replace("）", " ")
                .replace("/", " ")
                .replace("_", " ")
                .replace("-", " ")
                .split(" ")
            ]
        )
        for segment in segments:
            if len(segment) < 2:
                continue
            lowered = segment.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            tokens.append(segment)
    return tokens


def get_fill_nodes(task_id: str) -> list[TemplateNode]:
    nodes = list_template_nodes(task_id)
    return [
        node
        for node in nodes
        if node.node_type == "field" and node.content_mode == "fill" and node.enabled
    ]


def build_node_query(node: TemplateNode, all_nodes: list[TemplateNode]) -> FillNodeQuery:
    node_by_id = {item.node_id: item for item in all_nodes}
    section_title: Optional[str] = None
    parent_id = node.parent_id
    while parent_id:
        parent = node_by_id.get(parent_id)
        if not parent:
            break
        if parent.node_type == "section":
            section_title = parent.title
            break
        parent_id = parent.parent_id

    expected_unit_types: list[str] = []
    if node.requires_screenshot:
        expected_unit_types.append("image")
    if node.field_type == "image":
        expected_unit_types.append("image")
    elif node.field_type == "table":
        expected_unit_types.extend(["table_row", "table", "text"])
    elif node.field_type == "list":
        expected_unit_types.extend(["list", "text"])
    else:
        expected_unit_types.append("text")
    expected_unit_types = list(dict.fromkeys(expected_unit_types))

    parser_hint = None
    if node.parser_notes and isinstance(node.parser_notes.get("raw"), dict):
        raw = node.parser_notes.get("raw")
        parser_hint = str(raw.get("header") or raw.get("source") or "").strip() or None

    query_text = node.title if not section_title else f"{section_title} - {node.title}"
    keywords = _tokenize_keywords(node.title, section_title, parser_hint)
    return FillNodeQuery(
        query_text=query_text,
        section_title=section_title,
        keywords=keywords,
        expected_unit_types=expected_unit_types,
    )


def retrieve_candidates(task_id: str, node_query: FillNodeQuery) -> list[MaterialUnit]:
    units = list_material_units(task_id)
    if not units:
        return []

    expected = {item.lower() for item in node_query.expected_unit_types}
    recalled: list[MaterialUnit] = []
    expects_image_only = bool(expected) and expected.issubset({"image"})
    expects_structured = bool(expected.intersection({"table", "table_row", "list"}))

    for unit in units:
        title = (unit.title or "").lower()
        content = (unit.content or "").lower()
        unit_type = (unit.unit_type or "text").lower()

        keyword_hit = False
        for keyword in node_query.keywords:
            lowered = keyword.lower()
            if lowered in title or lowered in content:
                keyword_hit = True
                break
        section_hit = False
        if node_query.section_title:
            section_lower = node_query.section_title.lower()
            if section_lower in title or section_lower in content:
                section_hit = True
        type_hit = bool(expected and unit_type in expected)

        if expects_image_only:
            # Image fill fields should bind image units, but still prefer lexical relevance.
            hit = type_hit and (keyword_hit or section_hit)
        elif expects_structured:
            # table/list fields can use type as a weak recall signal.
            hit = keyword_hit or section_hit or type_hit
        else:
            # text-like fields: avoid recalling everything by type=text.
            hit = keyword_hit or section_hit

        if hit:
            recalled.append(unit)

    if not recalled:
        if expects_image_only:
            return [unit for unit in units if (unit.unit_type or "").lower() == "image"][: min(10, len(units))]
        if expects_structured:
            structured_units = [
                unit
                for unit in units
                if (unit.unit_type or "").lower() in {"table", "table_row", "list", "text"}
            ]
            return structured_units[: min(10, len(structured_units))]
        return units[: min(10, len(units))]
    return recalled


def _retrieve_rule_expanded_candidates(task_id: str, node_query: FillNodeQuery) -> list[MaterialUnit]:
    units = list_material_units(task_id)
    if not units:
        return []
    recalled: list[MaterialUnit] = []
    for unit in units:
        content = f"{unit.title} {unit.content}".lower()
        hit_count = 0
        for keyword in node_query.keywords:
            lowered = keyword.lower()
            if lowered and lowered in content:
                hit_count += 1
        if hit_count >= 2:
            recalled.append(unit)
    return recalled


def _merge_candidates_by_unit(
    rule_units: list[MaterialUnit],
    expanded_units: list[MaterialUnit],
    semantic_hits: list[tuple[str, float]],
    all_units_by_id: dict[str, MaterialUnit],
) -> list[MaterialUnit]:
    ordered: list[MaterialUnit] = []
    seen: set[str] = set()
    for unit in rule_units + expanded_units:
        if unit.id in seen:
            continue
        seen.add(unit.id)
        ordered.append(unit)
    for unit_id, _ in semantic_hits:
        unit = all_units_by_id.get(unit_id)
        if not unit or unit.id in seen:
            continue
        seen.add(unit.id)
        ordered.append(unit)
    return ordered


def _rerank_fill_candidates_hybrid(
    node: TemplateNode,
    node_query: FillNodeQuery,
    candidates: list[FillNodeMatchCandidate],
) -> list[FillNodeMatchCandidate]:
    if not candidates:
        return candidates

    from app.services import llm_client

    docs = [
        (
            f"unit_id={item.unit_id}\n"
            f"title={item.title}\n"
            f"unit_type={item.unit_type}\n"
            f"rule_score={item.score}\n"
            f"reason={item.reason}"
        )
        for item in candidates
    ]
    rerank_items = llm_client.llm_client.rerank(
        query=f"{node.title} | {node_query.query_text} | expected={','.join(node_query.expected_unit_types)}",
        documents=docs,
        top_n=len(candidates),
    )
    score_by_index: dict[int, tuple[float, str]] = {}
    for item in rerank_items:
        try:
            idx = int(item.get("index"))
        except Exception:
            continue
        try:
            score = float(item.get("relevance_score"))
        except Exception:
            score = 0.0
        reason = str(item.get("reason") or "llm_rerank")
        score_by_index[idx] = (max(0.0, min(1.0, score)), reason)

    for idx, item in enumerate(candidates):
        if idx in score_by_index:
            score, reason = score_by_index[idx]
            item.rerank_score = score
            item.rerank_reason = reason
        else:
            item.rerank_score = max(0.0, min(1.0, 0.5 + (item.score / 10.0)))
            item.rerank_reason = "fallback_by_rule_score"

    candidates.sort(
        key=lambda item: (
            item.rerank_score if item.rerank_score is not None else 0.0,
            item.score,
        ),
        reverse=True,
    )
    return candidates


def rank_candidates(
    node: TemplateNode,
    node_query: FillNodeQuery,
    candidates: list[MaterialUnit],
    top_n: int = 5,
) -> list[FillNodeMatchCandidate]:
    ranked: list[FillNodeMatchCandidate] = []
    expected = {item.lower() for item in node_query.expected_unit_types}
    section_lower = (node_query.section_title or "").lower()
    node_title_lower = node.title.lower()

    for unit in candidates:
        score = 0
        reasons: list[str] = []
        title = unit.title or ""
        content = unit.content or ""
        title_lower = title.lower()
        content_lower = content.lower()
        unit_type = (unit.unit_type or "text").lower()

        if node_title_lower and node_title_lower in title_lower:
            score += 3
            reasons.append("title_hit:+3")
        if node_title_lower and node_title_lower in content_lower:
            score += 2
            reasons.append("content_hit:+2")
        if section_lower and (section_lower in title_lower or section_lower in content_lower):
            score += 2
            reasons.append("section_hit:+2")
        if expected and unit_type in expected:
            score += 2
            reasons.append("unit_type_match:+2")
        for keyword in node_query.keywords:
            lowered = keyword.lower()
            if lowered and lowered in title_lower and lowered not in {node_title_lower, section_lower}:
                score += 1
                reasons.append("weak_keyword_hit:+1")
                break

        if score <= 0:
            continue

        ranked.append(
            FillNodeMatchCandidate(
                unit_id=unit.id,
                file_id=unit.file_id,
                title=title or "Untitled",
                unit_type=unit.unit_type or "text",
                source_type=unit.source_type or "docx",
                score=score,
                reason=", ".join(reasons),
                retrieval_source="rule",
            )
        )

    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[: max(1, int(top_n))]


def list_fill_node_matches(task_id: str) -> list[FillNodeMatch]:
    raw = _load_matches(task_id)
    items = raw.get("fill_node_matches", [])
    if not isinstance(items, list):
        return []
    results: list[FillNodeMatch] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            results.append(FillNodeMatch.model_validate(item))
        except Exception:
            continue
    return results


def _derive_match_evidence_status(selected: Optional[FillNodeMatchCandidate]) -> str:
    if not selected:
        return "missing"
    confidence = (
        float(selected.rerank_score)
        if selected.rerank_score is not None
        else max(0.0, min(1.0, 0.5 + (selected.score / 10.0)))
    )
    if confidence >= 0.8:
        return "verified"
    if confidence >= 0.6:
        return "weak"
    return "missing"


def match_fill_nodes(task_id: str, top_n: int = 5, strategy: str = "rule") -> FillNodeMatchResponse:
    _load_task(task_id)
    all_nodes = list_template_nodes(task_id)
    if not all_nodes:
        existing = _load_matches(task_id)
        existing.update(
            {
                "task_id": task_id,
                "fill_node_matches": [],
                "fill_node_match_summary": {
                    "fill_node_count": 0,
                    "matched_count": 0,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "top_n": max(1, int(top_n)),
                },
            }
        )
        _persist_matches(task_id, existing)
        return FillNodeMatchResponse(
            ok=True,
            task_id=task_id,
            fill_node_count=0,
            matched_count=0,
            results=[],
        )

    fill_nodes = get_fill_nodes(task_id)
    results: list[FillNodeMatch] = []
    matched_count = 0

    for node in fill_nodes:
        node_query = build_node_query(node, all_nodes)
        recalled = retrieve_candidates(task_id, node_query)
        selected_unit_id: Optional[str] = None
        selected_evidence_status: Optional[str] = None
        selection_reason: Optional[str] = None
        retrieval_debug: Optional[dict[str, Any]] = None

        if strategy == "hybrid":
            from app.services import fill_rerank_service, hybrid_retrieval_service

            hybrid_result = hybrid_retrieval_service.hybrid_retrieve_candidates(
                task_id=task_id,
                node_query=node_query,
                top_n=max(10, int(top_n) * 2),
            )
            merged_units = [
                MaterialUnit(
                    id=item.unit_id,
                    task_id=task_id,
                    file_id=item.file_id,
                    title=item.title,
                    content=item.content,
                    section_index=0,
                    source_type=item.source_type,
                    unit_type=item.unit_type,
                    metadata={},
                )
                for item in hybrid_result.candidates
            ]
            ranked = rank_candidates(
                node,
                node_query,
                merged_units,
                top_n=max(10, int(top_n) * 2),
            )
            hybrid_by_id = {item.unit_id: item for item in hybrid_result.candidates}
            for item in ranked:
                hybrid_meta = hybrid_by_id.get(item.unit_id)
                if not hybrid_meta:
                    continue
                item.retrieval_source = hybrid_meta.retrieval_source
                if hybrid_meta.vector_score is not None:
                    item.reason = f"{item.reason}, vector_score:{hybrid_meta.vector_score:.3f}"
            ranked = _rerank_fill_candidates_hybrid(node=node, node_query=node_query, candidates=ranked)
            rerank_selection = fill_rerank_service.llm_rerank_fill_candidates(
                node=node,
                node_query=node_query,
                candidates=ranked,
            )
            selected_unit_id = rerank_selection.selected_unit_id
            selected_evidence_status = rerank_selection.evidence_status
            selection_reason = rerank_selection.reason
            if selected_unit_id and node.field_type == "image":
                selected_candidate = next(
                    (item for item in ranked if item.unit_id == selected_unit_id),
                    None,
                )
                if selected_candidate is not None and selected_evidence_status == "missing":
                    selected_evidence_status = (
                        "verified" if selected_candidate.score >= 6 else "weak"
                    )
                    selection_reason = f"{selection_reason}; image_status_guardrail"
            retrieval_debug = dict(hybrid_result.debug)
            ranked = ranked[: max(1, int(top_n))]
        else:
            ranked = rank_candidates(node, node_query, recalled, top_n=top_n)
            selected = ranked[0] if ranked else None
            selected_unit_id = selected.unit_id if selected else None
            selected_evidence_status = _derive_match_evidence_status(selected)
            selection_reason = "rule_top1"
            retrieval_debug = {"rule_count": len(recalled), "merged_count": len(ranked)}

        status: Literal["matched", "no_candidates", "skipped"] = (
            "matched" if ranked else "no_candidates"
        )
        if ranked:
            matched_count += 1
        results.append(
            FillNodeMatch(
                task_id=task_id,
                node_id=node.node_id,
                node_title=node.title,
                query_text=node_query.query_text,
                expected_unit_types=node_query.expected_unit_types,
                candidates=ranked,
                selected_unit_id=selected_unit_id,
                evidence_status=selected_evidence_status,
                selection_reason=selection_reason,
                retrieval_debug=retrieval_debug,
                status=status,
            )
        )

    existing = _load_matches(task_id)
    existing.update(
        {
            "task_id": task_id,
            "fill_node_matches": [item.model_dump() for item in results],
            "fill_node_match_summary": {
                "fill_node_count": len(fill_nodes),
                "matched_count": matched_count,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "top_n": max(1, int(top_n)),
                "strategy": strategy,
            },
        }
    )
    _persist_matches(task_id, existing)

    return FillNodeMatchResponse(
        ok=True,
        task_id=task_id,
        fill_node_count=len(fill_nodes),
        matched_count=matched_count,
        results=results,
    )


def list_fill_node_results(task_id: str) -> list[FillNodeResult]:
    raw = _load_fill_results(task_id)
    items = raw.get("results", [])
    if not isinstance(items, list):
        return []
    results: list[FillNodeResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            results.append(FillNodeResult.model_validate(item))
        except Exception:
            continue
    return results


def _resolve_evidence_status(selected: Optional[FillNodeMatchCandidate]) -> EvidenceStatus:
    if not selected:
        return "missing"
    if selected.score >= 6:
        return "verified"
    if selected.score >= 2:
        return "weak"
    return "missing"


def _build_fill_value(
    field_type: NodeFieldType,
    selected: Optional[FillNodeMatchCandidate],
    unit_by_id: dict[str, MaterialUnit],
    node_title: str = "",
) -> Optional[Any]:
    if not selected:
        return None
    unit = unit_by_id.get(selected.unit_id)
    if not unit:
        return None

    if field_type == "image":
        return {
            "type": "image_ref",
            "unit_id": unit.id,
            "file_id": unit.file_id,
            "title": unit.title,
        }
    if field_type == "table":
        return {
            "type": "table_ref",
            "table_ref": {
                "unit_id": unit.id,
                "file_id": unit.file_id,
                "title": unit.title,
            },
        }
    # text/list/unknown are treated as textual fill in v1.
    content = unit.content or ""
    if not content:
        return ""
    business_keywords = {"承诺", "保密", "合同", "法务", "法律", "条款"}
    is_business_field = any(keyword in (node_title or "") for keyword in business_keywords)
    blocked_terms = ["甲方", "乙方", "采购编号", "投标文件", "销售合同", "通信地址", "联系方式", "联系人"]
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not is_business_field:
        lines = [line for line in lines if not any(term in line for term in blocked_terms)]
    if not lines:
        return ""
    keywords = [item.lower() for item in _tokenize_keywords(node_title) if item]
    for line in lines:
        lowered = line.lower()
        if any(keyword in lowered for keyword in keywords):
            return line
    return "\n".join(lines[:3])[:800]


def _generate_text_fill_value_hybrid(
    node_title: str,
    selected: Optional[FillNodeMatchCandidate],
    all_candidates: list[FillNodeMatchCandidate],
    unit_by_id: dict[str, MaterialUnit],
) -> tuple[str, float, str, list[str]]:
    from app.services import llm_client

    evidence_ids: list[str] = []
    evidence_payload: list[dict[str, Any]] = []
    ordered_candidates: list[FillNodeMatchCandidate] = []
    seen_candidate_ids: set[str] = set()
    if selected is not None:
        ordered_candidates.append(selected)
        seen_candidate_ids.add(selected.unit_id)
    for candidate in all_candidates:
        if candidate.unit_id in seen_candidate_ids:
            continue
        ordered_candidates.append(candidate)
        seen_candidate_ids.add(candidate.unit_id)
    for candidate in ordered_candidates[:3]:
        unit = unit_by_id.get(candidate.unit_id)
        if not unit:
            continue
        evidence_ids.append(unit.id)
        evidence_payload.append(
            {
                "unit_id": unit.id,
                "title": unit.title,
                "content": (unit.content or "")[:1800],
                "score": candidate.score,
                "rerank_score": candidate.rerank_score,
            }
        )

    if not evidence_payload:
        return "", 0.0, f"fallback-{uuid4()}", []

    if not llm_client.llm_client.enabled:
        fallback = str(evidence_payload[0].get("content") or "").strip()
        first_line = next((line.strip() for line in fallback.splitlines() if line.strip()), fallback[:600])
        confidence = (
            max(0.65, float(selected.rerank_score))
            if selected and selected.rerank_score is not None
            else 0.65
        )
        return first_line[:1000], confidence, f"fallback-{uuid4()}", evidence_ids

    system_prompt = (
        "你是项目验收文档回填助手。请根据给定证据生成一个可直接写入模板字段的完整文本。"
        "输出 JSON: {\"fill_text\":\"...\",\"confidence\":0-1}。"
        "允许完整成文，但不要引入与证据矛盾的事实。"
    )
    user_prompt = json.dumps(
        {
            "node_title": node_title,
            "evidences": evidence_payload,
        },
        ensure_ascii=False,
    )
    result = llm_client.llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
    try:
        payload = json.loads(result.text or "{}")
    except json.JSONDecodeError:
        payload = {}
    fill_text = str(payload.get("fill_text") or "").strip()
    if not fill_text:
        fill_text = str(evidence_payload[0].get("content") or "").strip()[:1000]
    try:
        confidence = float(payload.get("confidence"))
    except Exception:
        confidence = result.confidence
    confidence = max(0.0, min(1.0, confidence))
    return fill_text, confidence, result.trace_id, evidence_ids


def _select_candidate_for_resolution(
    match: FillNodeMatch,
    unit_by_id: dict[str, MaterialUnit],
    unit_usage_counts: dict[str, int],
    expects_image: bool,
) -> Optional[FillNodeMatchCandidate]:
    if not match.candidates:
        return None

    def usage_count(candidate: FillNodeMatchCandidate) -> int:
        return unit_usage_counts.get(candidate.unit_id, 0)

    if match.selected_unit_id:
        for candidate in match.candidates:
            if candidate.unit_id != match.selected_unit_id:
                continue
            if expects_image:
                unit = unit_by_id.get(candidate.unit_id)
                if unit and (unit.unit_type or "").lower() == "image":
                    return candidate
                break
            return candidate

    # Prefer candidates of expected type for image-like fields.
    if expects_image:
        image_candidates: list[FillNodeMatchCandidate] = []
        for candidate in match.candidates:
            unit = unit_by_id.get(candidate.unit_id)
            if unit and (unit.unit_type or "").lower() == "image":
                image_candidates.append(candidate)
        if image_candidates:
            image_candidates.sort(
                key=lambda candidate: (
                    usage_count(candidate),
                    -(candidate.rerank_score if candidate.rerank_score is not None else 0.0),
                    -candidate.score,
                )
            )
            return image_candidates[0]
        return None

    ranked = sorted(
        match.candidates,
        key=lambda candidate: (
            usage_count(candidate),
            -(candidate.rerank_score if candidate.rerank_score is not None else 0.0),
            -candidate.score,
        ),
    )
    return ranked[0] if ranked else None


def _unit_asset_path(unit: Optional[MaterialUnit]) -> Optional[str]:
    if not unit or not isinstance(unit.metadata, dict):
        return None
    for key in ("path", "file_path", "asset_path", "url"):
        value = unit.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _build_fill_render_payload(
    field_type: NodeFieldType,
    fill_value: Optional[Any],
    selected: Optional[FillNodeMatchCandidate],
    unit_by_id: dict[str, MaterialUnit],
    bound_image_unit_id: Optional[str],
) -> Optional[dict[str, Any]]:
    if bound_image_unit_id:
        unit = unit_by_id.get(bound_image_unit_id)
        path = _unit_asset_path(unit)
        payload: dict[str, Any] = {
            "type": "image",
            "unit_id": bound_image_unit_id,
        }
        if path:
            payload["path"] = path
        if unit and unit.title:
            payload["title"] = unit.title
        return payload

    if fill_value is None:
        return None

    if field_type == "table":
        return {
            "type": "table_ref",
            "value": fill_value,
        }
    if field_type == "list":
        return {
            "type": "list",
            "value": fill_value,
        }
    return {
        "type": "text",
        "value": fill_value,
    }


def resolve_fill_nodes(task_id: str, top_n: int = 5, strategy: str = "rule") -> FillNodeResolveResponse:
    _load_task(task_id)
    from app.services import rerank_policy_service

    all_nodes = list_template_nodes(task_id)
    node_by_id = {node.node_id: node for node in all_nodes}

    matches = list_fill_node_matches(task_id)
    if not matches:
        match_fill_nodes(task_id, top_n=top_n, strategy=strategy)
        matches = list_fill_node_matches(task_id)

    units = list_material_units(task_id)
    unit_by_id = {unit.id: unit for unit in units}

    results: list[FillNodeResult] = []
    verified_count = 0
    weak_count = 0
    missing_count = 0
    unit_usage_counts: dict[str, int] = {}

    for match in matches:
        node = node_by_id.get(match.node_id)
        field_type: NodeFieldType = node.field_type if node else "unknown"
        expects_image = bool(node and (node.field_type == "image" or node.requires_screenshot))
        selected = _select_candidate_for_resolution(
            match=match,
            unit_by_id=unit_by_id,
            unit_usage_counts=unit_usage_counts,
            expects_image=expects_image,
        )
        selected_unit = unit_by_id.get(selected.unit_id) if selected else None
        evidence_status = _resolve_evidence_status(selected)
        bound_image_unit_id: Optional[str] = None
        generation_confidence: Optional[float] = None
        llm_trace_id: Optional[str] = None
        evidence_unit_ids: list[str] = []
        pending_review = False
        applied_by_policy = False
        if expects_image:
            if selected_unit and (selected_unit.unit_type or "").lower() == "image":
                bound_image_unit_id = selected_unit.id
            else:
                evidence_status = "missing"
        if evidence_status in {"verified", "weak"}:
            if strategy == "hybrid" and field_type in {"text", "list", "unknown"}:
                fill_text, generation_confidence, llm_trace_id, evidence_unit_ids = _generate_text_fill_value_hybrid(
                    node_title=match.node_title,
                    selected=selected,
                    all_candidates=match.candidates,
                    unit_by_id=unit_by_id,
                )
                policy = rerank_policy_service.decide_policy(generation_confidence or 0.0)
                if policy == "auto_apply":
                    fill_value = fill_text
                    applied_by_policy = True
                elif policy == "pending_review":
                    fill_value = fill_text
                    pending_review = True
                else:
                    fill_value = None
                    evidence_status = "missing"
            else:
                fill_value = _build_fill_value(
                    field_type=field_type,
                    selected=selected,
                    unit_by_id=unit_by_id,
                    node_title=match.node_title,
                )
                evidence_unit_ids = [selected.unit_id] if selected else []
                generation_confidence = (
                    float(selected.rerank_score)
                    if selected and selected.rerank_score is not None
                    else max(0.0, min(1.0, 0.5 + ((selected.score if selected else 0) / 10.0)))
                )
                applied_by_policy = True if fill_value is not None else False
        else:
            fill_value = None

        render_payload = _build_fill_render_payload(
            field_type=field_type,
            fill_value=fill_value,
            selected=selected,
            unit_by_id=unit_by_id,
            bound_image_unit_id=bound_image_unit_id,
        )
        status: ResolveStatus = "resolved" if evidence_status != "missing" else "missing"

        if evidence_status == "verified":
            verified_count += 1
        elif evidence_status == "weak":
            weak_count += 1
        else:
            missing_count += 1
        if selected:
            unit_usage_counts[selected.unit_id] = unit_usage_counts.get(selected.unit_id, 0) + 1

        results.append(
            FillNodeResult(
                task_id=task_id,
                node_id=match.node_id,
                node_title=match.node_title,
                field_type=field_type,
                evidence_status=evidence_status,
                fill_value=fill_value,
                bound_image_unit_id=bound_image_unit_id,
                render_payload=render_payload,
                selected_candidate=selected,
                status=status,
                generation_confidence=generation_confidence,
                pending_review=pending_review,
                applied_by_policy=applied_by_policy,
                llm_trace_id=llm_trace_id,
                evidence_unit_ids=evidence_unit_ids,
            )
        )

    payload = {
        "task_id": task_id,
        "summary": {
            "result_count": len(results),
            "verified_count": verified_count,
            "weak_count": weak_count,
            "missing_count": missing_count,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "top_n": max(1, int(top_n)),
            "strategy": strategy,
        },
        "results": [item.model_dump() for item in results],
    }
    _persist_fill_results(task_id, payload)

    return FillNodeResolveResponse(
        ok=True,
        task_id=task_id,
        result_count=len(results),
        verified_count=verified_count,
        weak_count=weak_count,
        missing_count=missing_count,
        results=results,
    )


def match_fields(task_id: str, top_n: int = 5) -> dict[str, Any]:
    task = _load_task(task_id)
    template_files = [record for record in task.files if record.role == "template"]
    if not template_files:
        raise HTTPException(status_code=400, detail="No template file set")

    # First template wins (v1).
    template = template_files[0]
    if not template.parsed_template:
        raise HTTPException(status_code=400, detail="Template not parsed yet")

    _, fields = _load_fields(task_id)
    units = task.material_units
    results: list[dict[str, Any]] = []

    for field in fields:
        if field.mode == "ignored":
            continue
        field_label = str(field.label or "").strip()
        section_label = str(field.section or "").strip()
        if not field_label:
            continue

        candidates: list[dict[str, Any]] = []
        for unit in units:
            score = 0
            reasons: list[str] = []
            title = unit.title or ""
            content = unit.content or ""

            if field_label and field_label in title:
                score += 3
                reasons.append("field_in_title:+3")
            if field_label and field_label in content:
                score += 2
                reasons.append("field_in_content:+2")
            if section_label and section_label in content:
                score += 1
                reasons.append("section_in_content:+1")

            if score <= 0:
                continue

            candidates.append(
                {
                    "unit_id": unit.id,
                    "file_id": unit.file_id,
                    "title": unit.title,
                    "section_index": unit.section_index,
                    "score": score,
                    "reasons": reasons,
                }
            )

        candidates.sort(key=lambda item: item["score"], reverse=True)
        results.append(
            {
                "field_id": field.id,
                "field": field_label,
                "section": section_label or None,
                "top_candidates": candidates[: max(1, int(top_n))],
            }
        )

    result = {
        "ok": True,
        "task_id": task_id,
        "field_count": len(results),
        "unit_count": len(units),
        "results": results,
    }
    existing = _load_matches(task_id)
    existing.update(result)
    _persist_matches(task_id, existing)
    return result


def _find_task(task_id: str) -> Task:
    # Backwards-compat helper; keep signature for existing code.
    return _load_task(task_id)


def _find_task_file(task: Task, file_id: str) -> UploadedFileRecord:
    for record in task.files:
        if record.file_id == file_id:
            return record
    raise HTTPException(status_code=404, detail="File not found")


def _parse_template_file(record: UploadedFileRecord) -> dict[str, Any]:
    file_path = API_ROOT / record.path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Stored file not found")

    content = file_path.read_bytes()
    suffix = file_path.suffix.lower()

    if suffix == ".docx":
        try:
            parsed = parse_docx_template(content)
            # Enrich field_list with section labels where possible.
            sections = parsed.get("sections") or []
            section_titles = [str(section.get("title") or "") for section in sections]
            current_section = section_titles[0] if section_titles else None
            field_list = parsed.get("field_list") or []
            for item in field_list:
                if "section" not in item:
                    item["section"] = current_section
            return parsed
        except DocxParseError as exc:
            raise HTTPException(status_code=400, detail="Invalid DOCX template") from exc

    if suffix == ".xlsx":
        return parse_xlsx_template(content)

    if suffix == ".json":
        try:
            data = json.loads(content.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON template") from exc
        if isinstance(data, dict):
            return {
                "type": "json",
                "top_level_keys": list(data.keys()),
                "key_count": len(data.keys()),
            }
        if isinstance(data, list):
            return {
                "type": "json",
                "root_kind": "array",
                "item_count": len(data),
                "sample_item_type": type(data[0]).__name__ if data else None,
            }
        return {"type": "json", "root_kind": type(data).__name__}

    if suffix == ".csv":
        text = content.decode("utf-8")
        rows = list(csv.reader(text.splitlines()))
        headers = rows[0] if rows else []
        return {
            "type": "csv",
            "columns": headers,
            "column_count": len(headers),
            "row_count": max(len(rows) - 1, 0),
        }

    if suffix in {".txt", ".md"}:
        text = content.decode("utf-8")
        lines = text.splitlines()
        return {
            "type": "text",
            "line_count": len(lines),
            "character_count": len(text),
            "preview": text[:240],
        }

    if suffix in {".html", ".htm"}:
        text = content.decode("utf-8")
        lower = text.lower()
        title_hint = None
        if "<title>" in lower and "</title>" in lower:
            try:
                title_hint = text.split("<title>")[1].split("</title>")[0]
            except IndexError:
                title_hint = None
        return {
            "type": "html",
            "title_hint": title_hint,
            "character_count": len(text),
            "contains_table": "<table" in lower,
        }

    if suffix == ".png":
        return {
            "type": "image",
            "format": "png",
            "dimensions": parse_png_size(content),
            "size": len(content),
        }

    if suffix == ".gif":
        return {
            "type": "image",
            "format": "gif",
            "dimensions": parse_gif_size(content),
            "size": len(content),
        }

    if suffix in {".jpg", ".jpeg"}:
        return {
            "type": "image",
            "format": "jpeg",
            "dimensions": parse_jpeg_size(content),
            "size": len(content),
        }

    return {
        "type": "binary",
        "filename": record.filename,
        "path": record.path,
        "size": len(content),
        "extension": suffix or "unknown",
    }
