#!/usr/bin/env bash
#
# M2.4 · 从 backup.sh 产物恢复 + 完整性自检。
#
# Usage:
#   ./backend/scripts/restore.sh ./backups/eval_platform-20260526-030000.sql.gz
#
# 守门：
# - 先 dry-run（仅打印 SQL 行数），再确认实际恢复
# - 恢复前 dump 当前 DB 到 ./backups/pre-restore-<ts>.sql.gz 兜底
# - 恢复后自检：alembic_version / eval_run / eval_case_result 三张表行数 > 0
#
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <backup.sql.gz> [--yes]" >&2
  exit 2
fi
BACKUP_FILE="$1"
AUTO_YES="${2:-}"
DB_NAME="${POSTGRES_DB:-eval_platform}"
DB_USER="${POSTGRES_USER:-eval}"
CONTAINER="${PG_CONTAINER:-platform-postgres-1}"

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "[restore] file not found: $BACKUP_FILE" >&2
  exit 1
fi

LINES=$(gunzip -c "$BACKUP_FILE" | wc -l)
echo "[restore] backup file: $BACKUP_FILE ($LINES lines)"

if [[ "$AUTO_YES" != "--yes" ]]; then
  read -p "[restore] this will REPLACE database '$DB_NAME'. type 'yes' to proceed: " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    echo "[restore] aborted"
    exit 0
  fi
fi

# 兜底：恢复前先 snapshot 当前 DB
TS=$(date +%Y%m%d-%H%M%S)
PRE_DUMP="./backups/pre-restore-${TS}.sql.gz"
mkdir -p ./backups
echo "[restore] taking safety snapshot → $PRE_DUMP"
docker exec -i "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" \
  --no-owner --no-acl --clean --if-exists | gzip -9 > "$PRE_DUMP"

# 实际恢复
echo "[restore] restoring..."
gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1

# 自检
echo "[restore] self-check:"
for TBL in alembic_version eval_run eval_case_result; do
  CNT=$(docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT COUNT(*) FROM $TBL")
  echo "  $TBL: $CNT rows"
done

echo "[restore] ok (pre-restore snapshot kept at $PRE_DUMP)"
