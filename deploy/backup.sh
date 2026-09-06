#!/usr/bin/env bash
# 每日数据库备份:pg_dump | gzip 落到 backups/(建议 VPS crontab 每日执行 + 异地同步)
# 用法: deploy/backup.sh [输出目录,默认 ./backups]
set -euo pipefail

OUT_DIR="${1:-backups}"
mkdir -p "$OUT_DIR"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
FILE="$OUT_DIR/tradewinds-$STAMP.sql.gz"

docker compose exec -T postgres pg_dump -U tradewinds --clean --if-exists tradewinds | gzip > "$FILE"

echo "已备份: $FILE"
# 保留最近 14 份,防止占满磁盘(异地归档见 docs/runbook.md)
ls -1t "$OUT_DIR"/tradewinds-*.sql.gz | tail -n +15 | xargs -r rm --
