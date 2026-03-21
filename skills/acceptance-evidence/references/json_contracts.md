# JSON Contracts

以下文件由 OpenClaw 工作流生成，再通过 CLI 写回。

## 1) save-template-nodes

命令：

```bash
acceptance-agent save-template-nodes --task-id <task_id> --input template_nodes.normalized.json
```

支持结构：
- 直接数组：`TemplateNode[]`
- 或对象：`{ "nodes": TemplateNode[] }`

关键字段（最小）：
- `node_id`
- `task_id`
- `title`
- `node_type`
- `content_mode`

## 2) save-fill-results

命令：

```bash
acceptance-agent save-fill-results --task-id <task_id> --input fill_results.generated.json
```

支持结构：
- 直接数组：`FillNodeResult[]`
- 或对象：`{ "results": FillNodeResult[] }`

关键字段（最小）：
- `task_id`
- `node_id`
- `node_title`
- `selected_unit_id`（可空）
- `fill_status`（ready/risky/missing）

## 3) save-section-drafts

命令：

```bash
acceptance-agent save-section-drafts --task-id <task_id> --input section_drafts.generated.json
```

支持结构：
- 直接数组：`SectionDraftResult[]`
- 或对象：`{ "results": SectionDraftResult[] }`

关键字段（最小）：
- `task_id`
- `node_id`
- `node_title`
- `draft_text`
- `draft_status`（ready/risky/missing）
