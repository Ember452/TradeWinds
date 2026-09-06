# 运维 Runbook(阶段 0)

> 对应 [扩展计划](scaling-plan.md) 阶段 0 必做项:备份演练、三大核心指标告警、Sentry。
> 原则:由指标触发演进,本 runbook 只覆盖单实例阶段。
> 定位说明(2026-09-06):项目为面试演示项目,不真实上线;本文档作为运维设计的展示保留,其中"上线后执行"的步骤(恢复演练、告警值班)仅在真实部署时适用。

## 1. 数据库备份与恢复

```bash
# 手动备份(deploy/backup.sh 保留最近 14 份)
deploy/backup.sh

# 建议的 VPS crontab(每日 04:00 UTC,容器内时区无关):
# 0 4 * * * cd /opt/tradewinds && ./deploy/backup.sh >> backups/backup.log 2>&1
```

**异地存储**:备份目录用 rclone/restic 同步到对象存储,示例:

```bash
rclone copy backups/ remote:tradewinds-backups/ --max-age 48h
```

**恢复演练**(上线后一周内执行一次,之后每季度一次):

1. 在临时 compose 项目(或本地)起空 PostgreSQL;
2. `deploy/restore.sh backups/<最新文件>`,确认 psql 无报错;
3. `alembic current` 核对迁移版本与生产一致;
4. 抽查 `users`/`topics`/`items` 行数与业务抽查一条数据;
5. 在 runbook 记录演练日期与结果。

## 2. 三大核心指标与告警阈值

指标出口:`GET /api/v1/ops/summary`(需 `X-Ops-Token` 环境变量 `TRADEWINDS_OPS_TOKEN`)。监控脚本(机器上的 cron/uptime 工具)定时拉取并按阈值告警:

| 指标 | 字段 | 告警阈值(建议) | 动作 |
|---|---|---|---|
| 队列积压 | `queue_backlog.pipeline` | > 100 持续 15 分钟 | 检查 worker 是否存活/上游限流;必要时扩 worker 副本 |
| 队列积压 | `queue_backlog.push` | > 20 持续 15 分钟 | 检查 SMTP/推送任务失败日志 |
| LLM 成本 | `llm_usage_today` 各档位 total_tokens | 日 token 超预算(按成本折算,初始建议对齐 30 元/天) | 核对异常活跃主题,必要时下调配额 |
| 推送健康 | `push_today.failed` | failed > sent 且 failed ≥ 5 | 检查 SMTP 配置与 push_log.error |
| 业务活性 | `counts.items_accepted_24h` | 活跃主题 > 0 但连续 24h 为 0 | 检查 beat/worker/信息源降级日志 |
| 进程存活 | `/healthz` / `/readyz` | /readyz 连续 3 次非 200 | DB/Redis 连通性排查 |

Sentry(DSN 配置后自动启用)覆盖代码层错误上报;告警通道接 Sentry 邮件/IM webhook。

## 3. 常用命令

```bash
docker compose ps                       # 容器状态
docker compose logs -f worker           # 管道日志(pipeline_run / source_degraded / task_failed)
docker compose exec api alembic current # 数据库迁移版本
docker compose exec redis redis-cli llen pipeline   # 队列深度(与 summary 口径一致)
```

## 4. 已知边界(触发信号出现前不做)

- DB 独立实例 / 读写分离:DB CPU 持续 > 60% 才启动(扩展计划阶段 1)
- Prometheus + Grafana:日志指标仍够用时不上监控系统(阶段 1)
- api 多实例 / SSE 广播化:单实例扛不住峰值才启动(阶段 2)
