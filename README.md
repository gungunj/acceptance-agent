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

## 常用脚本

```bash
npm run dev:web
npm run dev:api
npm run install:web
npm run install:api
npm run lint
```
