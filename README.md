# TradeWinds 信风

> 把风声，吹给你。

**TradeWinds** 是一个 AI 信息研究助理：把你用自然语言描述的兴趣，变成持续、精准、带来源的信息流。

- **对话咨询** — 像和研究员聊天一样提问，Agent 多步检索、交叉验证，回答附原文引用
- **主题订阅** — 一句话创建监控主题（如"近一周的 Agent 新技术"），Agent 持续跟踪多信息源
- **信息 Feed** — 每条推送带原文链接、摘要、推荐理由与相关度评分
- **主动推送** — 高价值内容即时邮件推送；周期性聚合为日报/周报

## 状态

🚧 开发中。当前处于设计阶段，尚未开始实现。

## 技术栈

Python 3.13 · FastAPI · PostgreSQL · Redis · Celery · 自研 Agent 编排层（OpenAI-compatible） · React SPA · Docker

## 文档

| 文档 | 内容 |
|---|---|
| [设计文档](docs/design.md) | 产品定位、多 Agent 架构、数据与 API 概要、技术选型、里程碑 |
| [扩展计划](docs/scaling-plan.md) | 从单实例到规模化的演进路线与触发信号 |
| [AGENTS.md](AGENTS.md) | AI/协作者开发准则与工程规范 |

## License

暂未确定，发布前补充。
