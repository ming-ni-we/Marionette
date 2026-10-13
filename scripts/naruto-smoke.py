#!/usr/bin/env python3
"""火影剧情线上冒烟：开演 + 一轮对话，检查导演是否零降级、多角色轮转。

用法：python3 /workspace/naruto-smoke.py
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
import http.cookiejar

BASE = "http://101.33.117.223"
PASSWORD = "DgX1yLVky0MOmDPpRGlh"
WORLD_ID = "1b206300-d638-4af5-b08a-70911bea8535"
PRESET_ID = "b4e3e383-aac1-4fed-93d7-85771e132ca6"

cj = http.cookiejar.LWPCookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with opener.open(req, timeout=120) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:300]}
    except Exception as e:
        return 0, {"error": str(e)}


def stream(path, body, label):
    """消费 SSE，返回事件列表。"""
    data = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    events = []
    try:
        with opener.open(req, timeout=300) as r:
            buf = ""
            for chunk in r:
                buf += chunk.decode("utf-8", "replace")
                while "\n\n" in buf:
                    block, buf = buf.split("\n\n", 1)
                    ev, dat = None, ""
                    for line in block.splitlines():
                        if line.startswith("event:"):
                            ev = line[6:].strip()
                        elif line.startswith("data:"):
                            dat += line[5:].strip()
                    if ev:
                        try:
                            events.append((ev, json.loads(dat) if dat else {}))
                        except Exception:
                            events.append((ev, {"raw": dat[:200]}))
    except urllib.error.HTTPError as e:
        print(f"  [{label}] HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}")
    return events


def main():
    st, resp = call("POST", "/api/v1/auth/login", {"password": PASSWORD})
    print(f"[login] {st}")
    if st != 200:
        print("登录失败", resp)
        return 1

    # ---- 建会话（带世界 = 剧情会话）----
    # 需要一张 lead 卡：用卡卡西的卡 id（从脚本产物读）
    ids = json.loads(open("/tmp/naruto-ids.json", encoding="utf-8").read())
    lead = ids.get("lead_card_id") or ids["cards"]["旗木卡卡西"]
    st, resp = call("POST", "/api/v1/sessions", {
        "character_card_id": lead,
        "preset_id": PRESET_ID,
        "world_id": WORLD_ID,
    })
    print(f"[create session] {st} {json.dumps(resp, ensure_ascii=False)[:200]}")
    if st not in (200, 201):
        return 1
    sid = resp["data"]["id"]

    # ---- 开演 = 发一条空 input 的 stream ----
    evs = stream(f"/api/v1/sessions/{sid}/stream", {"input": ""}, "start")
    kinds = [e for e, _ in evs]
    print(f"[start] 事件: {kinds[:8]} … 共 {len(evs)}")
    err = [d for e, d in evs if e == "error"]
    if err:
        print(f"  ✗ 开演报错: {err[:2]}")
        return 1
    print("  ✓ 开演 201/SSE 正常")

    # ---- 一轮对话 ----
    evs = stream(f"/api/v1/sessions/{sid}/stream", {
        "input": "我蹲下来，把名册翻到最后一页。用指尖点了点被划掉的那三行，"
                 "问卡卡西老师：这三个名字，是谁划的？为什么不是标『未归』？",
    }, "turn1")
    d_ev = [d for e, d in evs if e == "director"]
    n_ev = [d for e, d in evs if e == "node"]
    a_ev = [d for e, d in evs if e == "actions"]
    print(f"[turn1] 事件数 {len(evs)}")
    if d_ev:
        d = d_ev[-1]
        print(f"  导演: degraded={d.get('degraded')} speakers={d.get('speakers')} "
              f"node_triggered={d.get('node_triggered')}")
        if d.get("reason"):
            print(f"  reason={d['reason'][:120]}")
    else:
        print("  ✗ 无 director 事件")
    if n_ev:
        print(f"  节点: {json.dumps(n_ev[-1], ensure_ascii=False)[:160]}")
    if a_ev:
        acts = a_ev[-1].get("actions") or a_ev[-1].get("items") or a_ev[-1]
        print(f"  建议: {json.dumps(acts, ensure_ascii=False)[:220]}")
    else:
        print("  ⚠ 无 actions 事件")

    ok = bool(d_ev) and not d_ev[-1].get("degraded") and bool(a_ev)
    print(f"\n=== 冒烟结论: {'✅ PASS' if ok else '❌ FAIL'} ===")
    print(f"session_id={sid}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
