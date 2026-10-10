#!/bin/sh
# 「提线」(Marionette) —— Round 2 创作侧：服务器端验收脚本
#
# 用法（在服务器 /opt/marionette 上以 ubuntu 身份运行）：
#     sh scripts/verify_round2.sh -v --tb=short
#
# 做法：
#   1) 复用**已部署的生产镜像** marionette-api:latest（依赖版本与线上完全一致）；
#   2) 把工作区的 backend/app + backend/tests 以只读方式挂进去，
#      保证跑的是「即将上线的这份代码」，而不是镜像里的旧拷贝；
#   3) 装 pytest / pytest-asyncio / pillow 后跑完整测试（含连真实 PostgreSQL 的集成测试）。
#
# 隔离保证：
#   - 集成测试自建临时 schema（mtest_*），结束 DROP SCHEMA ... CASCADE，不触碰生产 schema；
#   - 测试口令由 tests/conftest.py 强制注入，不继承部署环境的随机 ACCESS_PASSWORD。
#
# 顺序：先 ruff check（静态门禁），再 pytest。退出码即 pytest 退出码，便于 CI 判定。
set -e

cd /opt/marionette

# 复用 compose 的同一份 .env（只为了拿 DB 连接信息）
set -a
. ./.env
set +a

exec docker run --rm \
  --network marionette_marionette \
  -e "DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}" \
  -e "ASSETS_DIR=/tmp/mtest-assets" \
  -e "CONFIG_DIR=/tmp/mtest-config" \
  -e "STATIC_DIR=/app/static" \
  -e "PYTHONPATH=/app" \
  -e "MARIONETTE_INTEGRATION=1" \
  -v /opt/marionette/backend/app:/app/app:ro \
  -v /opt/marionette/backend/tests:/app/tests:ro \
  -v /opt/marionette/backend/pyproject.toml:/app/pyproject.toml:ro \
  --entrypoint sh \
  marionette-api:latest \
  -c "pip install -q pytest pytest-asyncio pillow ruff \
      && cd /app \
      && echo '########## ruff check ##########' && ruff check app tests \
      && echo '########## pytest ##########' && python -m pytest tests/ $*"
