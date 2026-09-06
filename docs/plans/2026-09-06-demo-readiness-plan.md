# TradeWinds 演示就绪实施计划书

> **For agentic workers:** 按任务顺序执行,每 Task 走 TDD 固定循环(写失败测试 → 最小实现 → 通过 → lint/mypy 零错误 → Commit)。

**Goal:** 项目定位调整为面试可演示的作品集项目(见 [design.md](../design.md) v0.3 第 1 节)后,补全"演示就绪"缺口:演示数据一键 seed、本地邮件可视化、周期报告邮件推送接线、`make demo` 一键全栈。

**Spec:** [docs/design.md](../design.md) v0.3 §10 里程碑 M6a/M6b/M6c;本文档锁定接口契约与验收标准。

**背景**:MVP 与扩展迭代已交付;此前所有"待上线"项(域名 HTTPS、Sentry 演练、真实发信、上线验收清单)随定位调整移除或转为本计划的演示等价物。

---

## Task A 周期报告邮件推送接线(补全既有设计承诺)

**范围:** `models/push_log.py`(PushType 增 `report`,native_enum=False 无需迁移)、`push/templates.py`(`render_report_email`,HTML/纯文本双版本,含退订链接)、`services/push_service.py`(`prepare_report` + `deliver` 支持 report 类型)、`services/pipeline_service.py`(报告 upsert 后推送)。

**Interfaces:**

- `PushService.prepare_report(report: Report) -> PushLog | None`——digest_key=`report:<report_id>`,push_type=report;同报告重复 run 幂等跳过(复用 topic_id+digest_key 唯一约束)
- `deliver()`:push_type=report 时由 digest_key 解析 report_id 渲染报告邮件
- 管道:`upsert_period_report` 返回非 None → `prepare_report`(同一周期首次创建即推,后续重算被去重键挡住)

**验收要点:** 报告邮件模板含主题名、统计区间、退订链接;集成测试:run → push_log 落 report 类型 → 重复 run 不重推;推送入 push 队列复用既有重试语义。

## Task B Mailpit 演示邮箱接入

**范围:** `docker-compose.yml` 增 mailpit 服务(Web UI 8025 / SMTP 1025);api/worker 容器 environment 注入演示 SMTP(覆盖 .env 空值:SMTP_HOST=mailpit、START_TLS=false、EMAIL_ENABLED=true、APP_BASE_URL=http://localhost、STATIC_DIR=/app/static);`.env.example` 注释说明演示默认值由 compose 注入。

**验收要点:** `make up` 后 Mailpit Web UI 可查看汇总/即时/报告邮件;不配任何真实发信服务。

## Task C 演示数据 seed

**范围:** `src/tradewinds/demo_seed.py`(`python -m tradewinds.demo_seed` 运行;纯本地数据,零网络零 LLM),Makefile 增 `make seed`(compose exec)。

**数据:** 演示账号 `demo@tradewinds.local` / `demo12345`;两个主题(Agent 新技术 daily、RAG 与检索增强 weekly,plan 为真实结构的检索计划,next_run_at 设远期避免无 LLM key 时 beat 空转报错);跨 arxiv/hn/github 的 accepted 条目(评分/摘要/推荐理由/聚类键)+ rejected 条目;当期周报 + share_token;含引用与工具轨迹的对话;item_clicks 点击历史;push_log 历史记录。url_hash 用 item_service 同一指纹函数保持一致。

**验收要点:** 幂等——重复执行不产生重复数据(以演示账号存在为整体开关);集成测试:seed 两次断言行数不变、条目 url_hash 唯一约束不冲突。

## Task D 一键演示入口(make demo + SPA 静态托管)

**范围:** Dockerfile 增前端构建阶段(node:22 build → dist 拷入运行镜像 /app/static,`.dockerignore` 相应调整:排除 `frontend/node_modules` 而非整个 frontend);`core/config.py` 增 `static_dir: str = ""`(空=不托管,本地开发与测试不受影响);`api/app.py` 在全部 API 路由之后挂载 SPA 静态资源(`/assets` StaticFiles + 兜底 GET 返回 index.html,`api/` 前缀路径除外);Makefile 增 `demo` 目标(up → exec alembic → seed → 打印演示入口)。

**验收要点:** `make demo` 一条命令起全栈并完成迁移与 seed;浏览器访问 http://localhost 直达前端(刷新任意前端路由不 404);`static_dir` 为空时行为与现状完全一致;SPA 兜底路由不劫持 /api 未知路径(仍 404)。

---

## 验收(演示走查清单,替代原上线验收清单)

- [x] 单元测试(190)、ruff、mypy 全绿;前端 `npm run build` 产出 dist,SPA 托管经真实 dist 冒烟验证(200/200/200/404)
- [ ] `make demo` 从零起全栈成功,打印演示入口——本机无 Docker,待有 Docker 环境或 CI 走查
- [ ] demo 账号登录 → 订阅/Feed/对话/报告/分享页全部有预置数据——同上(数据结构经集成测试幂等断言)
- [ ] Mailpit 收件箱可见推送邮件(需 .env 配 LLM key 后手动触发一次 run)
- [x] `make test-all`(含集成测试)、`make lint`、`make type` 全绿——集成测试本机跳过,待 CI 确认
- [x] study 文档:16-SPA静态托管与FastAPI兜底路由.md

## 实施记录(2026-09-06 交付)

- Task A:PushType 增 `report`(native_enum=False,无迁移);`render_report_email`;`PushService.prepare_report` / `deliver` report 分支 / `report_digest_key`;管道报告 upsert 后 `prepare_report`。测试:模板单测 2 例 + 集成"run 推送报告邮件一次、重复 run 不重推"。
- Task B:compose 增 mailpit 服务(`axllent/mailpit:v1.31.1`,Web UI 8025);api/worker 注入演示 SMTP 与 `APP_BASE_URL=http://localhost`;`.env.example` 注明 compose 覆盖关系。发现遗留死配置 `TRADEWINDS_EMAIL_ENABLED` 定义后从未被消费(邮件开关实为 SMTP host/sender 空值判断),未顺手删除,待后续清理。
- Task C:`tradewinds/demo_seed.py` + `make seed`;集成测试断言重复 seed 幂等、报告/推送/条目数据量稳定。主题 `next_run_at` 设远期,避免无 LLM key 时 beat 空转产生失败任务。
- Task D:`mount_spa` + `TRADEWINDS_STATIC_DIR`(默认空,行为不变);Dockerfile 增 `node:22-alpine` 前端构建阶段(产物入镜像 `/app/static`);`.dockerignore` 改为排除 `frontend/node_modules` 与 `frontend/dist`;Makefile 增 `demo`(up → exec alembic → exec seed → 打印入口)。SPA 挂载在 lifespan 中完成,`create_app()` 保持零配置依赖(单测无环境变量可用)。

## 边界(明确不做)

- web_search 通用搜索(暂缓理由不变,接入点已预留)
- Sentry 告警演练、Lighthouse、备份恢复演练(运营项,随 N6 移除)
- 真实发信服务、域名、公网 HTTPS
