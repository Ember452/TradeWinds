# TradeWinds 信风

> 把风声，吹给你。

**TradeWinds** 是一个 AI 信息研究助理：把你用自然语言描述的兴趣，变成持续、精准、带来源的信息流。

- **对话咨询** — 像和研究员聊天一样提问，Agent 多步检索、交叉验证，回答附原文引用
- **主题订阅** — 一句话创建监控主题（如"近一周的 Agent 新技术"），Agent 持续跟踪多信息源
- **信息 Feed** — 每条推送带原文链接、摘要、推荐理由与相关度评分
- **邮件推送** — 订阅主题执行后自动汇总邮件，含退订链接

## 状态

✅ 功能完整 · 本地可演示（定位为面试演示项目，不追求真实上线运营）：订阅检索管道、Feed、邮件推送、对话研究 Agent、周期报告与分享页、即时推送与抑制、自定义 RSS、跨会话记忆、RAG 已读检索全部落地。

## 快速演示

需要 Docker 与 [uv](https://docs.astral.sh/uv/)、Node 22+（前端热更新可选）。

```bash
cp .env.example .env    # 演示默认值即可跑;LLM key 留空时演示数据已预置,真实检索需填 key
make demo               # 一键起全栈(api/worker/beat/postgres/redis/caddy/mailpit)+迁移+演示数据
```

起来之后：

| 入口 | 地址 | 说明 |
|---|---|---|
| 前端 | http://localhost | 订阅/Feed/对话三个界面，用演示账号登录 |
| API 文档 | http://localhost/api/docs | OpenAPI |
| Mailpit 收件箱 | http://localhost:8025 | 演示邮箱：汇总邮件、即时推送、报告推送都在这里看 |

演示账号：`demo@tradewinds.local` / `demo12345`（由 `make seed` 创建，含预置主题、条目、报告与会话；幂等可重跑）。要体验真实检索→打分→推送链路，在 `.env` 配置 LLM key 后在主题页手动执行一次。

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

## 部署与运维

docker compose 起 api/worker/beat/postgres/redis/caddy/mailpit 全栈；Caddy 作反向代理入口（公网 HTTPS 上线不在当前定位，见 [design.md](docs/design.md) 第 1 节）；部署流水线(.github/workflows/deploy.yml)保留为手动触发。备份/恢复脚本与运维设计见 [deploy/](deploy/) 与 [运维 Runbook](docs/runbook.md)。

## 技术栈

Python 3.13 · FastAPI · PostgreSQL · Redis · Celery · 自研 Agent 编排层（OpenAI-compatible） · React SPA · Docker

## 文档

| 文档 | 内容 |
|---|---|
| [设计文档](docs/design.md) | 产品定位、多 Agent 架构、数据与 API 概要、技术选型、里程碑 |
| [实施计划](docs/plans/2026-09-06-mvp-implementation-plan.md) | MVP 分 Phase 实施计划与实施记录(偏差) |
| [演示就绪计划](docs/plans/2026-09-06-demo-readiness-plan.md) | 演示补全(报告推送接线/Mailpit/seed/一键演示)实施计划与记录 |
| [架构文档](docs/architecture.md) | 运行时架构、模块依赖规则、接口契约 |
| [学习文档](docs/study/) | 每个知识点的深入讲解(编排层/SSE/推送/迁移等) |
| [AGENTS.md](AGENTS.md) | AI/协作者开发准则与工程规范 |

## License

暂未确定，发布前补充。
