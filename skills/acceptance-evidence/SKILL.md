---
name: acceptance-evidence
description: Generate project acceptance documents with deterministic CLI pipelines and OpenClaw-managed LLM steps.
metadata:
  openclaw:
    requires:
      python: ">=3.9"
      commands:
        - acceptance-agent
      writable_paths:
        - apps/api/data
        - apps/api/uploads
        - exports
        - skills/acceptance-evidence/.state
---

# acceptance-evidence

## Summary
最小可用的 OpenClaw workspace skill 壳。  
skill 不复制业务逻辑，只调用仓库内 `acceptance-agent` CLI。

职责边界：
- CLI / `agent_core`：确定性流程（解析、规则匹配、结果写回、构建、导出）
- OpenClaw workflow：LLM 步骤（语义标准化、query expansion、rerank、fill 文本生成、section 草稿生成）

## Scripts
- `scripts/create_task.sh`
- `scripts/parse_template.sh`
- `scripts/parse_materials.sh`
- `scripts/save_template_nodes.sh`
- `scripts/save_fill_results.sh`
- `scripts/save_section_drafts.sh`
- `scripts/build_resolved_template.sh`
- `scripts/export_markdown.sh`
- `scripts/export_docx.sh`
- `scripts/run_full_pipeline.sh`

## References
- `references/input_layout.md`
- `references/json_contracts.md`
- `references/workflow.md`

## Invocation Notes
- 脚本只调用 `acceptance-agent ...`，不复制业务逻辑。
- 若未提供 `--task-id`，脚本会自动创建并复用任务 ID（保存在 `skills/acceptance-evidence/.state/current_task_id`）。
- 所有写回脚本使用 `--input <json_file>`。
- `run_full_pipeline.sh` 是纯确定性流程，不包含 LLM 调用。
