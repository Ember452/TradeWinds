# TradeWinds 信风

> 把风声，吹给你。

**TradeWinds** 是一个 AI 信息研究助理：把你用自然语言描述的兴趣，变成持续、精准、带来源的信息流。

- **对话咨询** — 像和研究员聊天一样提问，Agent 多步检索、交叉验证，回答附原文引用
- **主题订阅** — 一句话创建监控主题（如"近一周的 Agent 新技术"），Agent 持续跟踪多信息源
- **信息 Feed** — 每条推送带原文链接、摘要、推荐理由与相关度评分
- **邮件推送** — 订阅主题执行后自动汇总邮件，含退订链接

## 状态

🚧 MVP 开发中：后端(M1-M4)与前端(5.1-5.3)代码完成,首次上线待基础设施。

## 本地开发

前置:Python 3.13+、[uv](https://docs.astral.sh/uv/)、Node 22+。

```bash
# 后端(单元测试不需要数据库/Redis)
make test          # = uv run pytest -m "not integration"
make lint && make type

# 前端
cd frontend && npm install && npm run build

# 本地全栈(需要 PostgreSQL/Redis 与 .env,见 .env.example)
make migrate       # alembic upgrade head
make dev           # uvicorn,http://localhost:8000
make frontend      # vite dev server(代理 /api 到 8000)

# 全部测试(CI 亦跑此套件:集成测试连真实 PG/Redis)
make test-all
```

## 部署

`docker compose up -d --build` 起 api/worker/beat/postgres/redis/caddy 全栈;HTTPS 见 [deploy/Caddyfile](deploy/Caddyfile);部署流水线(.github/workflows/deploy.yml)为手动触发,需配置 `DEPLOY_HOST`/`DEPLOY_USER`/`DEPLOY_SSH_KEY` Secrets。

## 技术栈

Python 3.13 · FastAPI · PostgreSQL · Redis · Celery · 自研 Agent 编排层（OpenAI-compatible） · React SPA · Docker

## 文档

| 文档 | 内容 |
|---|---|
| [设计文档](docs/design.md) | 产品定位、多 Agent 架构、数据与 API 概要、技术选型、里程碑 |
| [实施计划](docs/plans/2026-09-06-mvp-implementation-plan.md) | MVP 分 Phase 实施计划与实施记录(偏差) |
| [架构文档](docs/architecture.md) | 运行时架构、模块依赖规则、接口契约 |
| [学习文档](docs/study/) | 每个知识点的深入讲解(编排层/SSE/推送/迁移等) |
| [AGENTS.md](AGENTS.md) | AI/协作者开发准则与工程规范 |

## License

暂未确定，发布前补充。
