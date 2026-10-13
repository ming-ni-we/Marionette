#!/usr/bin/env bash
# =============================================================================
# push-to-github.sh —— 把当前代码同步到 GitHub（一个功能阶段一次）
#
# 设计原则：**全绿才推**。任何一项校验失败都立即中止，且不产生提交。
#           宁可不推，也不把坏代码送上 GitHub。
#
# 用法：
#   ./scripts/push-to-github.sh "feat(story): S13 会话列表集成"
#   ./scripts/push-to-github.sh -m "fix: 修 xxx"        # 同上
#   ./scripts/push-to-github.sh --dry-run              # 只校验+试推，不真正推
#   ./scripts/push-to-github.sh --skip-verify          # 跳过校验（不推荐，仅应急）
#   ./scripts/push-to-github.sh --check-only           # 只跑校验，不同步不推
#
# 凭据（二选一，推荐前者）：
#   1) export GITHUB_TOKEN=ghp_xxx   （fine-grained 需 Contents: Read and write）
#   2) 本机已登录的 git credential helper
# =============================================================================

set -euo pipefail

# ---------- 配置 ----------
WORK_DIR="${WORK_DIR:-/workspace/marionette}"          # 工作目录（真实开发地）
# ⚠️ 变量名**不能**叫 GIT_DIR —— 那是 git 自己的保留环境变量，
#    一旦 export 出去，git 会把仓库根解析错，报 `fatal: not a git repository`。
#    实测踩过。这里用 REPO_DIR 规避。
REPO_DIR="${REPO_DIR:-${GIT_REPO_DIR:-/workspace/marionette-git}}"   # git 仓库
BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
REPO_SLUG="ming-ni-we/Marionette"

# ---------- 参数 ----------
DRY_RUN=0
SKIP_VERIFY=0
CHECK_ONLY=0
COMMIT_MSG=""

while [ $# -gt 0 ]; do
  case "$1" in
    -m|--message) COMMIT_MSG="${2:-}"; shift 2 ;;
    --dry-run)    DRY_RUN=1; shift ;;
    --skip-verify) SKIP_VERIFY=1; shift ;;
    --check-only) CHECK_ONLY=1; shift ;;
    -h|--help)    sed -n '3,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*)           echo "未知参数：$1" >&2; exit 2 ;;
    *)            [ -z "$COMMIT_MSG" ] && COMMIT_MSG="$1"; shift ;;
  esac
done

# ---------- 输出工具 ----------
C_R=$'\033[31m'; C_G=$'\033[32m'; C_Y=$'\033[33m'; C_B=$'\033[36m'; C_0=$'\033[0m'
log()  { printf '%s[%s]%s %s\n' "$C_B" "$(date '+%H:%M:%S')" "$C_0" "$*"; }
ok()   { printf '%s  ✓ %s%s\n' "$C_G" "$*" "$C_0"; }
warn() { printf '%s  ! %s%s\n' "$C_Y" "$*" "$C_0" >&2; }
die()  { printf '%s  ✗ %s%s\n' "$C_R" "$*" "$C_0" >&2; exit 1; }

FAILED=()
step_fail() { FAILED+=("$1"); printf '%s  ✗ %s%s\n' "$C_R" "$1" "$C_0" >&2; }

# ---------- 前置检查 ----------
log "前置检查"
[ -d "$WORK_DIR" ] || die "工作目录不存在：$WORK_DIR"
[ -d "$REPO_DIR/.git" ] || die "git 仓库不存在：$REPO_DIR（应含 .git）"
command -v git >/dev/null || die "缺少 git"
command -v rsync >/dev/null || die "缺少 rsync"
ok "目录与工具就绪"

# ---------- 第 1 步：工作目录 → git 仓库 ----------
if [ "$CHECK_ONLY" -eq 0 ]; then
  log "第 1 步／4 · 同步 $WORK_DIR → $REPO_DIR"
  # 以工作目录为准；排除版本控制、依赖、构建产物、敏感与运行时文件
  rsync -a --delete \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='.venv' \
    --exclude='dist' \
    --exclude='build' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    --exclude='.smoke-bundle.mjs' \
    --exclude='.env' \
    --exclude='.env.*' \
    --exclude='.backup-env' \
    --exclude='data/' \
    --exclude='backups/' \
    --exclude='*.log' \
    "$WORK_DIR/" "$REPO_DIR/"
  ok "工作目录已同步进 git 仓库"

  # 敏感文件防线（第二道；第一道是 rsync --exclude + .gitignore）
  # 直接看**将要被提交的文件清单**，而不是 status 文本 —— 更贴近真实风险。
  git -C "$REPO_DIR" add -A >/dev/null 2>&1 || true
  LEAK=$(git -C "$REPO_DIR" diff --cached --name-only 2>/dev/null \
         | grep -E '(^|/)\.env($|\.)|\.backup-env|(^|/)id_rsa|\.pem$' || true)
  if [ -n "$LEAK" ]; then
    git -C "$REPO_DIR" reset -q >/dev/null 2>&1 || true
    die "检测到敏感文件将被提交，已中止并撤销暂存：
$(printf '%s\n' "$LEAK" | sed 's/^/      /')
     请确认 .gitignore 是否失效，或该文件本不该出现在工作目录。"
  fi
  ok "敏感文件检查通过（无 .env / .backup-env / 私钥）"
fi

# ---------- 第 2 步：全量校验 ----------
# 注意：校验在**工作目录**跑，不在这里跑的 git 仓库跑。
# 原因：node_modules / .venv 被有意排除在 git 仓库之外，
#       在 git 仓库里跑前端校验会因缺依赖而假失败。
#       第 1 步已把工作目录同步进 git 仓库，两者内容一致，故校验结论等效。
VERIFY_DIR="$WORK_DIR"
if [ "$SKIP_VERIFY" -eq 1 ]; then
  warn "已跳过校验（--skip-verify）—— 请确认你清楚风险"
else
  log "第 2 步／4 · 全量校验（全绿才继续）｜在 $VERIFY_DIR"
  [ -d "$VERIFY_DIR" ] || die "校验目录不存在：$VERIFY_DIR"

  # 2.1 后端测试：必须在 backend/ 目录下跑
  if [ -x "$VERIFY_DIR/backend/.venv/bin/python" ]; then
    PY="$VERIFY_DIR/backend/.venv/bin/python"
  elif [ -x "/tmp/venv/bin/python" ]; then
    PY="/tmp/venv/bin/python"
  else
    PY="python3"
    warn "未找到项目 venv，回退用 python3（可能缺依赖）"
  fi

  OUT=$(cd "$VERIFY_DIR/backend" && "$PY" -m pytest -q 2>&1) || true
  if printf '%s' "$OUT" | grep -qE '[0-9]+ passed' \
     && ! printf '%s' "$OUT" | grep -qE '[0-9]+ (failed|error)'; then
    ok "pytest：$(printf '%s' "$OUT" | grep -oE '[0-9]+ passed[^i]*' | tail -1)"
  else
    step_fail "后端测试 pytest"
    printf '%s\n' "$OUT" | tail -5 >&2
  fi

  # 2.2 ruff
  if (cd "$VERIFY_DIR/backend" && "$PY" -m ruff check app/ tests/ >/dev/null 2>&1); then
    ok "ruff：All checks passed"
  else
    step_fail "ruff 检查"
  fi

  # 2.3 前端类型
  if (cd "$VERIFY_DIR/frontend" && npx tsc --noEmit >/dev/null 2>&1); then
    ok "tsc：0 错误"
  else
    step_fail "前端 tsc 类型检查"
  fi

  # 2.4 SSE 三处白名单同构
  if (cd "$VERIFY_DIR/frontend" && npm run verify:sse >/dev/null 2>&1); then
    ok "verify:sse：三处白名单同构"
  else
    step_fail "SSE 契约校验"
  fi

  # 2.5 冒烟
  if (cd "$VERIFY_DIR/frontend" && node scripts/smoke.mjs >/dev/null 2>&1); then
    ok "smoke：全 PASS"
  else
    step_fail "前端冒烟测试"
  fi

  if [ "${#FAILED[@]}" -gt 0 ]; then
    echo
    die "校验未通过：${FAILED[*]}
     —— 已中止，**未产生任何提交**。修好后重跑。"
  fi
  ok "五项校验全绿"
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  log "只校验模式，结束。"
  exit 0
fi

# ---------- 第 3 步：提交 ----------
log "第 3 步／4 · 提交"
cd "$REPO_DIR"

# 关掉可能存在的交互式编辑器
export GIT_EDITOR=true

if git diff --cached --quiet && git diff --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  warn "工作区无改动，无需提交。"
  DIRTY=0
else
  DIRTY=1
  if [ -z "$COMMIT_MSG" ]; then
    die "有改动但未提供提交信息。用法：$0 \"feat(xxx): 说明\""
  fi
  git add -A
  git commit -m "$COMMIT_MSG" >/dev/null
  ok "已提交：$(git log --oneline -1)"
fi

# ---------- 第 4 步：推送 ----------
log "第 4 步／4 · 推送到 $REMOTE/$BRANCH"

if [ -n "${GITHUB_TOKEN:-}" ]; then
  PUSH_URL="https://${GITHUB_TOKEN}@github.com/${REPO_SLUG}.git"
  ok "使用 GITHUB_TOKEN 推送"
else
  PUSH_URL="$REMOTE"
  warn "未设置 GITHUB_TOKEN，尝试用本机凭据助手"
fi

if [ "$DRY_RUN" -eq 1 ]; then
  log "试推（--dry-run，不会真正写入远端）"
  if git push --dry-run "$PUSH_URL" "$BRANCH"; then
    ok "试推通过 —— 具备写权限，去掉 --dry-run 即可真正推送"
  else
    die "试推失败：无写凭据或权限不足。请设置 GITHUB_TOKEN（需 Contents: Read and write）"
  fi
  exit 0
fi

if git push "$PUSH_URL" "$BRANCH"; then
  LOCAL_SHA=$(git rev-parse --short HEAD)
  ok "推送成功：$LOCAL_SHA → $REPO_SLUG/$BRANCH"
  echo
  log "远端确认中…"
  sleep 2
  REMOTE_SHA=$(git ls-remote "$PUSH_URL" "refs/heads/$BRANCH" | cut -f1 | cut -c1-7)
  if [ "$REMOTE_SHA" = "$LOCAL_SHA" ]; then
    ok "远端已确认与本地一致（$REMOTE_SHA）"
  else
    warn "远端 SHA=$REMOTE_SHA 与本地 $LOCAL_SHA 不一致，请复查"
  fi
  echo
  log "查看：https://github.com/${REPO_SLUG}/commits/${BRANCH}"
else
  die "推送失败。常见原因：Token 无 repo 写权限 / 已过期 / 分支保护规则"
fi
