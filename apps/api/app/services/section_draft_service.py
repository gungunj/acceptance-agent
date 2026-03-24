import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.repositories import section_draft_repo
from app.services import material_service

DraftStatus = Literal["ready", "risky", "missing"]
FallbackSource = Literal["task", "global", "template", "llm_task_context"]


class SectionQuery(BaseModel):
    query_text: str
    parent_title: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    expected_unit_types: list[str] = Field(default_factory=lambda: ["text", "table_row"])


class SectionCandidate(BaseModel):
    unit_id: str
    file_id: str
    title: str
    unit_type: str
    score: int
    reason: str
    source_scope: Literal["task", "global"] = "task"


class InlineAsset(BaseModel):
    type: Literal["image"] = "image"
    unit_id: str
    path: Optional[str] = None
    caption: Optional[str] = None
    position: Literal["after_text", "appendix"] = "after_text"


class SectionDraftResult(BaseModel):
    task_id: str
    node_id: str
    node_title: str
    selected_unit_ids: list[str] = Field(default_factory=list)
    query_text: str
    draft_text: str
    inline_assets: list[InlineAsset] = Field(default_factory=list)
    evidence_unit_ids: list[str] = Field(default_factory=list)
    generation_confidence: Optional[float] = None
    llm_trace_id: Optional[str] = None
    draft_status: DraftStatus
    fallback_used: bool = False
    fallback_source: FallbackSource = "task"
    filtered_out_count: int = 0
    blocked_source_types: list[str] = Field(default_factory=list)
    risk_note: Optional[str] = None
    manual_action: Optional[str] = None


class SectionDraftGenerationResponse(BaseModel):
    ok: bool = True
    task_id: str
    result_count: int
    ready_count: int
    risky_count: int
    missing_count: int
    generated_at: str
    results: list[SectionDraftResult]


def _read_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _read_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value.strip())
    except Exception:
        return default
    return parsed if parsed > 0 else default


def _global_materials_enabled() -> bool:
    return _read_bool_env("GLOBAL_MATERIALS_ENABLED", True)


def _fallback_template_enabled() -> bool:
    return _read_bool_env("FALLBACK_TEMPLATE_ENABLED", True)


def _global_materials_dir() -> Path:
    default_dir = material_service.API_ROOT / "data" / "global_materials"
    raw = os.getenv("GLOBAL_MATERIALS_DIR", "").strip()
    if not raw:
        return default_dir
    path = Path(raw)
    return path if path.is_absolute() else (material_service.API_ROOT / path)


def _read_docx_text(path: Path) -> str:
    try:
        from docx import Document

        document = Document(str(path))
    except Exception:
        return ""
    lines = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(lines)


def _chunk_text(text: str, chunk_size: int = 1200) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(normalized[start:end].strip())
        start = end
    return [chunk for chunk in chunks if chunk]


def _build_global_unit(
    task_id: str,
    unit_id: str,
    file_id: str,
    title: str,
    content: str,
    unit_type: str = "text",
    metadata: Optional[dict] = None,
) -> material_service.MaterialUnit:
    merged_metadata = dict(metadata or {})
    merged_metadata["source_scope"] = "global"
    return material_service.MaterialUnit(
        id=unit_id,
        task_id=task_id,
        file_id=file_id,
        title=(title or "Global Material").strip() or "Global Material",
        content=(content or "").strip(),
        section_index=0,
        source_type="global",
        unit_type=(unit_type or "text").strip() or "text",
        metadata=merged_metadata,
    )


def _load_global_material_units(task_id: str) -> list[material_service.MaterialUnit]:
    if not _global_materials_enabled():
        return []
    base_dir = _global_materials_dir()
    if not base_dir.exists() or not base_dir.is_dir():
        return []

    loaded: list[material_service.MaterialUnit] = []
    index_path = base_dir / "index.json"
    if index_path.exists():
        try:
            raw = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            raw = None
        items = raw.get("materials", []) if isinstance(raw, dict) else raw
        if isinstance(items, list):
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                content = str(item.get("content") or "").strip()
                if not content:
                    continue
                raw_unit_id = str(item.get("unit_id") or f"index-{idx}")
                loaded.append(
                    _build_global_unit(
                        task_id=task_id,
                        unit_id=f"global:{raw_unit_id}",
                        file_id=f"global_file:{str(item.get('file_id') or raw_unit_id)}",
                        title=str(item.get("title") or raw_unit_id),
                        content=content,
                        unit_type=str(item.get("unit_type") or "text"),
                        metadata={
                            "path": str(item.get("path") or ""),
                            "source": "index",
                        },
                    )
                )

    file_counter = 0
    for path in sorted(base_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name.lower() == "index.json":
            continue
        suffix = path.suffix.lower()
        text = ""
        if suffix in {".txt", ".md", ".markdown"}:
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
        elif suffix == ".docx":
            text = _read_docx_text(path)
        else:
            continue
        for chunk_idx, chunk in enumerate(_chunk_text(text)):
            file_counter += 1
            unit_id = f"global:file-{file_counter}-chunk-{chunk_idx + 1}"
            loaded.append(
                _build_global_unit(
                    task_id=task_id,
                    unit_id=unit_id,
                    file_id=f"global_file:{path.stem}",
                    title=path.stem,
                    content=chunk,
                    unit_type="text",
                    metadata={
                        "path": str(path),
                        "source": "file",
                    },
                )
            )
    return loaded


def get_generate_nodes(task_id: str) -> list[material_service.TemplateNode]:
    nodes = material_service.list_template_nodes(task_id)
    section_ids = {node.node_id for node in nodes if node.node_type == "section"}
    non_leaf_section_ids = {
        node.parent_id
        for node in nodes
        if node.node_type == "section" and node.parent_id in section_ids
    }
    return [
        node
        for node in nodes
        if (
            node.node_type == "section"
            and node.content_mode in {"generate", "mixed"}
            and node.enabled
            and node.node_id not in non_leaf_section_ids
        )
    ]


def _tokenize(*parts: Optional[str]) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        raw = str(part).strip()
        if not raw:
            continue
        segments = [raw]
        segments.extend(raw.replace("（", " ").replace("）", " ").replace("/", " ").split(" "))
        for segment in segments:
            token = segment.strip()
            if len(token) < 2:
                continue
            lowered = token.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            keywords.append(token)
    return keywords


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _extract_filename(unit: material_service.MaterialUnit, file_name_by_id: dict[str, str]) -> str:
    if isinstance(unit.metadata, dict):
        for key in ("filename", "file_name", "name"):
            value = unit.metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return str(file_name_by_id.get(unit.file_id) or "")


def _classify_unit_tags(
    unit: material_service.MaterialUnit,
    file_name_by_id: dict[str, str],
) -> set[str]:
    filename = _extract_filename(unit, file_name_by_id)
    text = _normalize_text(f"{filename} {unit.title or ''} {unit.content or ''}")
    tags: set[str] = set()

    contract_keywords = ["合同", "甲方", "乙方", "买断", "付款", "违约", "销售合同", "通信地址", "联系方式", "联系人"]
    bid_keywords = ["招标", "投标", "采购编号", "标包", "评审"]
    legal_keywords = ["保密条款", "法律责任", "争议解决", "法务", "法律"]
    technical_keywords = [
        "实施",
        "系统",
        "架构",
        "部署",
        "接口",
        "环境",
        "验收",
        "培训",
        "运维",
        "目标",
        "背景",
        "范围",
        "性能",
        "售后",
    ]

    if any(keyword in text for keyword in contract_keywords):
        tags.add("contract")
    if any(keyword in text for keyword in bid_keywords):
        tags.add("bid")
    if any(keyword in text for keyword in legal_keywords):
        tags.add("legal")
    if any(keyword in text for keyword in technical_keywords):
        tags.add("technical")
    if not tags:
        tags.add("general")
    return tags


def _section_profile(title: str) -> Literal["technical", "business"]:
    normalized = _normalize_text(title)
    business_keywords = ["承诺", "保密", "合同", "商务", "法律", "法务", "条款", "付款", "违约", "报价"]
    if any(keyword in normalized for keyword in business_keywords):
        return "business"
    return "technical"


def _filter_units_for_section(
    node: material_service.TemplateNode,
    units: list[material_service.MaterialUnit],
    file_name_by_id: dict[str, str],
) -> tuple[list[material_service.MaterialUnit], int, list[str]]:
    if not units:
        return [], 0, []
    profile = _section_profile(node.title)
    if profile == "business":
        return units, 0, []

    blocked_tags = {"contract", "bid", "legal"}
    allowed: list[material_service.MaterialUnit] = []
    filtered_out = 0
    blocked_hit: set[str] = set()
    for unit in units:
        tags = _classify_unit_tags(unit, file_name_by_id)
        hit = tags.intersection(blocked_tags)
        if hit:
            filtered_out += 1
            blocked_hit.update(hit)
            continue
        allowed.append(unit)
    return allowed, filtered_out, sorted(blocked_hit)


def build_section_query(
    node: material_service.TemplateNode, all_nodes: list[material_service.TemplateNode]
) -> SectionQuery:
    node_by_id = {item.node_id: item for item in all_nodes}
    parent_title: Optional[str] = None
    parent_id = node.parent_id
    while parent_id:
        parent = node_by_id.get(parent_id)
        if not parent:
            break
        if parent.node_type == "section":
            parent_title = parent.title
            break
        parent_id = parent.parent_id

    parser_hint = None
    if node.parser_notes and isinstance(node.parser_notes, dict):
        parser_hint = str(node.parser_notes.get("hint") or "").strip() or None

    query_text = node.title if not parent_title else f"{parent_title} / {node.title}"
    keywords = _tokenize(node.title, parent_title, parser_hint, f"level{node.level}")
    return SectionQuery(
        query_text=query_text,
        parent_title=parent_title,
        keywords=keywords,
        expected_unit_types=["text", "table_row"],
    )


def _unit_source_scope(unit: material_service.MaterialUnit) -> Literal["task", "global"]:
    if isinstance(unit.metadata, dict):
        scope = str(unit.metadata.get("source_scope") or "").strip().lower()
        if scope == "global":
            return "global"
    if (unit.source_type or "").lower() == "global" or str(unit.id).startswith("global:"):
        return "global"
    return "task"


def retrieve_section_candidates(
    units: list[material_service.MaterialUnit],
    section_query: SectionQuery,
) -> list[material_service.MaterialUnit]:
    if not units:
        return []

    recalled: list[material_service.MaterialUnit] = []
    for unit in units:
        title = (unit.title or "").lower()
        content = (unit.content or "").lower()
        unit_type = (unit.unit_type or "text").lower()

        # image units are not prioritized for generate sections.
        if unit_type == "image":
            continue

        hit = False
        for keyword in section_query.keywords:
            lowered = keyword.lower()
            if lowered in title or lowered in content:
                hit = True
                break
        if section_query.parent_title:
            parent_lower = section_query.parent_title.lower()
            if parent_lower in title or parent_lower in content:
                hit = True

        if hit:
            recalled.append(unit)

    if not recalled:
        fallback = [unit for unit in units if (unit.unit_type or "text").lower() != "image"]
        return fallback[: min(8, len(fallback))]
    return recalled


def _merge_section_candidates(
    rule_units: list[material_service.MaterialUnit],
    semantic_hits: list[tuple[str, float]],
    all_units_by_id: dict[str, material_service.MaterialUnit],
) -> list[material_service.MaterialUnit]:
    ordered: list[material_service.MaterialUnit] = []
    seen: set[str] = set()
    for unit in rule_units:
        if unit.id in seen:
            continue
        seen.add(unit.id)
        ordered.append(unit)
    for unit_id, _ in semantic_hits:
        unit = all_units_by_id.get(unit_id)
        if not unit or unit.id in seen:
            continue
        if (unit.unit_type or "text").lower() == "image":
            continue
        seen.add(unit.id)
        ordered.append(unit)
    return ordered


def _unit_asset_path(unit: material_service.MaterialUnit) -> Optional[str]:
    if not isinstance(unit.metadata, dict):
        return None
    for key in ("path", "file_path", "asset_path", "url"):
        value = unit.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def retrieve_section_image_candidates(
    units: list[material_service.MaterialUnit],
    section_query: SectionQuery,
) -> list[material_service.MaterialUnit]:
    if not units:
        return []

    recalled: list[material_service.MaterialUnit] = []
    for unit in units:
        unit_type = (unit.unit_type or "").lower()
        if unit_type != "image":
            continue

        title = (unit.title or "").lower()
        content = (unit.content or "").lower()
        metadata_text = ""
        if isinstance(unit.metadata, dict):
            metadata_text = " ".join(
                str(item).lower()
                for item in (
                    unit.metadata.get("filename"),
                    unit.metadata.get("path"),
                    unit.metadata.get("caption"),
                )
                if item is not None
            )

        hit = False
        for keyword in section_query.keywords:
            lowered = keyword.lower()
            if lowered in title or lowered in content or lowered in metadata_text:
                hit = True
                break
        if section_query.parent_title and section_query.parent_title.lower() in metadata_text:
            hit = True
        if hit:
            recalled.append(unit)

    if recalled:
        return recalled
    return [unit for unit in units if (unit.unit_type or "").lower() == "image"][:2]


def _rank_image_candidates(
    section_query: SectionQuery,
    candidates: list[material_service.MaterialUnit],
    top_n: int = 2,
) -> list[material_service.MaterialUnit]:
    scored: list[tuple[int, material_service.MaterialUnit]] = []
    for unit in candidates:
        score = 0
        title = (unit.title or "").lower()
        metadata_path = (_unit_asset_path(unit) or "").lower()
        for keyword in section_query.keywords:
            lowered = keyword.lower()
            if lowered in title:
                score += 3
            if lowered in metadata_path:
                score += 2
        if section_query.parent_title and section_query.parent_title.lower() in metadata_path:
            score += 1
        if score <= 0:
            score = 1
        scored.append((score, unit))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [unit for _, unit in scored[: max(0, int(top_n))]]


def attach_images_to_section_draft(
    section_query: SectionQuery,
    image_candidates: list[material_service.MaterialUnit],
    top_n: int = 2,
) -> list[InlineAsset]:
    selected_images = _rank_image_candidates(section_query, image_candidates, top_n=top_n)
    assets: list[InlineAsset] = []
    for unit in selected_images:
        assets.append(
            InlineAsset(
                type="image",
                unit_id=unit.id,
                path=_unit_asset_path(unit),
                caption=(unit.title or "").strip() or None,
                position="after_text",
            )
        )
    return assets


def _rank_section_candidates(
    node: material_service.TemplateNode,
    section_query: SectionQuery,
    candidates: list[material_service.MaterialUnit],
    top_n: int = 3,
) -> list[SectionCandidate]:
    expected = {item.lower() for item in section_query.expected_unit_types}
    parent_lower = (section_query.parent_title or "").lower()
    node_title_lower = node.title.lower()

    ranked: list[SectionCandidate] = []
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
        if parent_lower and (parent_lower in title_lower or parent_lower in content_lower):
            score += 2
            reasons.append("parent_hit:+2")
        if expected and unit_type in expected:
            score += 1
            reasons.append("type_pref:+1")
        if title and title.strip().lower() not in {"untitled", "目录"}:
            score += 1
            reasons.append("useful_title:+1")
        source_scope = _unit_source_scope(unit)
        if source_scope == "task":
            score += 2
            reasons.append("scope_task:+2")
        else:
            reasons.append("scope_global:+0")

        keyword_hits = 0
        for keyword in section_query.keywords:
            lowered = keyword.lower()
            if lowered and (lowered in title_lower or lowered in content_lower):
                keyword_hits += 1
        if keyword_hits > 0:
            score += min(keyword_hits, 3)
            reasons.append(f"keyword_hits:+{min(keyword_hits, 3)}")

        # Block type-only matches without lexical evidence.
        if keyword_hits == 0 and not (node_title_lower in title_lower or node_title_lower in content_lower):
            continue

        if score <= 0:
            continue
        ranked.append(
            SectionCandidate(
                unit_id=unit.id,
                file_id=unit.file_id,
                title=title or "Untitled",
                unit_type=unit.unit_type or "text",
                score=score,
                reason=", ".join(reasons),
                source_scope=source_scope,
            )
        )

    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[: max(1, int(top_n))]


def generate_section_draft(
    task: material_service.Task,
    node: material_service.TemplateNode,
    section_query: SectionQuery,
    selected_units: list[material_service.MaterialUnit],
    selected_candidates: list[SectionCandidate],
    force_llm_context: bool = False,
    force_context_local: bool = False,
    llm_remote_only: bool = False,
) -> tuple[
    str,
    DraftStatus,
    Optional[str],
    Optional[str],
    float,
    Optional[str],
    list[str],
    FallbackSource,
]:
    def _normalize_heading_text(text: str) -> str:
        normalized = re.sub(r"\s+", "", (text or ""))
        normalized = re.sub(r"^[0-9]+(?:\.[0-9]+)*\s*", "", normalized)
        return normalized

    def _is_markdown_table_rule(line: str) -> bool:
        stripped = (line or "").strip()
        if "|" not in stripped:
            return False
        compact = stripped.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")
        return compact == ""

    def _table_like_to_sentence(line: str) -> str:
        cells = [item.strip() for item in line.split("|") if item.strip()]
        if len(cells) <= 1:
            return line.strip()
        return "；".join(cells)

    def _polish_draft_text(node_title: str, text: str) -> str:
        lines = [line.strip() for line in (text or "").splitlines()]
        cleaned: list[str] = []
        target = _normalize_heading_text(node_title)

        for raw in lines:
            if not raw:
                if cleaned and cleaned[-1] != "":
                    cleaned.append("")
                continue
            if _is_markdown_table_rule(raw):
                continue
            line = raw
            if line.startswith("- "):
                line = line[2:].strip()
            if line.count("|") >= 2:
                line = _table_like_to_sentence(line)
            if not line:
                continue
            cleaned.append(line)

        while cleaned and _normalize_heading_text(cleaned[0]) == target:
            cleaned.pop(0)
            while cleaned and cleaned[0] == "":
                cleaned.pop(0)

        # collapse empty lines
        compact: list[str] = []
        for item in cleaned:
            if item == "" and (not compact or compact[-1] == ""):
                continue
            compact.append(item)
        return "\n".join(compact).strip()

    def _compress_sentence(text: str, max_chars: int = 90) -> str:
        sentence = re.sub(r"\s+", " ", (text or "").strip())
        if not sentence:
            return ""
        if len(sentence) <= max_chars:
            return sentence
        return sentence[:max_chars].rstrip("，。；;,. ") + "。"

    def _extract_evidence_points(unit: material_service.MaterialUnit, max_points: int = 2) -> list[str]:
        raw = (unit.content or "").strip()
        if not raw:
            return []
        chunks = re.split(r"[。；;！!\n]", raw)
        points: list[str] = []
        for chunk in chunks:
            point = _compress_sentence(chunk)
            if not point:
                continue
            # skip obvious contract boilerplate
            if any(keyword in point for keyword in ["甲方", "乙方", "采购编号", "投标文件", "销售合同"]):
                continue
            points.append(point)
            if len(points) >= max_points:
                break
        return points

    def _build_evidence_slots(units: list[material_service.MaterialUnit]) -> dict[str, list[str]]:
        slot_order = ["background", "objective", "scope", "implementation", "acceptance"]
        slot_keywords = {
            "background": ["背景", "现状", "痛点", "需求", "驱动", "必要性"],
            "objective": ["目标", "价值", "成效", "指标", "提升", "能力"],
            "scope": ["范围", "边界", "纳入", "不纳入", "接口", "职责"],
            "implementation": ["实施", "计划", "步骤", "阶段", "里程碑", "交付"],
            "acceptance": ["验收", "测试", "标准", "检查", "评审", "输出件"],
        }
        slots: dict[str, list[str]] = {key: [] for key in slot_order}
        fallback_cursor = 0
        for unit in units[:4]:
            for point in _extract_evidence_points(unit, max_points=2):
                assigned = None
                for slot, keywords in slot_keywords.items():
                    if any(keyword in point for keyword in keywords):
                        assigned = slot
                        break
                if not assigned:
                    assigned = slot_order[fallback_cursor % len(slot_order)]
                    fallback_cursor += 1
                bucket = slots.setdefault(assigned, [])
                if point not in bucket:
                    bucket.append(point)
        for key in slot_order:
            slots[key] = slots.get(key, [])[:2]
        return slots

    def _render_slot_lines(slots: dict[str, list[str]]) -> str:
        slot_label = {
            "background": "建设背景",
            "objective": "建设目标",
            "scope": "实施范围",
            "implementation": "实施安排",
            "acceptance": "验收关注点",
        }
        fallback_line = {
            "background": "项目建设基于现状痛点与治理诉求展开，以提升交付质量与协同效率为总体导向。",
            "objective": "建设目标覆盖业务成效、技术能力与交付质量三方面，并以可验收指标作为落地约束。",
            "scope": "实施范围围绕核心业务域与关键接口边界定义，确保职责清晰、范围稳定。",
            "implementation": "实施安排按阶段推进并设置里程碑与关键输出件，保证进度与质量可控。",
            "acceptance": "验收关注点围绕标准符合性、功能完整性与交付件一致性进行闭环核查。",
        }
        lines: list[str] = []
        for slot in ["background", "objective", "scope", "implementation", "acceptance"]:
            points = slots.get(slot) or []
            content = "；".join(points) if points else fallback_line[slot]
            lines.append(f"【{slot_label[slot]}】{content}")
        return "\n".join(lines)

    def _compose_structured_draft(units: list[material_service.MaterialUnit]) -> str:
        parent = f"{section_query.parent_title}下" if section_query.parent_title else ""
        head = f"本节是本项目{parent}的重要章节。"
        objective = f"本节围绕“{node.title}”明确实施目标、范围边界与交付要求。"
        slots = _build_evidence_slots(units)
        body = _render_slot_lines(slots)
        closing = "上述内容用于形成可审阅实施稿，关键参数与名称请结合实际交付件复核。"
        return f"{head}\n\n{objective}\n\n{body}\n\n{closing}"

    def _template_fallback_text() -> str:
        parent = f"{section_query.parent_title} / " if section_query.parent_title else ""
        return (
            f"本章节围绕“{parent}{node.title}”展开，重点说明建设背景、目标、实施边界与验收关注点。\n"
            "建议在复核时补充：\n"
            "1. 关键功能与业务范围说明；\n"
            "2. 实施过程与里程碑成果；\n"
            "3. 与验收相关的配置、指标、附件和截图。\n"
            "当前内容由模板结构自动生成，请结合项目材料完善事实细节。"
        )

    def _task_context_fallback_text() -> str:
        def _section_kind(title: str) -> str:
            lowered = (title or "").lower()
            mapping = [
                ("读者对象", "audience"),
                ("术语", "glossary"),
                ("定义", "glossary"),
                ("目的", "purpose"),
                ("用户数量", "user_scale"),
                ("响应时间", "response_time"),
                ("资源利用", "resource_utilization"),
                ("接口性能", "interface_performance"),
                ("引言", "intro"),
                ("背景", "background"),
                ("目标", "objective"),
                ("范围", "scope"),
                ("方案", "solution"),
                ("实施", "implementation"),
                ("计划", "plan"),
                ("验收", "acceptance"),
                ("风险", "risk"),
                ("运维", "operation"),
                ("培训", "training"),
                ("售后", "support"),
                ("接口", "interface"),
                ("性能", "performance"),
            ]
            for key, kind in mapping:
                if key in lowered:
                    return kind
            return "general"

        def _kind_paragraphs(kind: str) -> tuple[str, str]:
            catalog: dict[str, tuple[str, str]] = {
                "intro": (
                    "本节说明项目立项背景、建设必要性及文档适用边界，明确后续章节的组织依据和读者预期。",
                    "建议重点交代项目现状痛点、建设驱动、交付目标与验收口径，形成后续实施方案的总纲。",
                ),
                "purpose": (
                    "本节用于定义项目实施交付的核心目的，明确本方案在项目落地中的定位与价值。",
                    "建议将“为什么做、做到什么程度、如何验收”三类问题在本节中交代清楚。",
                ),
                "audience": (
                    "本节用于界定文档读者范围，明确管理、业务、技术与实施角色的阅读关注点。",
                    "建议按角色给出阅读路径与责任边界，提升方案执行与协同效率。",
                ),
                "glossary": (
                    "本节用于统一关键术语、缩略语与系统名称口径，避免跨团队理解偏差。",
                    "建议优先定义项目核心名词、平台组件名与交付件相关术语。",
                ),
                "background": (
                    "本节聚焦项目建设背景，阐明业务现状、管理痛点与技术改造诉求，形成方案建设的合理性依据。",
                    "建议结合组织现状与业务流程，明确问题边界、改造优先级及阶段性价值目标。",
                ),
                "objective": (
                    "本节定义建设目标，覆盖业务目标、技术目标和交付目标，确保项目范围与成果可量化评估。",
                    "建议将目标拆解为可验收项，明确关键指标、阶段里程碑与达标条件。",
                ),
                "scope": (
                    "本节界定项目实施范围与边界，明确纳入与不纳入内容，避免执行过程中的范围漂移。",
                    "建议同步说明职责分工、接口边界和交付物清单，保障实施与验收口径一致。",
                ),
                "solution": (
                    "本节描述总体实施方案，说明技术路线、能力架构与关键模块协同关系。",
                    "建议突出方案可落地性，明确建设步骤、关键依赖与质量控制机制。",
                ),
                "implementation": (
                    "本节给出实施路径与执行安排，覆盖阶段任务、资源投入和进度控制方法。",
                    "建议结合里程碑计划，细化关键活动、交付节点和风险应对措施。",
                ),
                "plan": (
                    "本节说明项目计划安排，明确时间节奏、阶段目标和协同机制。",
                    "建议将计划与资源配置、评审机制、验收节点进行联动设计，确保可执行性。",
                ),
                "acceptance": (
                    "本节定义验收策略与标准，说明验收对象、方法、指标及输出件要求。",
                    "建议明确验收前置条件、测试场景和问题闭环流程，保障交付质量可核查。",
                ),
                "risk": (
                    "本节识别项目实施风险并提出控制方案，覆盖进度、质量、协同与合规维度。",
                    "建议对高风险项明确触发条件、应急预案及责任主体，形成可执行管控闭环。",
                ),
                "operation": (
                    "本节说明运维保障方案，涵盖运行监控、故障处置、变更管理和服务响应机制。",
                    "建议定义运维SLA与升级路径，确保系统稳定运行与持续优化。",
                ),
                "training": (
                    "本节说明培训计划与知识转移安排，确保业务与技术团队具备独立使用能力。",
                    "建议按角色设计培训内容、考核方式与交付材料，提升培训效果可验证性。",
                ),
                "support": (
                    "本节描述售后服务与保障机制，明确服务范围、响应时效和问题升级路径。",
                    "建议结合服务等级与运维协同机制，保障交付后持续稳定运行。",
                ),
                "interface": (
                    "本节说明接口建设与集成要求，明确接口清单、调用关系、数据口径与异常处理机制。",
                    "建议重点描述关键接口性能、可靠性和安全要求，支撑系统联调与验收。",
                ),
                "performance": (
                    "本节定义性能指标体系，明确并发、响应、资源利用等核心约束。",
                    "建议将性能目标映射至测试场景与验收标准，确保指标可测、可证、可追溯。",
                ),
                "user_scale": (
                    "本节用于明确用户规模相关指标，说明并发用户、在线用户与峰值场景的容量边界。",
                    "建议将用户规模与资源配置、扩展策略和压测口径进行一致化设计。",
                ),
                "response_time": (
                    "本节用于定义响应时间目标，明确不同业务操作的时延阈值与测量方法。",
                    "建议按核心流程拆分响应要求，并给出异常场景下的容错策略。",
                ),
                "resource_utilization": (
                    "本节用于约束资源利用指标，覆盖CPU、内存、存储与网络等关键资源使用目标。",
                    "建议将资源阈值与监控告警策略绑定，保障系统稳定运行与容量可控。",
                ),
                "interface_performance": (
                    "本节用于定义接口性能要求，明确接口吞吐、成功率与超时控制指标。",
                    "建议对关键接口给出压测方法、验收阈值与故障降级机制。",
                ),
                "general": (
                    "本节围绕项目交付目标组织内容，重点说明业务价值、建设边界与实施要求。",
                    "建议结合章节主题补充关键事实、执行路径与验收关注点，形成可审阅正文。",
                ),
            }
            return catalog.get(kind, catalog["general"])

        def _project_subject_from_title(title: str) -> str:
            value = (title or "").strip()
            for suffix in ["实施交付方案", "项目交付方案", "交付方案", "实施方案"]:
                if value.endswith(suffix):
                    value = value[: -len(suffix)].strip("（）() -")
            return value or (title or "").strip()

        section_path = f"{section_query.parent_title} / {node.title}" if section_query.parent_title else node.title
        doc_title = str(task.title or "当前项目实施交付方案").strip() or "当前项目实施交付方案"
        doc_desc = str(task.description or "").strip()
        context_line = f"《{doc_title}》中“{section_path}”章节明确本项目在该主题下的实施要求与交付口径。"
        if doc_desc:
            context_line += f"本次交付目标为：{doc_desc}。"
        kind = _section_kind(section_path)
        if kind == "purpose":
            subject = _project_subject_from_title(doc_title) or doc_title
            slots = _build_evidence_slots(selected_units)
            scope = "；".join((slots.get("scope") or [])[:2]) or "覆盖全流程业务场景与关键实施环节"
            objective = "；".join((slots.get("objective") or [])[:2]) or "明确总体目标、技术路线、交付标准与验收要求"
            acceptance = "；".join((slots.get("acceptance") or [])[:2]) or "形成可执行、可验收、可追溯的交付闭环"
            return (
                f"本文档为《{subject}实施交付方案》，旨在{objective}。"
                f"通过本方案实施，将{scope}，并以{acceptance}作为项目落地与阶段评审依据。"
                "本节内容用于统一项目实施目标与交付口径，为后续章节展开提供基线。"
            )
        body_a, body_b = _kind_paragraphs(kind)
        slots = _build_evidence_slots(selected_units)
        evidence_line = _render_slot_lines(slots)
        closing_by_kind = {
            "purpose": "本节结论将作为后续实施与验收章节的目标参照。",
            "audience": "本节定义的读者角色将用于后续章节职责与协同边界说明。",
            "glossary": "本节术语口径将作为后续技术与交付描述的统一表达基线。",
            "background": "本节背景分析将直接支撑后续目标、范围与实施策略设计。",
            "objective": "本节目标体系将作为实施计划和验收标准的核心约束。",
            "scope": "本节范围定义将作为实施执行与验收边界控制依据。",
            "implementation": "本节实施安排将作为项目推进与里程碑管控的执行基准。",
            "plan": "本节计划安排将作为资源投入与阶段评审的时间基线。",
            "acceptance": "本节验收要求将作为交付评估和问题闭环的判定依据。",
            "risk": "本节风险策略将作为项目执行过程中的持续治理依据。",
            "operation": "本节运维策略将作为交付后稳定运行与优化的执行依据。",
            "training": "本节培训安排将作为能力移交与上线保障的重要支撑。",
            "support": "本节售后机制将作为缺陷闭环与服务保障的执行标准。",
            "interface": "本节接口约束将作为联调测试与上线验收的关键边界。",
            "performance": "本节性能要求将作为压测验证与容量规划的目标基线。",
            "user_scale": "本节用户规模指标将作为容量规划与扩展策略输入。",
            "response_time": "本节响应指标将作为性能验收与优化迭代的核心约束。",
            "resource_utilization": "本节资源指标将作为运行监控与弹性治理的控制依据。",
            "interface_performance": "本节接口性能指标将作为联调稳定性与验收评估依据。",
            "general": "本节内容将作为当前主题下实施与验收协同的执行依据。",
        }
        closing_line = closing_by_kind.get(kind, closing_by_kind["general"])
        return (
            f"{context_line}\n"
            f"{body_a}\n"
            f"{body_b}\n"
            f"{evidence_line}\n"
            f"{closing_line}"
        )

    evidence_unit_ids = [unit.id for unit in selected_units]

    def _llm_context_fallback() -> tuple[str, float, Optional[str], Optional[str], Optional[str], Optional[str]]:
        from app.services import llm_client

        if not llm_client.llm_client.enabled:
            return "", 0.0, None, None, None, "llm_disabled"
        max_attempts = _read_int_env("SECTION_LLM_FALLBACK_MAX_ATTEMPTS", 6 if force_llm_context else 3)
        retry_sleep_s = float(os.getenv("SECTION_LLM_FALLBACK_RETRY_SECONDS", "2.5"))
        project_title = str(task.title or "").strip()
        project_desc = str(task.description or "").strip()
        section_path = f"{section_query.parent_title} / {node.title}" if section_query.parent_title else node.title
        system_prompt = (
            "你是项目实施交付方案写作助手。"
            "请仅根据项目上下文与章节标题，直接输出可交付的章节正文。"
            "风格要求：正式、专业、项目交付文体，不要输出提示语或写作说明。"
            "禁止出现“本节说明/建议补充/当前内容按任务上下文生成”等元描述。"
            "不要输出Markdown表格。"
            "输出 JSON: {\"draft_text\":\"...\",\"confidence\":0-1,\"risk_note\":\"...\"}。"
        )
        user_prompt = (
            f"文档名称: {project_title}\n"
            f"文档说明: {project_desc or '（未提供）'}\n"
            f"章节路径: {section_path}\n"
            "写作目标: 围绕本章节说明建设背景、目标、实施边界与验收关注点。"
        )
        for attempt in range(max_attempts):
            result = llm_client.llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            llm_trace = result.trace_id
            try:
                payload = json.loads(result.text or "{}")
            except Exception:
                payload = {}
            text = str(payload.get("draft_text") or "").strip()
            risk = str(payload.get("risk_note") or "").strip() or None
            try:
                conf = float(payload.get("confidence"))
            except Exception:
                conf = result.confidence
            conf = max(0.0, min(1.0, conf))
            if text:
                return text, conf, risk, llm_trace, result.provider
            error_text = str((result.usage or {}).get("error") or "")
            if "429" in error_text and attempt < max_attempts - 1:
                sleep_s = retry_sleep_s * (1.35 ** attempt)
                time.sleep(min(sleep_s, 25.0))
                continue
            if attempt < max_attempts - 1:
                time.sleep(min(retry_sleep_s, 3.0))
        return "", 0.0, None, None, None, (error_text or "llm_empty_response")

    if force_context_local and force_llm_context:
        return (
            _task_context_fallback_text(),
            "risky",
            "按任务上下文强制生成章节草稿（本次未等待远程模型结果）。",
            "如需更高事实贴合度，可关闭 force_context_local 后再次生成。",
            0.42,
            None,
            evidence_unit_ids,
            "llm_task_context",
        )

    weak_evidence = (
        len(selected_units) < 2
        or (max((item.score for item in selected_candidates), default=0) < 4)
    )

    if force_llm_context or not selected_units or weak_evidence:
        llm_text, llm_confidence, llm_risk_note, llm_trace_id, _provider, llm_error = _llm_context_fallback()
        if llm_text:
            llm_text = _polish_draft_text(node.title, llm_text)
            return (
                llm_text,
                "risky",
                llm_risk_note or "素材证据较弱，已按任务上下文生成章节草稿，请重点复核事实细节。",
                "建议补充同章节专有素材后重新生成，以提升可追溯性与准确度。",
                max(llm_confidence, 0.45),
                llm_trace_id,
                evidence_unit_ids,
                "llm_task_context",
            )
        if llm_remote_only:
            return (
                "",
                "missing",
                f"LLM远程生成失败：{llm_error or 'unknown_error'}",
                "请检查模型额度/网络后重试，或关闭 llm_remote_only 允许本地兜底。",
                0.0,
                llm_trace_id,
                evidence_unit_ids,
                "llm_task_context",
            )
        if force_llm_context:
            return (
                _task_context_fallback_text(),
                "risky",
                "LLM调用受限，已按任务上下文生成章节草稿。",
                "建议在模型额度恢复后重新生成，以获取更贴合素材的正文。",
                0.4,
                None,
                evidence_unit_ids,
                "llm_task_context",
            )
        if _fallback_template_enabled():
            return (
                _template_fallback_text(),
                "risky",
                "未召回到充分证据，且LLM不可用，已按章节标题生成兜底草稿。",
                "建议配置LLM或补充同章节素材后再次生成。",
                0.35,
                None,
                evidence_unit_ids,
                "template",
            )
        return (
            "",
            "missing",
            "未召回到可用素材，章节草稿无法生成。",
            "请补充与该章节相关的素材后重新生成。",
            0.0,
            None,
            evidence_unit_ids,
            "template",
        )

    snippets: list[str] = []
    for unit in selected_units:
        points = _extract_evidence_points(unit, max_points=2)
        if not points:
            continue
        snippets.append(f"- {unit.title}: {' '.join(points)}")

    if not snippets:
        if _fallback_template_enabled():
            return (
                _template_fallback_text(),
                "risky",
                "候选素材缺少正文内容，已按章节标题生成兜底草稿。",
                "建议补充可解析的文本材料后再次生成。",
                0.4,
                None,
                evidence_unit_ids,
                "template",
            )
        return (
            "",
            "missing",
            "候选素材内容为空，无法形成可审阅草稿。",
            "请检查素材解析结果或重新上传素材。",
            0.0,
            None,
            evidence_unit_ids,
            "template",
        )

    from app.services import llm_client

    draft_text = ""
    confidence = 0.0
    llm_trace_id: Optional[str] = None
    if llm_client.llm_client.enabled:
        system_prompt = (
            "你是项目验收文档章节草稿助手。请基于证据生成结构完整、可直接审阅的章节草稿。"
            "输出 JSON: {\"draft_text\":\"...\",\"confidence\":0-1}。"
            "优先完整成文，但不要输出与证据矛盾的事实。"
        )
        user_prompt = (
            f"node_title={node.title}\nquery={section_query.query_text}\n"
            f"evidences:\n" + "\n".join(snippets[:6])
        )
        result = llm_client.llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        llm_trace_id = result.trace_id
        try:
            import json

            payload = json.loads(result.text or "{}")
        except Exception:
            payload = {}
        draft_text = str(payload.get("draft_text") or "").strip()
        try:
            confidence = float(payload.get("confidence"))
        except Exception:
            confidence = result.confidence
        confidence = max(0.0, min(1.0, confidence))

    if not draft_text:
        draft_text = _compose_structured_draft(selected_units)
        confidence = max(confidence, 0.55)
    draft_text = _polish_draft_text(node.title, draft_text)

    fallback_source: FallbackSource = "task"
    if any(_unit_source_scope(unit) == "global" for unit in selected_units):
        fallback_source = "global"
    if fallback_source == "task" and len(selected_units) >= 2:
        return draft_text, "ready", None, None, confidence, llm_trace_id, evidence_unit_ids, fallback_source
    return (
        draft_text,
        "risky",
        "可用素材较少，草稿覆盖度可能不足。" if fallback_source == "task" else "使用了全局白皮书兜底，请重点复核项目专有事实。",
        "建议补充同章节素材，或人工扩写草稿内容。" if fallback_source == "task" else "建议补充当前任务专有素材并重新生成，减少跨项目泛化内容。",
        min(confidence, 0.72) if fallback_source == "global" else confidence,
        llm_trace_id,
        evidence_unit_ids,
        fallback_source,
    )


def generate_section_drafts(
    task_id: str,
    top_n: int = 3,
    strategy: str = "rule",
    force_llm_context: bool = False,
    force_context_local: bool = False,
    llm_remote_only: bool = False,
) -> SectionDraftGenerationResponse:
    task = material_service.get_task(task_id)
    all_nodes = material_service.list_template_nodes(task_id)
    generate_nodes = get_generate_nodes(task_id)
    task_units = material_service.list_material_units(task_id)
    global_units = _load_global_material_units(task_id)
    file_name_by_id = {item.file_id: (item.filename or "") for item in task.files}
    all_unit_by_id = {unit.id: unit for unit in [*task_units, *global_units]}

    results: list[SectionDraftResult] = []
    per_section_sleep = float(os.getenv("SECTION_LLM_REQUEST_INTERVAL_SECONDS", "1.2"))
    ready_count = 0
    risky_count = 0
    missing_count = 0

    for node in generate_nodes:
        section_query = build_section_query(node, all_nodes)
        filtered_task_units, out_task, blocked_task = _filter_units_for_section(
            node=node,
            units=task_units,
            file_name_by_id=file_name_by_id,
        )
        filtered_global_units, out_global, blocked_global = _filter_units_for_section(
            node=node,
            units=global_units,
            file_name_by_id=file_name_by_id,
        )
        blocked_source_types = sorted(set([*blocked_task, *blocked_global]))
        filtered_out_count = out_task + out_global

        task_recalled = retrieve_section_candidates(filtered_task_units, section_query)
        global_recalled = retrieve_section_candidates(filtered_global_units, section_query) if filtered_global_units else []
        recalled = [*task_recalled]
        seen_unit_ids = {unit.id for unit in recalled}
        for unit in global_recalled:
            if unit.id in seen_unit_ids:
                continue
            seen_unit_ids.add(unit.id)
            recalled.append(unit)

        if strategy == "hybrid":
            from app.services import semantic_retrieval_service

            semantic_hits_raw = semantic_retrieval_service.semantic_recall(
                task_id=task_id,
                query_text=section_query.query_text,
                top_k=max(8, int(top_n) * 2),
            )
            semantic_hits = [(item.unit_id, item.score) for item in semantic_hits_raw]
            recalled = _merge_section_candidates(
                rule_units=recalled,
                semantic_hits=semantic_hits,
                all_units_by_id=all_unit_by_id,
            )

        ranked = _rank_section_candidates(node, section_query, recalled, top_n=top_n)
        if not ranked and filtered_global_units:
            seed_units = filtered_global_units[: max(1, min(2, int(top_n)))]
            ranked = [
                SectionCandidate(
                    unit_id=unit.id,
                    file_id=unit.file_id,
                    title=unit.title or "Global Material",
                    unit_type=unit.unit_type or "text",
                    score=1,
                    reason="global_fallback_seed",
                    source_scope="global",
                )
                for unit in seed_units
            ]
        selected_unit_ids = [item.unit_id for item in ranked]
        selected_units = [all_unit_by_id[unit_id] for unit_id in selected_unit_ids if unit_id in all_unit_by_id]
        image_candidates = retrieve_section_image_candidates(task_units, section_query)
        inline_assets = attach_images_to_section_draft(section_query, image_candidates, top_n=2)

        (
            draft_text,
            draft_status,
            risk_note,
            manual_action,
            generation_confidence,
            llm_trace_id,
            evidence_unit_ids,
            fallback_source,
        ) = generate_section_draft(
            task=task,
            node=node,
            section_query=section_query,
            selected_units=selected_units,
            selected_candidates=ranked,
            force_llm_context=force_llm_context,
            force_context_local=force_context_local,
            llm_remote_only=llm_remote_only,
        )
        if force_llm_context and per_section_sleep > 0:
            time.sleep(min(per_section_sleep, 5.0))
        if draft_status == "missing" and inline_assets:
            draft_status = "risky"
            if not risk_note:
                risk_note = "仅召回到章节配图，正文证据不足。"
            if not manual_action:
                manual_action = "请补充可用于正文生成的文本素材。"
        if draft_status == "ready":
            ready_count += 1
        elif draft_status == "risky":
            risky_count += 1
        else:
            missing_count += 1

        results.append(
            SectionDraftResult(
                task_id=task_id,
                node_id=node.node_id,
                node_title=node.title,
                selected_unit_ids=selected_unit_ids,
                query_text=section_query.query_text,
                draft_text=draft_text,
                inline_assets=inline_assets,
                evidence_unit_ids=evidence_unit_ids,
                generation_confidence=generation_confidence,
                llm_trace_id=llm_trace_id,
                draft_status=draft_status,
                fallback_used=fallback_source in {"global", "template", "llm_task_context"},
                fallback_source=fallback_source,
                filtered_out_count=filtered_out_count,
                blocked_source_types=blocked_source_types,
                risk_note=risk_note,
                manual_action=manual_action,
            )
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    section_draft_repo.save_section_draft_results(
        task_id=task_id,
        results=[item.model_dump() for item in results],
        generated_at=generated_at,
    )
    return SectionDraftGenerationResponse(
        ok=True,
        task_id=task_id,
        result_count=len(results),
        ready_count=ready_count,
        risky_count=risky_count,
        missing_count=missing_count,
        generated_at=generated_at,
        results=results,
    )


def list_section_drafts(task_id: str) -> list[SectionDraftResult]:
    raw = section_draft_repo.list_section_draft_results(task_id)
    results: list[SectionDraftResult] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            results.append(SectionDraftResult.model_validate(item))
        except Exception:
            continue
    return results
