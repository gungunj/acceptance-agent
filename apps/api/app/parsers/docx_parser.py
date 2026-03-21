import io
import re
import zipfile
from typing import Any
from xml.etree import ElementTree as ET


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def paragraph_text(paragraph: ET.Element, namespace: dict[str, str]) -> str:
    fragments = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
    return "".join(fragments).strip()


def style_value(paragraph: ET.Element, namespace: dict[str, str]) -> str:
    style = paragraph.find(".//w:pPr/w:pStyle", namespace)
    return style.get(f"{{{namespace['w']}}}val", "") if style is not None else ""


def extract_placeholder_fields(text: str) -> list[str]:
    matches = re.findall(r"\{\{\s*([^{}]+?)\s*\}\}", text)
    return [match.strip() for match in matches if match.strip()]


def is_fillable_text(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False

    patterns = [
        r"\{\{[^{}]+\}\}",
        r"\[\s*填写[^\]]*\]",
        r"\(\s*填写[^\)]*\)",
        r"_{3,}",
        r"x{3,}",
        r"待填写|待填|to be filled|tbd|todo",
    ]
    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)


def is_toc_paragraph(text: str, paragraph_style: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    if paragraph_style.startswith("TOC"):
        return True
    if normalized in {"目录", "contents"}:
        return True
    if re.search(r"\.{3,}\s*\d+\s*$", text):
        return True
    return False


def normalize_toc_title(raw_line: str) -> str:
    line = raw_line.strip()
    if not line:
        return ""
    # Remove trailing leader dots/page number patterns like "...... 12"
    line = re.sub(r"[\.·…\s]{2,}\d+\s*$", "", line)
    # Remove trailing page number appended without separator like "项目概述2"
    line = re.sub(r"(?<=[\u4e00-\u9fffA-Za-z\)])\s*\d+\s*$", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def infer_level_from_heading_number(title: str) -> int:
    chapter_match = re.match(r"^\s*第\s*[0-9一二三四五六七八九十百千]+\s*章", title)
    if chapter_match:
        return 1
    numbered_match = re.match(r"^\s*(\d+(?:\.\d+){1,3})\s+", title)
    if numbered_match:
        return numbered_match.group(1).count(".") + 1
    return 1


def extract_toc_entries(paragraph_details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    chapter_pattern = re.compile(
        r"^\s*(第\s*[0-9一二三四五六七八九十百千]+\s*章)\s*[:：.\-、]?\s*(.+)\s*$"
    )
    numbered_pattern = re.compile(r"^\s*(\d+(?:\.\d+){1,3})\s+(.+)\s*$")

    for paragraph_index, paragraph in enumerate(paragraph_details, start=1):
        text = str(paragraph.get("text") or "").strip()
        if not text:
            continue
        for line in [segment.strip() for segment in text.splitlines() if segment.strip()]:
            normalized = normalize_toc_title(line)
            if not normalized:
                continue
            if normalized in {"目录", "Contents"}:
                continue

            chapter_match = chapter_pattern.match(normalized)
            numbered_match = numbered_pattern.match(normalized)
            if not chapter_match and not numbered_match:
                continue

            if chapter_match:
                heading_number = chapter_match.group(1).replace(" ", "")
                heading_text = chapter_match.group(2).strip()
                title = f"{heading_number} {heading_text}".strip()
            else:
                heading_number = numbered_match.group(1)
                heading_text = numbered_match.group(2).strip()
                title = f"{heading_number} {heading_text}".strip()

            level = infer_level_from_heading_number(title)
            dedupe_key = f"{heading_number}|{heading_text}".lower()
            if dedupe_key in seen_titles:
                continue
            seen_titles.add(dedupe_key)
            entries.append(
                {
                    "title": title,
                    "heading_number": heading_number,
                    "level": level,
                    "paragraph_index": paragraph_index,
                    "raw_line": line,
                }
            )

    return entries


def detect_toc_like_doc(
    paragraph_details: list[dict[str, Any]], toc_entries: list[dict[str, Any]]
) -> bool:
    if not paragraph_details:
        return False
    if len(toc_entries) < 4:
        return False

    has_toc_word = any("目录" in str(item.get("text") or "") for item in paragraph_details)
    toc_style_count = sum(1 for item in paragraph_details if item.get("is_toc"))
    page_tail_count = sum(
        1
        for item in paragraph_details
        if re.search(r"(?:\.{2,}\s*\d+|[\u4e00-\u9fffA-Za-z\)]\s*\d+)\s*$", str(item.get("text") or ""))
    )

    toc_ratio = toc_style_count / max(1, len(paragraph_details))
    return has_toc_word or toc_ratio >= 0.35 or page_tail_count >= 3


def build_section_tree_from_toc(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        sections.append(
            {
                "title": entry["title"],
                "level": int(entry.get("level") or 1),
                "content": "",
                "block_count": 0,
                "section_index": index,
                "source_location": {
                    "synthetic_toc": True,
                    "heading_number": entry.get("heading_number"),
                    "paragraph_index": entry.get("paragraph_index"),
                    "raw_line": entry.get("raw_line"),
                },
            }
        )
    return sections


def build_compat_field_list_from_toc_sections(
    sections: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Compatibility layer for legacy field_list UI on TOC-only templates."""
    fields: list[dict[str, Any]] = []
    seen: set[str] = set()
    current_l1_title: str | None = None

    for section in sections:
        title = str(section.get("title") or "").strip()
        if not title:
            continue
        level = int(section.get("level") or 1)
        if level <= 1:
            current_l1_title = title
            continue

        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        fields.append(
            {
                "field": title,
                "source": "toc_section",
                "section": current_l1_title,
                "level": level,
                "context": title,
            }
        )

    return fields


def parse_docx_tables(root: ET.Element, namespace: dict[str, str]) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []

    for table_index, table in enumerate(root.findall(".//w:tbl", namespace), start=1):
        rows = table.findall(".//w:tr", namespace)
        parsed_rows: list[dict[str, Any]] = []
        max_column_count = 0

        for row_index, row in enumerate(rows, start=1):
            cells = row.findall(".//w:tc", namespace)
            parsed_cells: list[dict[str, Any]] = []

            for col_index, cell in enumerate(cells, start=1):
                paragraphs = cell.findall(".//w:p", namespace)
                text = " ".join(
                    [paragraph_text(paragraph, namespace) for paragraph in paragraphs]
                ).strip()
                fillable = is_fillable_text(text)
                parsed_cells.append(
                    {
                        "column_index": col_index,
                        "text": text,
                        "fillable": fillable,
                    }
                )

            max_column_count = max(max_column_count, len(parsed_cells))
            parsed_rows.append({"row_index": row_index, "cells": parsed_cells})

        header_cells = parsed_rows[0]["cells"] if parsed_rows else []
        headers = [cell["text"] for cell in header_cells]

        fillable_cells = []
        for row in parsed_rows:
            for cell in row["cells"]:
                if cell["fillable"]:
                    header_text = (
                        headers[cell["column_index"] - 1]
                        if cell["column_index"] - 1 < len(headers)
                        else ""
                    )
                    placeholders = extract_placeholder_fields(cell["text"])
                    fillable_cells.append(
                        {
                            "row_index": row["row_index"],
                            "column_index": cell["column_index"],
                            "header": header_text,
                            "text": cell["text"],
                            "placeholders": placeholders,
                        }
                    )

        tables.append(
            {
                "table_index": table_index,
                "row_count": len(parsed_rows),
                "column_count": max_column_count,
                "headers": headers,
                "rows": parsed_rows,
                "fillable_cell_count": len(fillable_cells),
                "fillable_cells": fillable_cells,
            }
        )

    return tables


class DocxParseError(Exception):
    pass


def parse_docx_sections(content: bytes) -> dict[str, Any]:
    """Parses a DOCX into heading-based sections for both template/material use."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            document_xml = archive.read("word/document.xml")
            core_xml = (
                archive.read("docProps/core.xml")
                if "docProps/core.xml" in archive.namelist()
                else None
            )
    except (KeyError, zipfile.BadZipFile) as exc:
        raise DocxParseError("invalid docx zip") from exc

    word_ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        raise DocxParseError("invalid document.xml") from exc

    body = root.find(".//w:body", word_ns)
    if body is None:
        raise DocxParseError("missing body")

    blocks: list[dict[str, Any]] = []
    for child in list(body):
        kind = local_name(child.tag)
        if kind == "p":
            text = paragraph_text(child, word_ns)
            if not text:
                continue
            blocks.append(
                {
                    "kind": "paragraph",
                    "text": text,
                    "style": style_value(child, word_ns) or None,
                }
            )
        elif kind == "tbl":
            # Flatten table cells in reading order.
            rows = child.findall(".//w:tr", word_ns)
            table_lines: list[str] = []
            for row in rows:
                cells = row.findall(".//w:tc", word_ns)
                cell_texts: list[str] = []
                for cell in cells:
                    paragraphs = cell.findall(".//w:p", word_ns)
                    text = " ".join(
                        [paragraph_text(paragraph, word_ns) for paragraph in paragraphs]
                    ).strip()
                    cell_texts.append(text)
                if any(cell_texts):
                    table_lines.append(" | ".join(cell_texts))
            if table_lines:
                blocks.append({"kind": "table", "text": "\n".join(table_lines)})

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_heading: str | None = None
    current_level: int = 1

    for block in blocks:
        if block["kind"] == "paragraph":
            style = block.get("style") or ""
            if isinstance(style, str) and style.startswith("Heading"):
                match = re.search(r"Heading(\d+)", style)
                current_level = int(match.group(1)) if match else 1
                current_heading = block["text"]
                current = {
                    "title": current_heading,
                    "level": current_level,
                    "content": "",
                    "block_count": 0,
                    "source_location": {
                        "heading_style": style,
                    },
                }
                sections.append(current)
                continue

        if current is None:
            # Content before first heading goes into a synthetic section.
            current_heading = "Untitled"
            current = {
                "title": current_heading,
                "level": 1,
                "content": "",
                "block_count": 0,
                "source_location": {"synthetic": True},
            }
            sections.append(current)

        current["content"] = (
            (current["content"] + "\n" if current["content"] else "") + block["text"]
        )
        current["block_count"] += 1

    title = None
    if core_xml:
        try:
            core_root = ET.fromstring(core_xml)
            dc_ns = {"dc": "http://purl.org/dc/elements/1.1/"}
            title_node = core_root.find(".//dc:title", dc_ns)
            title = (
                title_node.text.strip()
                if title_node is not None and title_node.text
                else None
            )
        except ET.ParseError:
            title = None

    # Add section_index for stable referencing.
    for index, section in enumerate(sections, start=1):
        section["section_index"] = index

    return {"title": title, "sections": sections, "root": root, "word_ns": word_ns}


def parse_docx_template(content: bytes) -> dict[str, Any]:
    parsed = parse_docx_sections(content)
    root = parsed["root"]
    word_ns = parsed["word_ns"]

    paragraphs: list[str] = []
    headings: list[str] = []
    paragraph_details: list[dict[str, Any]] = []
    placeholder_count = 0
    current_section: str | None = None

    for paragraph in root.findall(".//w:p", word_ns):
        text = paragraph_text(paragraph, word_ns)
        if not text:
            continue

        paragraphs.append(text)
        fillable = is_fillable_text(text)
        placeholder_count += text.count("{{")
        style_val = style_value(paragraph, word_ns)
        toc_flag = is_toc_paragraph(text, style_val)
        if style_val.startswith("Heading"):
            current_section = text

        paragraph_details.append(
            {
                "text": text,
                "style": style_val or None,
                "fillable": fillable,
                "is_toc": toc_flag,
                "placeholders": extract_placeholder_fields(text),
                "section": current_section,
            }
        )

        if style_val.startswith("Heading"):
            headings.append(text)

    tables = parse_docx_tables(root, word_ns)
    table_fillable_cells = sum(table["fillable_cell_count"] for table in tables)
    paragraph_fillable_count = sum(
        1 for paragraph in paragraph_details if paragraph["fillable"]
    )
    toc_entries = extract_toc_entries(paragraph_details)
    toc_like_doc = detect_toc_like_doc(paragraph_details, toc_entries)
    toc_only = bool(paragraph_details) and all(
        paragraph["is_toc"] for paragraph in paragraph_details
    )
    if toc_like_doc:
        toc_only = True

    parsed_sections = parsed["sections"]
    if toc_like_doc and toc_entries:
        parsed_sections = build_section_tree_from_toc(toc_entries)

    if toc_only:
        fill_recommendation = {
            "mode": "fill_full_body",
            "reason": "document_contains_toc_structure",
            "description": "仅检测到目录内容，需填充目录对应的全部正文内容。",
        }
        modules_to_keep: list[str] = []
    else:
        fill_recommendation = {
            "mode": "fill_marked_fields",
            "reason": "template_contains_content_blocks",
            "description": "模板存在已填写内容，仅填充标记字段，已完成模块保留。",
        }
        modules_to_keep = []
        for paragraph in paragraph_details:
            if (
                paragraph.get("style")
                and str(paragraph["style"]).startswith("Heading")
                and not paragraph["fillable"]
            ):
                modules_to_keep.append(paragraph["text"])
        modules_to_keep = list(dict.fromkeys(modules_to_keep))

    field_candidates: list[dict[str, Any]] = []
    for paragraph in paragraph_details:
        if paragraph["placeholders"]:
            for field_name in paragraph["placeholders"]:
                field_candidates.append(
                    {
                        "field": field_name,
                        "source": "paragraph",
                        "context": paragraph["text"],
                        "section": paragraph.get("section"),
                    }
                )

    for table in tables:
        for cell in table["fillable_cells"]:
            if cell["placeholders"]:
                for field_name in cell["placeholders"]:
                    field_candidates.append(
                        {
                            "field": field_name,
                            "source": "table",
                            "table_index": table["table_index"],
                            "header": cell["header"],
                            "cell_text": cell["text"],
                        }
                    )
            else:
                fallback_field = (cell["header"] or cell["text"]).strip()
                if fallback_field:
                    field_candidates.append(
                        {
                            "field": fallback_field,
                            "source": "table",
                            "table_index": table["table_index"],
                            "header": cell["header"],
                            "cell_text": cell["text"],
                        }
                    )

    field_list: list[dict[str, Any]] = []
    seen_fields: set[str] = set()
    for item in field_candidates:
        key = item["field"].lower()
        if key in seen_fields:
            continue
        seen_fields.add(key)
        field_list.append(item)

    if not field_list and toc_like_doc and parsed_sections:
        field_list = build_compat_field_list_from_toc_sections(parsed_sections)

    title = parsed["title"]

    return {
        "type": "docx",
        "title": title,
        "paragraph_count": len(paragraphs),
        "heading_count": len(headings),
        "headings": headings[:12],
        "placeholder_count": placeholder_count,
        "preview_paragraphs": paragraphs[:8],
        "tables": tables,
        "table_count": len(tables),
        "fillable_paragraph_count": paragraph_fillable_count,
        "fillable_table_cell_count": table_fillable_cells,
        "fill_recommendation": fill_recommendation,
        "modules_to_keep": modules_to_keep,
        "field_list": field_list,
        "sections": parsed_sections,
        "toc_like": toc_like_doc,
        "toc_entry_count": len(toc_entries),
    }
