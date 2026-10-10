# ADR-003: 后端采用 FastAPI (Python) + Uvicorn

## Status
Accepted (2026-10-09)

## Background
后端要承担：内容 CRUD、会话编排（世界书触发、记忆摘要、上下文组装）、LLM 流式调度、图像钩子、向量检索。这些能力（tokenizer、embedding、sentence-transformers、ComfyUI 客户端）**几乎全在 Python 生态**。
候选：FastAPI、NestJS 12、Hono/Express。

## Decision
选择 **FastAPI 0.141.1 + Uvicorn 0.48.0 + Python 3.12 + Pydantic 2.13.4**。理由：
1. AI/向量/分词生态原生在 Python，避免跨语言桥接进程。
2. 原生 async + `StreamingResponse` 直接支持 SSE 流式。
3. Pydantic 校验 + 自动生成 OpenAPI，与 spec-as-contract 工作流天然契合。
4. NestJS/Hono 工程化好，但需另起 Python 进程处理 embedding/分词/ComfyUI，单机场景净增复杂度。

## Consequences
- 正面：AI 能力零桥接、契约自动生成、异步 IO 流畅。
- 负面：CPU 密集型任务（大文本处理）需注意不阻塞事件循环（放线程池/后台任务）；需自建 DI 约定（用 FastAPI `Depends`）。
- 约束：业务层不得 import 具体 LLM SDK，只能依赖 `LLMProvider` 接口（见架构 §2 分层依赖方向）。

## Related ADRs
- ADR-006（本地推理运行时）
- ADR-007（流式传输）
