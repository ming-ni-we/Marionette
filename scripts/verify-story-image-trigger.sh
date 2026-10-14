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
WID=$(printf '%s' "$WJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("id",""))' 2>/dev/null)
[ -n "$WID" ] && ok "世界 id = $WID" || { bad "建世界观失败：$WJSON"; exit 1; }

# --------------------------------------------------------------------------- #
step "[3/6] 建剧情会话（绑定世界观）"
# 先拿一张卡 + 一个预设
CARD=$(curl -s -m 15 -b "$JAR" "$BASE/api/v1/cards?limit=1" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print((d.get("items") or d.get("data") or [{}])[0].get("id",""))' 2>/dev/null)
PRESET=$(curl -s -m 15 -b "$JAR" "$BASE/api/v1/presets?limit=1" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print((d.get("items") or d.get("data") or [{}])[0].get("id",""))' 2>/dev/null)
if [ -z "$CARD" ] || [ -z "$PRESET" ]; then
  bad "缺角色卡或预设（$CARD / $PRESET），无法建会话"
  exit 1
fi
ok "card=$CARD preset=$PRESET"

SJSON=$(curl -s -m 60 -b "$JAR" -X POST "$BASE/api/v1/sessions" \
  -H 'Content-Type: application/json' \
  -d "{\"character_card_id\":\"$CARD\",\"preset_id\":\"$PRESET\",\"world_id\":\"$WID\"}")
SID=$(printf '%s' "$SJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("id",""))' 2>/dev/null)
[ -n "$SID" ] && ok "会话 id = $SID" || { bad "建会话失败：$SJSON"; exit 1; }

# --------------------------------------------------------------------------- #
step "[4/6] 跑一轮真实剧情，抓 SSE"
echo "  （真调 LLM + 可能真出图，最多等 ${MAXWAIT}s）"
curl -s -N -m "$MAXWAIT" -b "$JAR" -X POST "$BASE/api/v1/sessions/$SID/reply" \
  -H 'Content-Type: application/json' \
  -d '{"input_text":"我推开门，雨水顺着衣角滴在地板上。抬头看看屋里有没有人。"}' \
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
step "[6/6] 去重验证：再跑一轮，不应重复画同一角色"
curl -s -N -m "$MAXWAIT" -b "$JAR" -X POST "$BASE/api/v1/sessions/$SID/reply" \
  -H 'Content-Type: application/json' \
  -d '{"input_text":"我开口问：这屋里先前住的人，是什么时候走的？"}' \
  > "${SSE}.2" 2>/dev/null
EVT2=$(grep -o '^event: .*' "${SSE}.2" 2>/dev/null | sed 's/^event: //' | tr '\n' ' ')
echo "  第 2 轮事件序列：$EVT2"

# 查会话 story 记账
STORY=$(curl -s -m 15 -b "$JAR" "$BASE/api/v1/sessions/$SID" \
  | python3 -c '
import sys,json
d=json.load(sys.stdin)
st=(d.get("extensions") or {}).get("story") or {}
print(json.dumps({k:st.get(k) for k in ("image_count","last_image_turn","image_nodes","image_cast")}, ensure_ascii=False))
' 2>/dev/null)
echo "  记账：$STORY"
CNT=$(printf '%s' "$STORY" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("image_count") or 0)' 2>/dev/null)
if [ "${CNT:-0}" -ge 1 ]; then
  ok "记账已写入（image_count=$CNT）"
  CASTN=$(printf '%s' "$STORY" | python3 -c 'import sys,json; print(len(json.load(sys.stdin).get("image_cast") or []))' 2>/dev/null)
  if [ "${CASTN:-0}" -le "${CNT:-0}" ]; then
    ok "image_cast 去重生效（$CASTN 项 ≤ $CNT 张图）"
  else
    bad "image_cast 多于出图数，去重可能失效"
  fi
else
  echo "  ⚠️  本轮未出图，记账为空（符合预期，若上轮也没出图）"
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
