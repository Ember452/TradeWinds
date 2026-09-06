#!/usr/bin/env bash
# 从备份恢复:演练时先在临时库验证(dry-run),确认后再指向正式库
# 用法: deploy/restore.sh backups/tradewinds-YYYYmmdd-HHMMSS.sql.gz
set -euo pipefail

FILE="${1:?用法: deploy/restore.sh <备份文件> }"
[ -f "$FILE" ] || { echo "文件不存在: $FILE"; exit 1; }

echo "即将把 $FILE 恢复到 docker compose 的 postgres(会清空并重建现有对象)。"
read -r -p "确认恢复?输入 yes 继续:" confirm
[ "$confirm" = "yes" ] || exit 1

gunzip -c "$FILE" | docker compose exec -T postgres psql -U tradewinds -d tradewinds

echo "恢复完成。建议执行: docker compose exec api alembic current(核对迁移版本)。"
