#!/usr/bin/env bash
#
# 「提线」备份系统 —— 一键安装到服务器
#
# 在服务器上以 ubuntu 用户运行（需要 sudo 权限）：
#     sudo bash scripts/install-backup-cron.sh
#
# 幂等：重复运行只会更新脚本与 crontab，不会重复叠加条目。
#
# 它做的事：
#   1. 安装 backup.sh / restore.sh 到 /opt/marionette（700 root）
#   2. 安装 backup-env.example 配置模板
#   3. 写入 root crontab（每日 03:20 备份、每周日 04:40 恢复演练）
#   4. 准备日志文件
#   5. 立即跑一次备份做冒烟验证

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/marionette}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/marionette-backup.log"

log() { echo "[install] $*"; }
die() { echo "[install][错误] $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "请以 root 运行：sudo bash $0"
[ -d "$APP_DIR" ] || die "未找到 $APP_DIR"

# --------------------------------------------------------------------------- #
# 1. 安装脚本
# --------------------------------------------------------------------------- #
log "安装 backup.sh / restore.sh 到 $APP_DIR ..."
install -m 700 -o root -g root "$SRC_DIR/backup.sh"  "$APP_DIR/backup.sh"
install -m 700 -o root -g root "$SRC_DIR/restore.sh" "$APP_DIR/restore.sh"
install -m 600 -o root -g root "$SRC_DIR/backup-env.example" "$APP_DIR/backup-env.example"

# 脚本语法自检，装完就坏比不装更糟
bash -n "$APP_DIR/backup.sh"  || die "backup.sh 语法错误"
bash -n "$APP_DIR/restore.sh" || die "restore.sh 语法错误"

# --------------------------------------------------------------------------- #
# 2. crontab（幂等）
# --------------------------------------------------------------------------- #
log "写入 root crontab ..."
BACKUP_LINE="20 3 * * * /usr/bin/flock -n /tmp/marionette-backup.lock $APP_DIR/backup.sh >> $LOG_FILE 2>&1"
RESTORE_LINE="40 4 * * 0 /usr/bin/flock -n /tmp/marionette-restore.lock $APP_DIR/restore.sh >> $LOG_FILE 2>&1"

# 先删掉同功能的旧条目（含早期手工加的），再追加，避免重复。
#
# 注意：这里刻意**不用** `crontab -l | grep -v ... | grep -v ...` 的管道写法。
# 那种写法有两个坑：
#   1. grep -v 在「全部行都被过滤掉」或「crontab 为空」时返回非 0，
#      在 set -o pipefail 下会让管道整体失败，导致 crontab - 收到空输入 →
#      把已有 crontab 整个清空。
#   2. crontab -l 无 crontab 时本身返回非 0（"no crontab for X"）。
# 因此改为：先把现有内容读进变量（用 || true 兜住非 0），再用 bash 内部过滤。
EXISTING="$(crontab -l 2>/dev/null || true)"
KEPT="$(printf '%s\n' "$EXISTING" \
          | grep -v -e 'marionette/backup\.sh' -e 'marionette/restore\.sh' -e 'PROBE_BACKUP_FIRING' \
          || true)"

printf '%s\n%s\n%s\n' "$KEPT" "$BACKUP_LINE" "$RESTORE_LINE" \
  | sed '/^[[:space:]]*$/d' \
  | crontab -

# 写入后自检：两条任务必须在，否则回滚思路都来不及 —— 直接报错
if [ "$(crontab -l | grep -c 'marionette/backup\.sh')" -ne 1 ] \
   || [ "$(crontab -l | grep -c 'marionette/restore\.sh')" -ne 1 ]; then
  die "crontab 写入后自检失败，请检查：sudo crontab -l"
fi

# 保护性校验：安装前后「非本系统的既有条目」数量不应减少。
# 这条守卫是为了防止未来有人改动过滤逻辑时，误删别人（或云厂商）的定时任务。
PRESERVED_BEFORE="$(printf '%s\n' "$EXISTING" | grep -v -e 'marionette/backup\.sh' -e 'marionette/restore\.sh' -e 'PROBE_BACKUP_FIRING' | grep -c . || true)"
PRESERVED_AFTER="$(crontab -l | grep -v -e 'marionette/backup\.sh' -e 'marionette/restore\.sh' | grep -c . || true)"
if [ "${PRESERVED_AFTER:-0}" -lt "${PRESERVED_BEFORE:-0}" ]; then
  die "检测到既有 crontab 条目被误删（安装前 ${PRESERVED_BEFORE} 条 → 安装后 ${PRESERVED_AFTER} 条），请立即检查 sudo crontab -l"
fi
log "crontab 校验通过（保留既有条目 ${PRESERVED_AFTER} 条）。"

# --------------------------------------------------------------------------- #
# 3. 日志
# --------------------------------------------------------------------------- #
touch "$LOG_FILE"

# --------------------------------------------------------------------------- #
# 4. 冒烟：立刻备份一次
# --------------------------------------------------------------------------- #
log "冒烟验证：立刻执行一次备份 ..."
"$APP_DIR/backup.sh" || die "首次备份失败，请检查上方输出"

COUNT=$(find "$APP_DIR/backups" -maxdepth 1 -type f 2>/dev/null | wc -l)
[ "$COUNT" -gt 0 ] || die "备份目录为空，安装未成功"

log "完成。当前 $APP_DIR/backups 下有 $COUNT 个文件。"
log "当前 crontab："
crontab -l | sed 's/^/    /'
log "查看日志：sudo tail -20 $LOG_FILE"
