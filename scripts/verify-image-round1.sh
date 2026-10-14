#!/usr/bin/env bash
# 图像出图端到端验证（火山方舟 Seedream / 任意 OpenAI 兼容 images 接口）
#
# 验证链路（真实、不打折）：
#   1. 登录拿会话 Cookie
#   2. POST /api/v1/images/jobs  —— 同步出图（走 ImageHook -> CloudImageProvider）
#   3. 校验响应：status=done / archived=true / asset_id 非空
#   4. GET /api/v1/assets/{assetId} 内容 —— 确认真能取到图
#   5. 校验 PNG 魔数（8 字节）
#
# 用法：bash scripts/verify-image-round1.sh [prompt]
set -u
cd /workspace/marionette-git || exit 1
ROOT=$(pwd)

PROMPT="${1:-一只红色千纸鹤，白色桌面，柔和晨光，极简摄影}"
BASE="http://127.0.0.1"
JAR=/tmp/img-jar.txt
rm -f "$JAR"

PW=$(grep -E '^ACCESS_PASSWORD=' .env | cut -d= -f2-)
MODEL=$(grep -E '^IMAGE_MODEL=' .env | cut -d= -f2-)
BURL=$(grep -E '^IMAGE_BASE_URL=' .env | cut -d= -f2-)
echo "模型 = $MODEL"
echo "后端 = $BURL"
echo

echo "=== [1/5] 登录 ==="
CODE=$(curl -s -m 15 -c "$JAR" -X POST "$BASE/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"password\":\"$PW\"}" -o /tmp/login.json -w '%{http_code}')
echo "  HTTP $CODE"
if [ "$CODE" != "200" ]; then echo "  登录失败，响应："; cat /tmp/login.json; exit 1; fi
echo "  OK"

echo
echo "=== [2/5] 提交出图任务（同步执行） ==="
python3 - "$PROMPT" > /tmp/job-req.json <<'PY'
import json, sys
print(json.dumps({"prompt": sys.argv[1], "width": 1024, "height": 1024}, ensure_ascii=False))
PY
T0=$(date +%s)
CODE=$(curl -s -m 180 -b "$JAR" -X POST "$BASE/api/v1/images/jobs" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/job-req.json -o /tmp/job.json -w '%{http_code}')
T1=$(date +%s)
echo "  HTTP $CODE  (耗时 $((T1-T0))s)"
cat /tmp/job.json | python3 -m json.tool 2>/dev/null | head -30

if [ "$CODE" != "202" ] && [ "$CODE" != "200" ]; then
  echo "  >>> FAIL：出图请求未成功"; exit 1
fi

echo
echo "=== [3/5] 校验任务状态 ==="
python3 - <<'PY'
import json, sys
d = json.load(open('/tmp/job.json'))
data = d.get('data') or d
ok = True
def chk(name, cond, val):
    global ok
    print(f"  {'PASS' if cond else 'FAIL'}  {name} = {val}")
    if not cond: ok = False
chk('status',   data.get('status') == 'done',     data.get('status'))
chk('archived', data.get('archived') is True,     data.get('archived'))
chk('asset_id', bool(data.get('asset_id')),       data.get('asset_id'))
chk('error',    not data.get('error'),            data.get('error'))
open('/tmp/asset-id.txt','w').write(str(data.get('asset_id') or ''))
open('/tmp/job-id.txt','w').write(str(data.get('id') or ''))
sys.exit(0 if ok else 1)
PY
CHK=$?
[ $CHK -ne 0 ] && echo "  >>> FAIL：任务状态校验未通过" && exit 1

echo
echo "=== [4/5] 取回归档资产 ==="
AID=$(cat /tmp/asset-id.txt)
echo "  asset_id = $AID"
CODE=$(curl -s -m 30 -b "$JAR" -o /tmp/out.png -w '%{http_code}' "$BASE/api/v1/assets/$AID/content")
SIZE=$(stat -c%s /tmp/out.png 2>/dev/null || echo 0)
echo "  HTTP $CODE  文件大小 = $SIZE bytes"
if [ "$CODE" != "200" ] || [ "$SIZE" -lt 1000 ]; then
  echo "  >>> FAIL：资产取回失败"; exit 1
fi

echo
echo "=== [5/5] 校验图片魔数（JPEG 或 PNG 均合法） ==="
python3 - <<'PY'
data = open('/tmp/out.png','rb').read(12)
print('  前 12 字节 =', data.hex())
if data.startswith(b'\xff\xd8\xff'):
    print('  PASS：合法 JPEG（火山 Seedream 返回 JPEG，属预期）')
elif data.startswith(b'\x89PNG\r\n\x1a\n'):
    print('  PASS：合法 PNG')
else:
    print('  FAIL：既不是 JPEG 也不是 PNG（可能是错误页面）')
    raise SystemExit(1)
PY
[ $? -ne 0 ] && echo "  >>> FAIL" && exit 1

cp /tmp/out.png /workspace/marionette/docs/asset/evidence-image-e2e.png 2>/dev/null || true
echo
echo ">>> 全部 PASS：出图链路端到端可用（出图 → 服务端自动归档 → 取回）"
