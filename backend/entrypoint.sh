#!/bin/sh
# 「提线」api 容器入口：先跑迁移，再起服务。失败给中文原因。
set -e

echo "[marionette] 执行数据库迁移（alembic upgrade head）..."

attempt=0
until alembic upgrade head; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "[marionette][错误] 数据库迁移连续失败 30 次，已放弃启动。" >&2
    echo "[marionette][排查] 1) docker compose ps 确认 db 为 healthy；" >&2
    echo "[marionette][排查] 2) 核对 .env 的 DB_PASSWORD 与 db 服务一致；" >&2
    echo "[marionette][排查] 3) docker compose logs db 查看数据库自身报错。" >&2
    exit 1
  fi
  echo "[marionette] 数据库尚未就绪，2 秒后重试（第 ${attempt} 次）..."
  sleep 2
done

echo "[marionette] 迁移完成，启动 API（uvicorn）..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --proxy-headers \
  --forwarded-allow-ips='*'
