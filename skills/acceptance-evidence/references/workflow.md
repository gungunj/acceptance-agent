# Workflow

推荐执行顺序（CLI 负责确定性，OpenClaw 负责 LLM）：

0. 创建或自动获取 task_id  
- 显式创建：`acceptance-agent create-task --title "..." --description "..."`
- 或直接运行 skill 脚本，未传 `--task-id` 时会自动创建并缓存当前 task。

1. 解析模板  
`acceptance-agent parse-template --task-id <task_id>`

2. OpenClaw 对模板节点做语义标准化（LLM）  
输出：`template_nodes.normalized.json`

3. 写回模板节点  
`acceptance-agent save-template-nodes --task-id <task_id> --input template_nodes.normalized.json`

4. 解析素材  
`acceptance-agent parse-materials --task-id <task_id>`

5. 规则候选召回  
`acceptance-agent match-fill-rules --task-id <task_id>`

6. OpenClaw 做 rerank/fill/section draft（LLM）  
输出：
- `fill_results.generated.json`
- `section_drafts.generated.json`

7. 写回结果  
`acceptance-agent save-fill-results --task-id <task_id> --input fill_results.generated.json`  
`acceptance-agent save-section-drafts --task-id <task_id> --input section_drafts.generated.json`

8. 生成缺口并构建最终模板  
`acceptance-agent generate-gaps --task-id <task_id>`  
`acceptance-agent build-resolved-template --task-id <task_id>`

9. 导出文档  
`acceptance-agent export-markdown --task-id <task_id>`  
`acceptance-agent export-docx --task-id <task_id>`
