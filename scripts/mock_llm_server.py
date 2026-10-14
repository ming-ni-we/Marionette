#!/usr/bin/env python3
"""极简 OpenAI 兼容 mock 服务 —— 供「不放外部模型也能端到端验证」使用。

为什么需要它：
  本项目的剧情链路依赖一个 OpenAI 兼容的 LLM（导演 / 角色演出 / 行动建议）。
  验证 S16 出图触发时，真正要验的是**我写的接线代码**，而不是「火山账号有没有
  开通文本模型」——后者是环境问题，不该阻塞代码验收。

  所以起一个本地 mock：流式返回固定剧情文本，非流式（导演/建议/提示词扩写）
  返回可解析的 JSON。这样：
    - 不花一分钱、不依赖外网
    - 可重复执行，结果确定
    - 真实走过 FastAPI → ChatSvc → SSE 全链路

用法：
  python3 scripts/mock_llm_server.py 8899 &
  export LLM_BASE_URL=http://<容器可达IP>:8899/v1
  export LLM_API_KEY=mock
  export LLM_MODEL=mock-story
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# --------------------------------------------------------------------------- #
# 固定应答素材
# --------------------------------------------------------------------------- #

# 导演决策：让第一个说话者出场，并**故意给一个节点触发** —— 这样自动出图
# 一定有信号可命中（node 优先级最高）。
DIRECTOR_JSON = {
    "speakers": [{"id": "su_wan", "name": "苏晚", "intent": "试探"}],
    "narration": "雨声压过了两人的呼吸。",
    "scene_patch": {
        "location": "老弄堂的堂屋",
        "time": "深夜",
        "mood": "压抑",
        "beat": "两人对质",
        "present": ["su_wan"],
    },
    "node_triggered": {
        "id": "n_ledger",
        "title": "账册现形",
        "brief": "苏晚把账册拍在桌上",
    },
}

# 行动建议（非流式）
ACTIONS_JSON = [
    {"id": "a1", "label": "翻开账册", "text": "我翻开账册，指着一行数字。"},
    {"id": "a2", "label": "沉默对峙", "text": "我不说话，只是看着她。"},
]

# 出图提示词扩写（非流式）—— 刻意写得像真的，便于人工核对
IMAGE_PROMPT_JSON = {
    "prompt": (
        "昏暗的堂屋，木桌上摊开一本泛黄账册，"
        "一个穿深灰长衫的年轻男子垂手站在桌边，"
        "油灯火苗被穿堂风压低，雨丝斜打在窗纸上，写实电影感，冷色调，胶片颗粒"
    ),
    "negative_prompt": "文字, 水印, 签名, 乱码字符, 畸变, 多余手指, 低分辨率",
    "aspect": "landscape",
}

STORY_CHUNKS = ["我", "把账册", "拍在桌上，", "纸页", "弹起", "又落下。"]


def _sse(obj: dict) -> bytes:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A002
        sys.stderr.write("[mock-llm] " + (fmt % args) + "\n")

    def _read_body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except Exception:  # noqa: BLE001
            return {}

    def _send_json(self, obj: object, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------------ #
    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/").endswith("/models"):
            self._send_json({"object": "list", "data": [{"id": "mock-story", "object": "model"}]})
            return
        self._send_json({"ok": True, "mock": True})

    def do_POST(self) -> None:  # noqa: N802
        body = self._read_body()
        messages = body.get("messages") or []
        # 用系统提示词的关键词区分「这是哪一类调用」
        blob = json.dumps(messages, ensure_ascii=False)
        stream = bool(body.get("stream"))

        # ⚠️ 分支顺序**不能随意调换**（踩过坑）：
        # `_DIRECTOR_SYSTEM` 的正文里也出现了「行动」「建议」等词（"决定本轮由哪些
        # 角色登场说话/行动"），若把行动建议分支放在导演之前，导演调用会被误判成
        # 行动建议 → 返回数组而非导演对象 → 导演解析失败降级 → node_triggered 恒为
        # null → 自动出图永远拿不到信号。**用最独特的字段名做判定**。

        # ---- 1) 提示词扩写（image_trigger 要求返回 prompt/negative_prompt/aspect）----
        if "negative_prompt" in blob and "aspect" in blob:
            self._send_chat(IMAGE_PROMPT_JSON, stream=False)
            return

        # ---- 2) 导演决策（最独特：node_triggered / relation_updates）----
        if "node_triggered" in blob or "relation_updates" in blob:
            self._send_chat(DIRECTOR_JSON, stream=False)
            return

        # ---- 3) 行动建议（要求 JSON 数组；用 actions 字段名判定）----
        if "actions" in blob:
            self._send_chat(ACTIONS_JSON, stream=False)
            return

        # ---- 4) 角色演出（流式）----
        if stream:
            self._send_stream(STORY_CHUNKS)
            return

        self._send_chat({"text": "".join(STORY_CHUNKS)}, stream=False)

    # ------------------------------------------------------------------ #
    def _send_chat(self, payload: object, *, stream: bool) -> None:
        content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        self._send_json(
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "model": "mock-story",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            }
        )

    def _send_stream(self, chunks: list[str]) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        for piece in chunks:
            self.wfile.write(
                _sse(
                    {
                        "id": "chatcmpl-mock",
                        "object": "chat.completion.chunk",
                        "model": "mock-story",
                        "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
                    }
                )
            )
            self.wfile.flush()
        self.wfile.write(
            _sse(
                {
                    "id": "chatcmpl-mock",
                    "object": "chat.completion.chunk",
                    "model": "mock-story",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                }
            )
        )
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)  # noqa: S104
    sys.stderr.write(f"[mock-llm] listening on 0.0.0.0:{port}\n")
    srv.serve_forever()


if __name__ == "__main__":
    main()
