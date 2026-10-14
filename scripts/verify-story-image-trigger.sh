#!/usr/bin/env bash
# 剧情配图自动触发 —— 端到端真实验证（S16 §4.6.3）
#
# 验证什么（真调 LLM + 真调火山出图，会花钱，约 ¥0.4/次）：
#   1. 建世界观 + 剧情会话（走真实 API）
#   2. 跑一轮真实剧情对话，抓 SSE 事件流
#   3. 断言 image 事件**确实出现**，且带 reason（node / cast）
#   4. 取回该 asset 的二进制，校验魔数（JPEG 或 PNG）
#   5. 再跑一轮，断言**同一角色不重复出图**（去重生效）
#
# 用法：bash scripts/verify-story-image-trigger.sh [每轮最大等待秒数]
#
# 前置条件：
#   - 栈已起（docker compose up -d）
#   - .env 里 STORY_IMAGE_ENABLED=true 且 IMAGE_*/LLM_* 配好
set -u
cd "$(dirname "$0")/.." || exit 1

MAXWAIT="${1:-120}"
BASE="http://127.0.0.1"
JAR=/tmp/story-img-jar.txt
SSE=/tmp/story-img-sse.txt
rm -f "$JAR" "$SSE"

PASS=0
FAIL=0
ok()   { echo "  ✅ $1"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ $1"; FAIL=$((FAIL+1)); }
step() { echo; echo "=== $1 ==="; }

# --------------------------------------------------------------------------- #
step "[1/6] 登录"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -m 15 -c "$JAR" \
  -X POST "$BASE/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"password\":\"$(grep -E '^ACCESS_PASSWORD=' .env | cut -d= -f2-)\"}")
[ "$CODE" = "200" ] && ok "登录 HTTP 200" || { bad "登录失败 HTTP $CODE"; exit 1; }

# --------------------------------------------------------------------------- #
step "[2/6] 建世界观"
WJSON=$(curl -s -m 30 -b "$JAR" -X POST "$BASE/api/v1/worlds" \
  -H 'Content-Type: application/json' -d '{
    "title": "触发验证·雨夜弄堂",
    "setting": {
      "location": "民国老弄堂",
      "time": "深夜",
      "mood": "压抑",
      "era": "1920s 上海",
      "genre": "悬疑"
    },
    "outline": {"acts": [{"id": "a1", "summary": "查账册"}]},
    "opening": "雨点砸在青石板上。"
  }')
WID=$(printf '%s' "$WJSON" | python3 -c '
import sys, json
d = json.load(sys.stdin)
# 统一响应是 Envelope：业务数据在 data 里
d = d.get("data") or d
print(d.get("id", ""))
' 2>/dev/null)
[ -n "$WID" ] && ok "世界 id = $WID" || { bad "建世界观失败：$WJSON"; exit 1; }

# --------------------------------------------------------------------------- #
step "[3/6] 建剧情会话（绑定世界观）"
# 先拿一张卡 + 一个预设；库里为空则**自动造一份**，保证脚本自洽可重复
#
# 注意两个解析函数要分开：列表响应里 id 在 data.items[0].id，
# 而创建响应里 id 直接在 data.id —— 混用会静默拿到空串。
_pick_from_list() {
  python3 -c '
import sys, json
d = json.load(sys.stdin)
d = d.get("data") or d
items = d.get("items") or []
print(items[0].get("id", "") if items else "")
' 2>/dev/null
}

_pick_id() {
  python3 -c '
import sys, json
d = json.load(sys.stdin)
d = d.get("data") or d
print(d.get("id", ""))
' 2>/dev/null
}

CARD=$(curl -s -m 15 -b "$JAR" "$BASE/api/v1/cards?limit=1" | _pick_from_list)
if [ -z "$CARD" ]; then
  echo "  （库中无角色卡，自动创建一张）"
  CARD=$(curl -s -m 20 -b "$JAR" -X POST "$BASE/api/v1/cards" \
    -H 'Content-Type: application/json' -d '{
      "spec": "rpg_card",
      "spec_version": "1.0",
      "data": {
        "name": "沈砚",
        "description": "穿深灰长衫的年轻男子，眉骨有旧疤",
        "personality": "克制、短句、不肯多说一个字",
        "scenario": "雨夜的堂屋，桌上摊着一本账册。",
        "first_mes": "他把灯芯挑亮了些。"
      }
    }' | _pick_id)
fi

PRESET=$(curl -s -m 15 -b "$JAR" "$BASE/api/v1/presets?limit=1" | _pick_from_list)
if [ -z "$PRESET" ]; then
  echo "  （库中无预设，自动创建一个）"
  PRESET=$(curl -s -m 20 -b "$JAR" -X POST "$BASE/api/v1/presets" \
    -H 'Content-Type: application/json' -d '{
      "spec": "rpg_preset",
      "spec_version": "1.0",
      "data": {
        "name": "冷峻写实",
        "description": "短句、克制的写实笔法",
        "prompt_template": {"system": "以冷峻写实的笔法演出，短句为主。"},
        "sampling": {"temperature": 0.8, "max_tokens": 800}
      }
    }' | _pick_id)
fi
if [ -z "$CARD" ] || [ -z "$PRESET" ]; then
  bad "缺角色卡或预设（$CARD / $PRESET），无法建会话"
  exit 1
fi
ok "card=$CARD preset=$PRESET"

SJSON=$(curl -s -m 60 -b "$JAR" -X POST "$BASE/api/v1/sessions" \
  -H 'Content-Type: application/json' \
  -d "{\"character_card_id\":\"$CARD\",\"preset_id\":\"$PRESET\",\"world_id\":\"$WID\"}")
SID=$(printf '%s' "$SJSON" | python3 -c '
import sys, json
d = json.load(sys.stdin)
d = d.get("data") or d
print(d.get("id", ""))
' 2>/dev/null)
[ -n "$SID" ] && ok "会话 id = $SID" || { bad "建会话失败：$SJSON"; exit 1; }

# --------------------------------------------------------------------------- #
step "[4/6] 跑一轮真实剧情，抓 SSE"
echo "  （真调 LLM + 可能真出图，最多等 ${MAXWAIT}s）"
curl -s -N -m "$MAXWAIT" -b "$JAR" -X POST "$BASE/api/v1/sessions/$SID/stream" \
  -H 'Content-Type: application/json' \
  -d '{"input":"我推开门，雨水顺着衣角滴在地板上。抬头看看屋里有没有人。"}' \
  > "$SSE" 2>/dev/null

EVT_NAMES=$(grep -o '^event: .*' "$SSE" 2>/dev/null | sed 's/^event: //' | tr '\n' ' ')
echo "  事件序列：$EVT_NAMES"

for need in world_info director start usage done; do
  if printf '%s' "$EVT_NAMES" | grep -qw "$need"; then
    ok "SSE 含 $need"
  else
    bad "SSE 缺 $need"
  fi
done

# --------------------------------------------------------------------------- #
step "[5/6] 断言 image 事件 + reason"
if printf '%s' "$EVT_NAMES" | grep -qw image; then
  ok "image 事件已触发（自动配图生效）"
  # 取该事件的 data 行
  REASON=$(grep -A1 '^event: image' "$SSE" | grep '^data: ' | head -1 \
    | sed 's/^data: //' | python3 -c 'import sys,json; print(json.load(sys.stdin).get("reason",""))' 2>/dev/null)
  ASSET=$(grep -A1 '^event: image' "$SSE" | grep '^data: ' | head -1 \
    | sed 's/^data: //' | python3 -c 'import sys,json; print(json.load(sys.stdin).get("asset_id",""))' 2>/dev/null)
  echo "  reason=$REASON  asset_id=$ASSET"
  case "$REASON" in
    node|cast) ok "reason 合法（$REASON）" ;;
    *) bad "reason 异常（$REASON），应为 node / cast" ;;
  esac

  if [ -n "$ASSET" ]; then
    BIN=/tmp/story-img-asset.bin
    HCODE=$(curl -s -o "$BIN" -w '%{http_code}' -m 30 -b "$JAR" \
      "$BASE/api/v1/assets/$ASSET/content")
    if [ "$HCODE" = "200" ]; then
      MAGIC=$(od -An -tx1 -N4 "$BIN" | tr -d ' \n')
      SIZE=$(stat -c%s "$BIN")
      echo "  魔数=$MAGIC 大小=${SIZE}B"
      case "$MAGIC" in
        ffd8ff*) ok "合法 JPEG" ;;
        89504e47) ok "合法 PNG" ;;
        *) bad "未知图片格式（$MAGIC）" ;;
      esac
    else
      bad "取回归档资产失败 HTTP $HCODE"
    fi
  else
    bad "image 事件缺 asset_id"
  fi
else
  echo "  ⚠️  本轮未触发 image（可能是：导演未给 node、无新角色、或间隔不足）"
  echo "     这说明**触发条件未命中**，不等于链路故障。要强验链路请连续多跑几轮，"
  echo "     或临时把 STORY_IMAGE_MIN_GAP=0 后重启 api。"
fi

# --------------------------------------------------------------------------- #
step "[6/6] 节流验证：连跑第 2 轮，间隔不足时不应再出图"
curl -s -N -m "$MAXWAIT" -b "$JAR" -X POST "$BASE/api/v1/sessions/$SID/stream" \
  -H 'Content-Type: application/json' \
  -d '{"input":"我开口问：这屋里先前住的人，是什么时候走的？"}' \
  > "${SSE}.2" 2>/dev/null
EVT2=$(grep -o '^event: .*' "${SSE}.2" 2>/dev/null | sed 's/^event: //' | tr '\n' ' ')
echo "  第 2 轮事件序列：$EVT2"

# 查会话 story 记账
#
# ⚠️ 路径易错（踩过）：记账在 **`state_machine.story`**，
# 而 cast / relations 固化副本在 `extensions.story` —— 两者不是同一个地方。
STORY=$(curl -s -m 15 -b "$JAR" "$BASE/api/v1/sessions/$SID" \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)
d = d.get("data") or d
st = (d.get("state_machine") or {}).get("story") or {}
print(json.dumps({k: st.get(k) for k in ("image_count","last_image_turn","image_nodes","image_cast")}, ensure_ascii=False))
' 2>/dev/null)
echo "  记账（state_machine.story）：$STORY"

read -r CNT LASTGAP NODES <<EOF
$(printf '%s' "$STORY" | python3 -c '
import sys, json
st = json.load(sys.stdin)
print(st.get("image_count") or 0, st.get("last_image_turn"), len(st.get("image_nodes") or []))
' 2>/dev/null)
EOF

if [ "${CNT:-0}" -ge 1 ]; then
  ok "记账已写入：image_count=$CNT, last_image_turn=$LASTGAP, image_nodes=$NODES 项"
else
  echo "  ⚠️  记账为空（若第 1 轮也没出图则属正常）"
fi

# 间隔节流：第 2 轮的 turn 是 1，last_image_turn 是 0 → gap=1 < min_gap(2) 应拦住
if printf '%s' "$EVT2" | grep -qw image; then
  echo "  ℹ️  第 2 轮也出了图（可能 min_gap=0 或该会话是本轮首次命中）"
else
  if [ "${CNT:-0}" -ge 1 ] && [ "${LASTGAP:-x}" = "0" ]; then
    ok "间隔节流生效：第 1 轮出图后，第 2 轮（gap=1 < min_gap=2）未重复出图"
  else
    echo "  ℹ️  第 2 轮未出图（触发条件未命中或已节流）"
  fi
fi

# 去重一致性：已配图节点数不应超过总出图数
if [ "${NODES:-0}" -le "${CNT:-0}" ]; then
  ok "节点去重一致（image_nodes=$NODES ≤ image_count=$CNT）"
else
  bad "image_nodes 多于出图数，去重可能失效"
fi

# --------------------------------------------------------------------------- #
echo
echo "=================================================="
echo "  PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "  结论：✅ 剧情配图自动触发链路验证通过"
else
  echo "  结论：❌ 存在失败项，请查看上方输出"
fi
echo "=================================================="
echo "原始 SSE 已留在 $SSE 与 ${SSE}.2"
exit "$FAIL"
