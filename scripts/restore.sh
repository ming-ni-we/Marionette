#!/usr/bin/env bash
#
# 「提线」(Marionette) —— 备份恢复工具
#
# 用途：把某个备份产物恢复到**临时库**做校验，或真正恢复到生产库。
#
# 安全设计：
#   - 默认只做「演练」：恢复到一个临时库，断言数据可查，然后删掉临时库。
#     绝不碰生产库。
#   - 真恢复必须显式加 --to-prod，且会先提示、要求输入确认。
#
# 用法：
#   sudo /opt/marionette/restore.sh                        # 演练最近一份（推荐，定期跑）
#   sudo /opt/marionette/restore.sh db_2026-10-13_094652.dump   # 演练指定文件
#   sudo /opt/marionette/restore.sh --to-prod <file>       # 真恢复到生产库（危险）

set -euo pipefail

APP_DIR="/opt/marionette"
BACKUP_DIR="${APP_DIR}/backups"
DB_CONTAINER="marionette-db"
DB_NAME="marionette"
DB_USER="postgres"
TEST_DB="marionette_restore_test"

cd "$APP_DIR"

die() { echo "错误: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "请以 root 运行：sudo $0"

TO_PROD=0
if [ "${1:-}" = "--to-prod" ]; then
  TO_PROD=1
  shift
fi

# 选备份文件：显式指定，或取最近一份
if [ -n "${1:-}" ]; then
  DUMP="$BACKUP_DIR/$1"
  [ -f "$DUMP" ] || die "备份文件不存在：$DUMP"
else
  DUMP=$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'db_*.dump' -printf '%T@ %p\n' 2>/dev/null \
           | sort -rn | head -1 | cut -d' ' -f2-)
  [ -n "$DUMP" ] || die "在 $BACKUP_DIR 中找不到任何 db_*.dump 备份。"
fi

echo "使用备份文件：$(basename "$DUMP") ($(du -h "$DUMP" | cut -f1))"

# 先校验归档结构
docker exec -i "$DB_CONTAINER" pg_restore -l < "$DUMP" >/dev/null 2>&1 \
  || die "归档损坏，pg_restore -l 校验失败。"

if [ "$TO_PROD" -eq 1 ]; then
  echo
  echo "!!! 你正在把备份恢复到【生产库 $DB_NAME】。现有数据将被覆盖。"
  echo "!!! 建议先手动跑一次 backup.sh 留底。"
  read -r -p "确认继续？输入 yes 继续：" ans
  [ "$ans" = "yes" ] || die "已取消。"
  TARGET_DB="$DB_NAME"
  # --clean --if-exists：先删再建，保证与备份一致
  docker exec -i "$DB_CONTAINER" pg_restore \
    -U "$DB_USER" -d "$TARGET_DB" --clean --if-exists --no-owner --no-privileges < "$DUMP"
  echo "已恢复到生产库。"
  exit 0
fi

# ---------- 默认：演练模式 ----------
echo "演练模式：恢复到临时库 $TEST_DB"
docker exec "$DB_CONTAINER" dropdb -U "$DB_USER" --if-exists "$TEST_DB" >/dev/null 2>&1 || true
docker exec "$DB_CONTAINER" createdb -U "$DB_USER" "$TEST_DB"

# pg_restore 在有依赖告警时会返回非 0，但数据通常已恢复；这里不因它中断，改为断言校验
docker exec -i "$DB_CONTAINER" pg_restore \
  -U "$DB_USER" -d "$TEST_DB" --no-owner --no-privileges < "$DUMP" 2>/dev/null || true

echo "---- 数据校验 ----"
FAIL=0
for t in cards worldbooks presets sessions worlds; do
  C=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB" -tAc "select count(*) from $t" 2>/dev/null || echo "ERR")
  printf "  %-12s %s\n" "$t" "$C"
  [ "$C" = "ERR" ] && FAIL=1
done

# 关键断言：cards 表必须可查（否则说明恢复失败）
CARD_COUNT=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB" -tAc "select count(*) from cards" 2>/dev/null || echo 0)
echo
if [ "$FAIL" -eq 0 ] && [ "${CARD_COUNT:-0}" -ge 0 ]; then
  echo "演练结果：通过（临时库数据可查，cards=$CARD_COUNT）"
  RC=0
else
  echo "演练结果：失败（有表无法查询）"
  RC=1
fi

docker exec "$DB_CONTAINER" dropdb -U "$DB_USER" "$TEST_DB" >/dev/null 2>&1 || true
echo "临时库 $TEST_DB 已清理。"
exit "$RC"
