#!/usr/bin/env bash
#
# M2.4 · 每日 pg_dump 全备 + 30 天保留 + 可选 S3 上传。
#
# Usage:
#   ./backend/scripts/backup.sh                            # 本地备份到 ./backups/
#   BACKUP_DIR=/data/backups ./backend/scripts/backup.sh   # 自定义目录
#   S3_BUCKET=my-bucket ./backend/scripts/backup.sh        # 同时推 S3（需 aws cli）
#
# Cron 示例（每日 03:00）:
#   0 3 * * * cd /opt/platform && ./backend/scripts/backup.sh >> /var/log/platform-backup.log 2>&1
#
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DB_NAME="${POSTGRES_DB:-eval_platform}"
DB_USER="${POSTGRES_USER:-eval}"
CONTAINER="${PG_CONTAINER:-platform-postgres-1}"

mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d-%H%M%S)
OUT="$BACKUP_DIR/eval_platform-${TS}.sql.gz"

echo "[backup] pg_dump $DB_NAME → $OUT"
docker exec -i "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" \
  --no-owner --no-acl --clean --if-exists \
  | gzip -9 > "$OUT"

SIZE=$(du -h "$OUT" | cut -f1)
echo "[backup] done size=$SIZE"

# 可选 S3 推送
if [[ -n "${S3_BUCKET:-}" ]]; then
  echo "[backup] uploading to s3://$S3_BUCKET/eval-platform/"
  aws s3 cp "$OUT" "s3://$S3_BUCKET/eval-platform/" --storage-class STANDARD_IA
fi

# 清理超过 RETENTION_DAYS 的旧备份
echo "[backup] pruning files older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name 'eval_platform-*.sql.gz' -mtime "+$RETENTION_DAYS" -print -delete || true

echo "[backup] ok"
