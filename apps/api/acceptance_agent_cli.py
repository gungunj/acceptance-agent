#!/usr/bin/env python3
import argparse
import json
import sys

from app.services import material_service
from app.services import export_service
from app.services import gap_review_service
from app.services import fill_review_service
from app.services import resolved_template_service
from app.services import section_draft_service


def cmd_resolve_fill_nodes(args: argparse.Namespace) -> int:
    result = material_service.resolve_fill_nodes(
        task_id=args.task_id,
        top_n=args.top_n,
        strategy=args.strategy,
    )
    print(
        json.dumps(
            {
                "ok": result.ok,
                "task_id": result.task_id,
                "result_count": result.result_count,
                "verified_count": result.verified_count,
                "weak_count": result.weak_count,
                "missing_count": result.missing_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_match_fill_nodes(args: argparse.Namespace) -> int:
    result = material_service.match_fill_nodes(
        task_id=args.task_id,
        top_n=args.top_n,
        strategy=args.strategy,
    )
    print(
        json.dumps(
            {
                "ok": result.ok,
                "task_id": result.task_id,
                "fill_node_count": result.fill_node_count,
                "matched_count": result.matched_count,
                "strategy": args.strategy,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_review_fill_results(args: argparse.Namespace) -> int:
    results = fill_review_service.list_reviewable_fill_results(task_id=args.task_id)
    print(json.dumps([item.model_dump() for item in results], ensure_ascii=False, indent=2))
    return 0


def cmd_show_fill_node_results(args: argparse.Namespace) -> int:
    return cmd_review_fill_results(args)


def cmd_generate_gaps(args: argparse.Namespace) -> int:
    result = gap_review_service.generate_gap_items(task_id=args.task_id)
    print(
        json.dumps(
            {
                "ok": result.ok,
                "task_id": result.task_id,
                "generated_count": result.generated_count,
                "high_count": result.high_count,
                "medium_count": result.medium_count,
                "low_count": result.low_count,
                "generated_at": result.generated_at,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_show_gap_items(args: argparse.Namespace) -> int:
    items = gap_review_service.list_gap_items(task_id=args.task_id)
    print(json.dumps([item.model_dump() for item in items], ensure_ascii=False, indent=2))
    return 0


def cmd_generate_section_drafts(args: argparse.Namespace) -> int:
    result = section_draft_service.generate_section_drafts(
        task_id=args.task_id,
        top_n=args.top_n,
        strategy=args.strategy,
    )
    print(
        json.dumps(
            {
                "ok": result.ok,
                "task_id": result.task_id,
                "result_count": result.result_count,
                "ready_count": result.ready_count,
                "risky_count": result.risky_count,
                "missing_count": result.missing_count,
                "generated_at": result.generated_at,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_show_section_drafts(args: argparse.Namespace) -> int:
    drafts = section_draft_service.list_section_drafts(task_id=args.task_id)
    print(json.dumps([item.model_dump() for item in drafts], ensure_ascii=False, indent=2))
    return 0


def cmd_build_resolved_template(args: argparse.Namespace) -> int:
    result = resolved_template_service.build_resolved_template(task_id=args.task_id)
    print(
        json.dumps(
            {
                "ok": result.ok,
                "task_id": result.task_id,
                "built_at": result.built_at,
                "node_count": result.node_count,
                "ready_count": result.ready_count,
                "risky_count": result.risky_count,
                "missing_count": result.missing_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_normalize_template_semantics(args: argparse.Namespace) -> int:
    result = material_service.normalize_template_semantics(task_id=args.task_id)
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    return 0


def cmd_build_material_embeddings(args: argparse.Namespace) -> int:
    result = material_service.build_material_embeddings(task_id=args.task_id)
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    return 0


def cmd_show_resolved_template(args: argparse.Namespace) -> int:
    result = resolved_template_service.get_resolved_template(task_id=args.task_id)
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
    return 0


def cmd_export_markdown(args: argparse.Namespace) -> int:
    result = export_service.export_markdown(task_id=args.task_id, rebuild=not args.no_rebuild)
    print(
        json.dumps(
            {
                "ok": result.ok,
                "task_id": result.task_id,
                "format": result.format,
                "filename": result.filename,
                "file_path": result.file_path,
                "generated_at": result.generated_at,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_show_export_markdown(args: argparse.Namespace) -> int:
    result = export_service.get_markdown_export(task_id=args.task_id)
    print(result.content)
    return 0


def cmd_export_html(args: argparse.Namespace) -> int:
    result = export_service.export_html(task_id=args.task_id, rebuild=not args.no_rebuild)
    print(
        json.dumps(
            {
                "ok": result.ok,
                "task_id": result.task_id,
                "format": result.format,
                "filename": result.filename,
                "file_path": result.file_path,
                "generated_at": result.generated_at,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_show_export_html(args: argparse.Namespace) -> int:
    result = export_service.get_html_export(task_id=args.task_id)
    print(result.content)
    return 0


def cmd_export_word(args: argparse.Namespace) -> int:
    result = export_service.export_word(task_id=args.task_id, rebuild=not args.no_rebuild)
    print(
        json.dumps(
            {
                "ok": result.ok,
                "task_id": result.task_id,
                "format": result.format,
                "filename": result.filename,
                "file_path": result.file_path,
                "generated_at": result.generated_at,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_show_export_word(args: argparse.Namespace) -> int:
    result = export_service.get_word_export(task_id=args.task_id)
    print(
        json.dumps(
            {
                "ok": result.ok,
                "task_id": result.task_id,
                "format": result.format,
                "filename": result.filename,
                "file_path": result.file_path,
                "generated_at": result.generated_at,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acceptance-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve-fill-nodes")
    resolve.add_argument("--task-id", required=True)
    resolve.add_argument("--top-n", type=int, default=5)
    resolve.add_argument("--strategy", choices=["rule", "hybrid"], default="rule")
    resolve.set_defaults(func=cmd_resolve_fill_nodes)

    match_fill = sub.add_parser("match-fill-nodes")
    match_fill.add_argument("--task-id", required=True)
    match_fill.add_argument("--top-n", type=int, default=5)
    match_fill.add_argument("--strategy", choices=["rule", "hybrid"], default="rule")
    match_fill.set_defaults(func=cmd_match_fill_nodes)

    normalize_semantics = sub.add_parser("normalize-template-semantics")
    normalize_semantics.add_argument("--task-id", required=True)
    normalize_semantics.set_defaults(func=cmd_normalize_template_semantics)

    build_embeddings = sub.add_parser("build-material-embeddings")
    build_embeddings.add_argument("--task-id", required=True)
    build_embeddings.set_defaults(func=cmd_build_material_embeddings)

    index_embeddings = sub.add_parser("index-material-embeddings")
    index_embeddings.add_argument("--task-id", required=True)
    index_embeddings.set_defaults(func=cmd_build_material_embeddings)

    review_fill = sub.add_parser("review-fill-results")
    review_fill.add_argument("--task-id", required=True)
    review_fill.set_defaults(func=cmd_review_fill_results)

    show_fill = sub.add_parser("show-fill-node-results")
    show_fill.add_argument("--task-id", required=True)
    show_fill.set_defaults(func=cmd_show_fill_node_results)

    generate_gaps = sub.add_parser("generate-gaps")
    generate_gaps.add_argument("--task-id", required=True)
    generate_gaps.set_defaults(func=cmd_generate_gaps)

    show_gaps = sub.add_parser("show-gap-items")
    show_gaps.add_argument("--task-id", required=True)
    show_gaps.set_defaults(func=cmd_show_gap_items)

    generate_section_drafts = sub.add_parser("generate-section-drafts")
    generate_section_drafts.add_argument("--task-id", required=True)
    generate_section_drafts.add_argument("--top-n", type=int, default=3)
    generate_section_drafts.add_argument("--strategy", choices=["rule", "hybrid"], default="rule")
    generate_section_drafts.set_defaults(func=cmd_generate_section_drafts)

    show_section_drafts = sub.add_parser("show-section-drafts")
    show_section_drafts.add_argument("--task-id", required=True)
    show_section_drafts.set_defaults(func=cmd_show_section_drafts)

    build_resolved_template = sub.add_parser("build-resolved-template")
    build_resolved_template.add_argument("--task-id", required=True)
    build_resolved_template.set_defaults(func=cmd_build_resolved_template)

    show_resolved_template = sub.add_parser("show-resolved-template")
    show_resolved_template.add_argument("--task-id", required=True)
    show_resolved_template.set_defaults(func=cmd_show_resolved_template)

    export_markdown = sub.add_parser("export-markdown")
    export_markdown.add_argument("--task-id", required=True)
    export_markdown.add_argument("--no-rebuild", action="store_true")
    export_markdown.set_defaults(func=cmd_export_markdown)

    show_export_markdown = sub.add_parser("show-export-markdown")
    show_export_markdown.add_argument("--task-id", required=True)
    show_export_markdown.set_defaults(func=cmd_show_export_markdown)

    export_html = sub.add_parser("export-html")
    export_html.add_argument("--task-id", required=True)
    export_html.add_argument("--no-rebuild", action="store_true")
    export_html.set_defaults(func=cmd_export_html)

    show_export_html = sub.add_parser("show-export-html")
    show_export_html.add_argument("--task-id", required=True)
    show_export_html.set_defaults(func=cmd_show_export_html)

    export_word = sub.add_parser("export-word")
    export_word.add_argument("--task-id", required=True)
    export_word.add_argument("--no-rebuild", action="store_true")
    export_word.set_defaults(func=cmd_export_word)

    show_export_word = sub.add_parser("show-export-word")
    show_export_word.add_argument("--task-id", required=True)
    show_export_word.set_defaults(func=cmd_show_export_word)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
