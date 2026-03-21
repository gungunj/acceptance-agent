# Input Layout

推荐为每个任务准备独立目录（示例：`tasks/<task_id>/`）：

```text
tasks/<task_id>/
  template/
    template.docx
  materials/
    SDD.docx
    whitepaper.pdf
    screenshots/
      login-page.png
      dashboard-overview.png
  llm_outputs/
    template_nodes.normalized.json
    fill_results.generated.json
    section_drafts.generated.json
  exports/
```

命名建议：
- 模板文件：`template.docx`
- 截图：`<module>-<scene>.png`，例如 `user-center-list.png`
- LLM 输出：固定使用 `llm_outputs/` 下三类 JSON，便于脚本写回

最小素材清单：
- 1 份模板文档（docx）
- 业务与技术素材（说明文档、设计文档等）
- 关键页面截图（若暂缺可留空，后续通过 gap 清单补齐）
