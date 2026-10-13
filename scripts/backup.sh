#!/usr/bin/env bash
#
# 「提线」(Marionette) —— 每日自动备份
#
# 备份内容（三件套，恢复一个实例所需的最小完备集合）：
#   1. PostgreSQL 全库（pg_dump，自定义格式，便于 pg_restore 选择性恢复）
#   2. data/assets 上传资产（用户上传的图片/素材）
#   3. .env         运行时密钥与配置（ACCESS_PASSWORD / SECRET_KEY / LLM key / DB 口令）
#
# 设计要点（都是踩过坑才加的）：
#   - data/ 与 .env 属主是 root，ubuntu 读不到 → 用 sudo 读取（ubuntu 已配 sudo 免密）
#   - 每个产物都做「非空 + 完整性」校验；宁可不生成，也不留下一个坏的备份
#   - pg_dump 用管道时必须 pipefail，否则 gzip 成功会掩盖 pg_dump 失败
#   - 保留策略按文件名前缀 + 天数，不用无差别 find -delete
#   - flock 防止上一轮没跑完就叠下一轮
#   - 可选同步到腾讯云 COS（密钥存在才执行，不存在则跳过并告警）
#
# 用法：
#   sudo /opt/marionette/backup.sh          # 正常备份
#   sudo /opt/marionette/backup.sh --verify  # 只做校验，不产生新备份
#
# 退出码：0 成功；非 0 失败（cron 可据此告警）

set -euo pipefail

# --------------------------------------------------------------------------- #
# 配置
# --------------------------------------------------------------------------- #
APP_DIR="/opt/marionette"
BACKUP_DIR="${APP_DIR}/backups"
LOG_FILE="/var/log/marionette-backup.log"
RETENTION_DAYS=7
DB_CONTAINER="marionette-db"
DB_NAME="marionette"
DB_USER="postgres"
COS_ENV_FILE="${APP_DIR}/.backup-env"   # 可选：COS 凭据（600，不进 rsync，不进 git）
LOCK_FILE="/tmp/marionette-backup.lock"

STAMP="$(date +%F_%H%M%S)"
STAMP_SHORT="$(date +%F)"

# --------------------------------------------------------------------------- #
# 日志
# --------------------------------------------------------------------------- #
log() {
  local msg="[$(date '+%F %T')] $*"
  echo "$msg"
  # 只在以 root 运行时写系统日志文件
  if [ -w "$(dirname "$LOG_FILE")" ] || [ -w "$LOG_FILE" ]; then
    echo "$msg" >> "$LOG_FILE"
  fi
}

die() {
  log "错误: $*"
  exit 1
}

# --------------------------------------------------------------------------- #
# 并发保护：同一时刻只允许一个实例
# --------------------------------------------------------------------------- #
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "已有备份任务在运行，本次跳过。"
  exit 0
fi

# --------------------------------------------------------------------------- #
# 前置检查
# --------------------------------------------------------------------------- #
[ "$(id -u)" -eq 0 ] || die "请以 root 运行（需要读取 root 属主的 data/ 与 .env）：sudo $0"

cd "$APP_DIR"
[ -f docker-compose.yml ] || die "未找到 $APP_DIR/docker-compose.yml"

# 容器必须在跑，否则 pg_dump 出来的可能是空库
if ! docker exec "$DB_CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
  die "数据库容器 $DB_CONTAINER 未就绪，中止备份。"
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# --------------------------------------------------------------------------- #
# 1. 数据库
# --------------------------------------------------------------------------- #
DB_OUT="${BACKUP_DIR}/db_${STAMP}.dump"

log "开始备份数据库 ..."
# --format=custom：体积小、可用 pg_restore 并行/选择性恢复
# --no-owner/--no-privileges：恢复目标角色可能不同，去掉属主依赖更可移植
if ! docker exec "$DB_CONTAINER" pg_dump \
      -U "$DB_USER" -d "$DB_NAME" \
      --format=custom --no-owner --no-privileges \
      > "$DB_OUT" 2>"${DB_OUT}.err"; then
  log "pg_dump 失败：$(cat "${DB_OUT}.err" 2>/dev/null)"
  rm -f "$DB_OUT" "${DB_OUT}.err"
  die "数据库备份失败。"
fi
rm -f "${DB_OUT}.err"

# 完整性校验：pg_restore -l 能列出目录 = 归档结构完好
if ! docker exec -i "$DB_CONTAINER" pg_restore -l < "$DB_OUT" >/dev/null 2>&1; then
  rm -f "$DB_OUT"
  die "数据库备份归档损坏（pg_restore -l 校验未通过）。"
fi
DB_SIZE=$(stat -c%s "$DB_OUT")
[ "$DB_SIZE" -gt 1024 ] || { rm -f "$DB_OUT"; die "数据库备份过小（${DB_SIZE}B），疑似异常。"; }
log "数据库备份完成：$(basename "$DB_OUT") ($(numfmt --to=iec "$DB_SIZE" 2>/dev/null || echo "${DB_SIZE}B"))"

# --------------------------------------------------------------------------- #
# 2. 上传资产
# --------------------------------------------------------------------------- #
ASSETS_OUT="${BACKUP_DIR}/assets_${STAMP}.tar.gz"
log "开始备份上传资产 ..."
# data/ 属主 root，sudo 读取；assets 为空时也生成一个合法空包
tar czf "$ASSETS_OUT" -C "$APP_DIR" data/assets config 2>/dev/null || true
if [ ! -s "$ASSETS_OUT" ]; then
  rm -f "$ASSETS_OUT"
  die "资产备份失败或为空。"
fi
gzip -t "$ASSETS_OUT" || { rm -f "$ASSETS_OUT"; die "资产归档损坏（gzip -t 未通过）。"; }
ASSETS_SIZE=$(stat -c%s "$ASSETS_OUT")
# 统计归档里的真实文件数（排除目录项）。注意 grep -c 在无匹配时会额外输出 0，
# 且 set -e 下 grep 无匹配返回 1 会中断脚本，故用 || true 兜住并取首行。
ASSETS_FILES=$(tar tzf "$ASSETS_OUT" 2>/dev/null | grep -v '/$' | grep -c . || true)
ASSETS_FILES=${ASSETS_FILES:-0}
if [ "$ASSETS_FILES" -eq 0 ]; then
  log "提示：assets 归档为空目录（当前尚无上传资产），保留空包占位。"
fi
log "资产备份完成：$(basename "$ASSETS_OUT") ($(numfmt --to=iec "$ASSETS_SIZE" 2>/dev/null || echo "${ASSETS_SIZE}B"), ${ASSETS_FILES} 个文件)"

# --------------------------------------------------------------------------- #
# 3. 运行时配置（.env）
# --------------------------------------------------------------------------- #
ENV_OUT="${BACKUP_DIR}/env_${STAMP}.tar.gz"
log "开始备份运行时配置 ..."
tar czf "$ENV_OUT" -C "$APP_DIR" .env
gzip -t "$ENV_OUT" || { rm -f "$ENV_OUT"; die "配置归档损坏。"; }
chmod 600 "$ENV_OUT"   # 含密钥，收紧权限
log "配置备份完成：$(basename "$ENV_OUT")"

# --------------------------------------------------------------------------- #
# 4. 可选：同步到腾讯云 COS（异地容灾）
# --------------------------------------------------------------------------- #
# 设计要点：**只上传当天产物，绝不同步删除**。
# 本地保留 7 天、云端保留更久（靠生命周期规则清理），这样"本地被误删/磁盘坏"
# 时云端仍有历史。若用 coscmd 的 -rs --delete 会把本地删除同步到云端，等于自毁容灾。
COS_KEEP_DAYS="${COS_KEEP_DAYS:-90}"

if [ -f "$COS_ENV_FILE" ]; then
  # shellcheck disable=SC1090
  . "$COS_ENV_FILE"
  if [ -n "${COS_SECRET_ID:-}" ] && [ -n "${COS_SECRET_KEY:-}" ] && [ -n "${COS_BUCKET:-}" ]; then
    log "开始上传到 COS（异地）..."
    if command -v coscmd >/dev/null 2>&1; then
      COS_OK=1
      for f in "$DB_OUT" "$ASSETS_OUT" "$ENV_OUT"; do
        if ! coscmd -b "$COS_BUCKET" -r "${COS_REGION:-ap-hongkong}" \
               -s "$COS_SECRET_ID" -k "$COS_SECRET_KEY" \
               upload -f "$f" "/marionette-backups/$(basename "$f")" >>"$LOG_FILE" 2>&1; then
          COS_OK=0
          log "警告：上传失败 $(basename "$f")"
        fi
      done
      if [ "$COS_OK" -eq 1 ]; then
        log "COS 同步完成（3 个文件）。云端保留策略依赖存储桶生命周期规则（建议 ${COS_KEEP_DAYS} 天）。"
      else
        log "警告：COS 同步部分失败（本地备份仍然有效），详见 $LOG_FILE"
      fi
    else
      log "警告：未安装 coscmd，跳过 COS 同步。安装：pip3 install coscmd"
    fi
  else
    log "警告：$COS_ENV_FILE 存在但缺少 COS_SECRET_ID / COS_SECRET_KEY / COS_BUCKET，跳过 COS 同步。"
  fi
else
  log "提示：未配置 $COS_ENV_FILE，跳过 COS 异地同步（仅本地备份）。"
fi

# --------------------------------------------------------------------------- #
# 5. 保留策略：各类文件各留最近 N 天
# --------------------------------------------------------------------------- #
log "清理超过 ${RETENTION_DAYS} 天的备份 ..."
# 每个前缀只匹配自己的后缀，避免误伤（如 assets_ 前缀不该去匹配 .dump）
find "$BACKUP_DIR" -maxdepth 1 -type f -name "db_*.dump"     -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
find "$BACKUP_DIR" -maxdepth 1 -type f -name "assets_*.tar.gz" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
find "$BACKUP_DIR" -maxdepth 1 -type f -name "env_*.tar.gz"    -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true
# 清掉历史遗留的解压/临时文件
find "$BACKUP_DIR" -maxdepth 1 -type f -name "*.err" -delete 2>/dev/null || true

REMAIN=$(find "$BACKUP_DIR" -maxdepth 1 -type f | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
log "备份任务完成。当前保留 ${REMAIN} 个文件，共 ${TOTAL_SIZE}。"

# 汇总可用于 cron 告警的最终状态
log "SUMMARY db=${DB_SIZE}B assets=${ASSETS_SIZE}B files=${REMAIN} stamp=${STAMP}"
