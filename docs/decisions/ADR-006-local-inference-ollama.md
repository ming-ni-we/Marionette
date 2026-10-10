# ADR-006: 本地推理运行时采用 Ollama（宿主机原生），重 GPU 任务不放入容器

## Status
Accepted (2026-10-09)

## Background
用户环境：**Windows + RTX 5060 Ti 16GB（Blackwell / sm_120）**，已部署 ComfyUI、动手能力强。深度联网核实到真实兼容坑：
- RTX 50 系计算能力 **sm_120**，**驱动必须 ≥ 570**；CUDA 建议 **12.8+**。
- **稳定版 PyTorch 曾未编译 sm_120 内核**，出现 `No CUDA GPUs are available` / `capability sm_120 is not compatible` 警告；需 **cu128+** 轮子或 nightly，且 `pip install` 可能静默保留旧 cu124（需 `--force-reinstall --no-cache-dir`）。
- `CUDA_VISIBLE_DEVICES=""`（空串）会让 PyTorch 看不到 GPU 而 `nvidia-smi` 正常。
- 容器内 GPU 需 NVIDIA Container Toolkit（Windows 走 WSL2 + Docker Desktop）。

## Decision
1. **本地 LLM 用 Ollama 0.33.x**，**宿主机原生安装**（不默认入 compose）。理由：Windows 原生即用 GPU、自带模型管理、暴露 OpenAI 兼容 `/v1/chat/completions`（流式），适配层零成本；官方明确支持 RTX 50 系（compute 12.0）。备选 llama.cpp server（同源 GGUF，需精细层卸载时用）。
2. **重 GPU 任务（LLM、出图）全部在宿主机原生运行时**（Ollama + ComfyUI），**不在 api 容器内跑 GPU torch**，从而绕开容器内 sm_120 轮子问题。
3. **api 容器内 embedding 走 CPU / ONNX Runtime**（bge 系列 326M，CPU 单条百毫秒级足够），必要时启动自检降级。
4. **容器内 GPU 作为可选**：compose profile `local-llm` 提供容器版 Ollama；镜像基线 `nvidia/cuda:12.8-*-runtime` + cu128 轮子，启动做 `torch.cuda.is_available()` 自检，**失败即显式降级 CPU 并在 UI 提示，不静默**。
5. 模型档位（16GB 显存实测口径）：默认 8B 稠密 Q8_0（最稳、长上下文）或 14B 稠密 Q4_K_M（甜点但偏紧）；MoE（GPT-OSS-20B / Qwen3-30B-A3B）作"速度优先"档；**32B 稠密明确排除**。默认上下文 8K–16K（KV Cache 随上下文线性增长）。

## Consequences
- 正面：规避 sm_120 容器坑；利用用户已有 ComfyUI/GPU；本地推理一键可用。
- 负面：宿主原生运行时使"完全容器化的可移植性"打折（不同机器需各自装 Ollama/ComfyUI）；已通过 `LLMProvider`/`ImageProvider` 接口 + 云端 API 备选兜底。
- 约束：所有 LLM 调用走 OpenAI 兼容协议适配层；`gpu_available` 在 `/system/info` 暴露，UI 据实提示。

## Related ADRs
- ADR-003（后端）
- ADR-009（部署形态）
