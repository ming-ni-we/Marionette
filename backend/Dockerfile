# 「提线」(Marionette) 后端镜像 —— 多阶段构建
#
# 构建上下文必须是**仓库根目录**（见 docker-compose.yml 注释）：
#   stage 1 构建 frontend/，stage 2 运行 Python 应用并托管静态产物。
#
# 前端由另一位工程师在 frontend/ 并行开发。若该目录暂不存在，
# 本 Dockerfile 会生成一个占位 index.html 保证镜像仍可构建，不会卡住后端交付。

# --------------------------------------------------------------------------
# stage 1: 构建前端 SPA
# --------------------------------------------------------------------------
FROM node:22-slim AS web

WORKDIR /src
COPY . .

RUN if [ -f frontend/package.json ]; then \
      cd frontend && \
      echo "[web] 丢弃异平台 package-lock.json：Windows 生成的 lock 不含 Linux 原生可选依赖，npm ci 会静默漏装 rollup/esbuild 的 linux 包"; \
      rm -f package-lock.json && \
      npm install --no-audit --no-fund --include=optional && \
      npm run build && \
      echo "[web] 前端构建完成"; \
    else \
      mkdir -p /src/frontend/dist && \
      printf '%s' '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>提线 (Marionette)</title></head><body style="font-family:system-ui,sans-serif;padding:3rem"><h1>提线 (Marionette)</h1><p>前端尚未构建。请确认 frontend/ 已存在并执行 npm run build。</p></body></html>' \
        > /src/frontend/dist/index.html && \
      echo "[web] 未找到 frontend/package.json，已生成占位 index.html"; \
    fi

# --------------------------------------------------------------------------
# stage 2: 运行时
# --------------------------------------------------------------------------
FROM python:3.12-slim AS api

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# curl 供容器 healthcheck 使用
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖再拷业务代码无意义（本项目用 pyproject 一并安装），直接整体拷贝
COPY backend/ /app/

RUN pip install --upgrade pip && pip install .

# 前端构建产物 → /app/static（api 容器同时托管 SPA）
COPY --from=web /src/frontend/dist /app/static

RUN mkdir -p /app/data/assets /app/data/config && chmod +x /app/entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=12 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
