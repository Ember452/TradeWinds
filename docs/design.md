# TradeWinds 设计文档

| | |
|---|---|
| 版本 | v0.1（草案，待评审） |
| 日期 | 2026-09-06 |
| 状态 | 设计中 |
| 相关代码 | 本仓库（尚未开始实现） |

## 1. 背景与定位

信息获取存在两类真实痛点：

1. **主动检索成本高**：想了解"最近 Agent 领域有什么新进展"，需要跨 arXiv、Hacker News、GitHub、技术博客等多个来源反复搜索、筛选、阅读，一次认真的调研耗时 1-2 小时。
2. **被动订阅不精准**：RSS/Newsletter 是"源级订阅"而非"主题级订阅"——订阅一个源会收到大量无关内容，而真正关心的细分主题（如"具身智能的抓取策略"）没有对应的信息源。

**TradeWinds（信风）** 是一个「AI 信息研究助理」：

- **对话咨询**：用户像和研究员聊天一样提问，Agent 多步检索、交叉验证，带原文引用地回答；
- **主题订阅**：用户用自然语言创建监控主题，Agent 持续跟踪，产出带原文链接、摘要与推荐理由的条目流（Feed）；
- **周期报告**：按周期将条目聚合成结构化日报/周报，存档可分享；
- **主动推送**：高价值条目（超阈值评分）即时推送，不等周期报告。

一句话定位：**把自然语言描述的兴趣，变成持续、精准、带来源的信息流。**

slogan：把风声，吹给你。

## 2. 目标与非目标

### 2.1 目标

- G1：对话式研究 Agent，回答中每条关键结论均带可点击的原文引用
- G2：主题订阅全流程可用：创建 → 定时检索 → Feed 呈现 → 邮件推送
- G3：单实例部署即可稳定运行，核心链路有降级与重试，单信息源故障不影响整体出报
- G4：LLM 成本可估算、可控制（分级模型 + 缓存 + 配额）
- G5：可真实运营：注册/登录、配额限制、公网可访问、可观测（日志/健康检查/错误上报）

### 2.2 非目标（明确不做）

- N1：实时流式监控（新内容秒级推送）——周期任务 + 阈值推送已满足需求
- N2：全文托管与版权内容再分发——只存摘要与链接，指向原文
- N3：移动端 App——Web 优先，邮件作为主要触达渠道
- N4：团队协作、多角色权限——单用户视角
- N5：自建搜索引擎或爬虫框架——使用各来源的公开 API 与通用网页抓取

## 3. 用户旅程

### 3.1 订阅用户（主路径）

1. 注册登录，创建主题："近一周的 Agent 新技术"，设置频率（每天/每周）
2. 系统将主题编译为检索计划；到达执行时间后，后台 Agent 检索多源、过滤、摘要
3. 用户在 Feed 页看到条目：**原文链接 + 标题 + 摘要 + 推荐理由 + 相关度评分**，点击进入原文
4. 周期结束生成报告（日报/周报），推送至邮箱
5. 评分超过阈值的条目即时邮件推送（带抑制策略，避免打扰）

### 3.2 咨询用户

1. 在对话页提问："Agent 框架最近有什么值得看的新东西？"
2. Agent 拆解问题 → 调用检索工具 → 抓取原文 → 综合回答，流式输出，结论附引用
3. 用户可追问、可要求深挖某个条目

## 4. 系统架构

```
┌─────────────────────────── FastAPI 应用（单实例） ───────────────────────────┐
│                                                                             │
│  API 层：auth / topics / items / reports / conversations (SSE) / health     │
│                                                                             │
│  ┌────────── Agent 层（共享工具与记忆） ──────────┐                          │
│  │  Planner   自然语言 → 结构化检索计划           │                          │
│  │  Retriever 带工具循环的检索执行体              │                          │
│  │  Analyst   相关性打分 + 跨源去重聚类（便宜模型）│                          │
│  │  Editor    摘要 / 推荐理由 / 报告生成（好模型） │                          │
│  └────────────────┬────────────────────────────┘                          │
│                   │                                                        │
│  工具层：search_arxiv / search_hn / search_github / search_web / fetch_page │
│                                                                             │
│  调度层：APScheduler（订阅任务 + 报告任务 + 推送任务）                        │
│  推送层：邮件（SMTP）+ 站内通知；抑制策略（同簇 24h 不重复）                  │
└──────────────┬──────────────────────────────────────────────────────────────┘
               │
        PostgreSQL（业务数据 + 已见 URL/内容指纹）
```

### 4.1 Agent 角色与职责

| 角色 | 输入 | 输出 | 模型档位 | 触发方式 |
|---|---|---|---|---|
| Planner | 主题自然语言描述 | 检索计划（关键词组、源选择、时间窗、判定标准） | 中 | 主题创建/编辑时 |
| Retriever | 检索计划 或 对话问题 | 候选条目集合（含原文内容） | 低（工具循环本身不需要强模型） | 定时任务 / 对话请求 |
| Analyst | 候选条目 + 主题描述 | 评分（0-10）、去重聚类、过滤 | 低（便宜模型） | 检索完成后 |
| Editor | 通过过滤的条目 | 单条摘要+推荐理由；周期报告 | 高 | 打分完成后 / 报告任务 |

设计原则：

- **对话与订阅共用 Planner/Retriever/Analyst**：对话即"一次性主题"，订阅即"持久化主题"，核心管道同一套，降低维护成本
- **多 Agent 的价值在分工而非表演**：每个角色职责单一、prompt 独立、可单独评测与替换模型档位
- **结构化输出**：所有 Agent 间传递的数据用 Pydantic 模型定义并校验，校验失败进入重试/降级

### 4.2 关键流程

**主题编译（Planner）**

输入："近一周的 Agent 新技术"
输出（结构化）：

```json
{
  "keywords": ["AI agent framework", "LLM agent", "agent orchestration"],
  "sources": ["arxiv", "hacker_news", "github"],
  "arxiv_categories": ["cs.AI", "cs.CL"],
  "github_queries": {"min_stars": 50, "created_after_days": 7},
  "window_days": 7,
  "relevance_criteria": "与 LLM Agent 构建相关的新框架、重要版本发布、有影响力的论文或讨论"
}
```

**订阅执行（定时）**

1. Scheduler 触发到期主题
2. Retriever 按计划并发抓取各源（httpx 异步），排除已见 URL 指纹（增量）
3. Analyst 打分与聚类；单源失败时跳过该源并在报告/Feed 中标注降级，不阻塞整体
4. Editor 为通过条目生成摘要与推荐理由
5. 条目入库；超阈值条目进入即时推送队列；累计条目等待周期报告

**对话研究（同步，SSE）**

1. 用户消息进入 Retriever 的工具循环（拆解 → 检索 → 按需 fetch_page → 评估是否充分）
2. 循环上限：单轮对话最多 N 次工具调用（暂定 10）与总时长上限（暂定 120s），超限则基于已有信息作答并声明局限
3. Editor 汇总生成带引用的回答，SSE 流式返回；引用以 `[1][2]` 标注，页面渲染为原文链接

## 5. 数据模型（PostgreSQL）

| 表 | 关键字段 | 说明 |
|---|---|---|
| users | id, email, password_hash, notify_email, quota_topic_max, created_at | 注册用户；配额默认每用户 5 个主题 |
| topics | id, user_id, name, description, plan JSONB, cadence ('daily'\|'weekly'), status, last_run_at, next_run_at, created_at | plan 为 Planner 编译产物 |
| items | id, topic_id, source, url, url_hash, title, raw_content, published_at, score, cluster_key, summary, reason, status, fetched_at | status: pending→scored→accepted/rejected；url_hash = topic_id + url 去重指纹 |
| reports | id, topic_id, period_start, period_end, content_md, item_count, created_at | 周期报告存档 |
| conversations | id, user_id, title, created_at | 对话会话 |
| messages | id, conversation_id, role, content, citations JSONB, tool_trace JSONB, created_at | citations 持久化引用，保证历史可回看 |
| push_log | id, user_id, item_id, report_id, channel, dedup_key, sent_at | 推送去重与审计 |

索引要点：`items(topic_id, status, score desc)`、`items(url_hash)` 唯一、`topics(next_run_at) where status='active'`。

## 6. API 设计（v1，前缀 `/api/v1`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /auth/register, /auth/login | 注册；登录返回 JWT |
| GET/POST | /topics | 主题列表 / 创建（创建时同步调用 Planner，秒级返回计划预览） |
| PATCH/DELETE | /topics/{id} | 编辑（plan 重新编译）/ 删除 |
| POST | /topics/{id}/run | 手动触发一次执行（受配额限制） |
| GET | /topics/{id}/items | Feed 分页；支持 `since`、`min_score` |
| GET | /topics/{id}/reports, /reports/{id} | 报告列表 / 详情（公开分享 token） |
| POST | /conversations | 创建会话 |
| POST | /conversations/{id}/messages | 发送消息，SSE 流式返回 |
| GET | /healthz, /readyz | 存活 / 就绪（DB 连通） |

认证：JWT（Authorization: Bearer）。限流：登录/注册接口按 IP 限流；主题执行按用户配额。

## 7. 推送策略

- **即时推送**：item.score ≥ 8（暂定）且未被同簇条目在 24h 内推送过 → 立即邮件
- **周期推送**：cadence 到期时聚合生成报告并邮件推送；周期内无有效条目则发送"本期无值得看的"轻量邮件（可关闭）
- **抑制规则**：dedup_key = cluster_key + 日期；同一 cluster 24h 内只推一次
- 邮件发送失败重试 3 次（指数退避），仍失败记入 push_log 并可查询

## 8. 技术选型

| 层 | 选择 | 理由 |
|---|---|---|
| 语言/框架 | Python 3.13 + FastAPI | 生态成熟，异步友好，类型标注配合 Pydantic |
| 数据库 | PostgreSQL 16 + SQLAlchemy 2.0 (async) + Alembic | JSONB 存检索计划，迁移可控 |
| 调度 | APScheduler | 单实例够用；避免初期引入 Celery+Redis 的运维成本，规模到了再拆 |
| HTTP 客户端 | httpx (async) | 并发抓取、连接池 |
| Agent 框架 | PydanticAI（轻框架） | 透明、结构化输出原生支持、可替换模型；避免 LangGraph 的黑盒感 |
| LLM | 分级：Analyst 用 DeepSeek/GLM 低价位模型；Editor/对话用中档模型；具体型号实现时定 | 成本分级可控，Provider 抽象便于替换 |
| 搜索 | Tavily 或 Brave Search API（付费层起步） | 对话研究需要通用 Web 检索；arXiv/HN/GitHub 用官方免费 API |
| 邮件 | SMTP（Resend 或邮箱服务商） | 简单可靠 |
| 认证 | JWT + passlib(bcrypt) | 标准做法 |
| 部署 | Docker Compose（app + postgres）+ Caddy（自动 HTTPS） | 单 VPS 全家桶，简单可复制 |
| CI/CD | GitHub Actions：lint + test → build image → SSH 部署 | 推送即上线 |
| 可观测 | structlog 结构化日志 + Sentry（免费层）+ /healthz | 生产基本盘 |

## 9. 测试策略

- **单元测试**：评分过滤逻辑、URL 指纹去重、抑制规则、配额计算（纯函数，覆盖边界）
- **契约测试**：各信息源客户端对录制的响应（respx/vcr）解析正确
- **Agent 评测**：固定"金标集"（10 个主题 + 期望检索计划要点），CI 中跑 Planner 输出比对；Retriever/Editor 以离线样例数据跑管道，断言产物结构
- **集成测试**：docker compose 起真实 Postgres，覆盖 注册→建主题→mock 源抓取→出条目 全链路
- LLM 调用在测试中一律 mock（不做真实调用，保证 CI 稳定与零成本）

## 10. 里程碑

**一期（MVP，目标 4-5 周业余时间）**

- M1：项目骨架、配置管理、DB 迁移、注册登录、健康检查（可部署空壳上线）
- M2：Planner + Retriever + Analyst + items 入库，手动触发跑通（核心管道）
- M3：Feed 页 API + APScheduler 定时执行 + 邮件推送（订阅闭环）
- M4：对话研究 Agent（工具循环 + SSE + 引用）
- M5：前端页面（订阅/Feed/对话三个界面）、限流配额、CI/CD、监控，正式上线

**二期**

- 周期报告生成与分享页
- 主动推送阈值与抑制策略完善、站内通知
- 跨会话用户记忆（关注历史影响打分与推荐）
- 自定义 RSS 源、更多信息源（Reddit、Twitter Lists 等）

## 11. 风险与对策

| 风险 | 对策 |
|---|---|
| LLM 成本失控 | 分级模型 + 打分前截断 raw_content + 每用户每日报表成本统计 + 配额硬限 |
| 信息源 API 变更/限流 | 客户端层隔离，单源降级不影响整体；对 HN/GitHub 遵守速率限制并本地缓存 |
| Planner 编译的计划质量不稳定 | 金标集评测 + 用户可在创建预览中手工修正关键词 |
| 单实例 Scheduler 与 Web 同进程互相影响 | 任务与 API 分 worker 进程部署（同镜像不同启动命令），资源隔离 |
| 邮件进垃圾箱 | 使用独立发信域名 + SPF/DKIM/DMARC，提供退订链接 |
| 版权风险 | 只存摘要与链接，摘要标注来源，提供原文跳转 |

## 12. 开放问题（实现前需确认）

1. LLM 具体供应商与型号（涉及 API Key 与预算，建议 Analyst 用 DeepSeek，Editor 视效果定）
2. Web 搜索 API 选型（Tavily vs Brave，看免费额度是否覆盖初期用量）
3. 前端形态：服务端渲染（Jinja2 + htmx，最快）vs 轻量 SPA（React/Vue，演示效果好）——影响 M5 工作量
