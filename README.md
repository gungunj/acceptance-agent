# acceptance-agent

轻量 monorepo，包含：

- `apps/web`: Next.js 前端
- `apps/api`: FastAPI 后端

## 开发方式

先安装根目录工具依赖：

```bash
npm install
```

安装前端依赖：

```bash
npm run install:web
```

安装 API 的 Python 虚拟环境和依赖：

```bash
npm run install:api
```

或者一次性完成初始化：

```bash
npm run bootstrap
```

在仓库根目录一键启动前后端：

```bash
npm run dev
```

默认端口：

- Web: `http://localhost:3000`
- API: `http://127.0.0.1:8000`

当前首页会请求 API 的 `GET /hello` 接口并展示返回结果。

## CLI 安装与使用

在仓库根目录执行：

```bash
pip install -e .
```

建议在虚拟环境中执行；若 `pip install -e .` 报 editable 安装错误，请先升级 pip：

```bash
python -m pip install --upgrade pip setuptools wheel
```

安装后可直接使用：

```bash
acceptance-agent --help
acceptance-agent create-task --title <title> --description <description>
acceptance-agent parse-template --task-id <task_id>
acceptance-agent parse-materials --task-id <task_id>
acceptance-agent match-fill-rules --task-id <task_id>
acceptance-agent resolve-fill-nodes --task-id <task_id>
acceptance-agent generate-section-drafts --task-id <task_id>
acceptance-agent generate-gaps --task-id <task_id>
acceptance-agent save-template-nodes --task-id <task_id> --input <template_nodes.json>
acceptance-agent save-fill-results --task-id <task_id> --input <fill_results.json>
acceptance-agent save-section-drafts --task-id <task_id> --input <section_drafts.json>
acceptance-agent build-resolved-template --task-id <task_id>
acceptance-agent export-markdown --task-id <task_id>
acceptance-agent export-docx --task-id <task_id>
```

说明：CLI 采用确定性模式，不直接调用 LLM。  
需要 LLM 的步骤（语义标准化、重排、生成）建议在 OpenClaw workflow 中完成，再通过 `save-*` 命令写回。

OpenClaw skill 壳位于：

```text
skills/acceptance-evidence/
```

其脚本仅调用 `acceptance-agent`，不复制业务实现。

## LLM Provider 配置

当前后端支持可切换 provider，默认 `bigmodel`。未配置 key 时会自动 fallback（链路可运行但不调用远端模型）。

```bash
# provider: bigmodel | openai
export LLM_PROVIDER=bigmodel

# BigModel (默认)
export BIGMODEL_API_KEY=your_key
export BIGMODEL_BASE_URL=https://open.bigmodel.cn/api/paas/v4
export BIGMODEL_CHAT_MODEL=glm-5-turbo
export BIGMODEL_EMBEDDING_MODEL=embedding-3
export BIGMODEL_RERANK_MODEL=rerank

# OpenAI (兼容保留)
export OPENAI_API_KEY=your_key
export OPENAI_CHAT_MODEL=gpt-4o-mini
export OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

可以先复制示例配置：

```bash
cp apps/api/.env.example apps/api/.env
```

启动时会执行一次“LLM 启动前自检”，在日志中输出：
- provider 是否有效
- key 是否缺失
- 模型名是否疑似错误

并且 `GET /health` 会返回 preflight 摘要（`warning_count/error_count`）。

## 常用脚本

```bash
npm run dev:web
npm run dev:api
npm run install:web
npm run install:api
npm run lint
```
