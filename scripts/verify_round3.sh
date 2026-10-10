#!/usr/bin/env bash
# 第三轮验证：① 开 MARIONETTE_INTEGRATION=1 跑真实 PG 集成测试
#              ② 中文关键词检索（用百分号编码，绕开一切 shell/终端编码问题）
#              ③ 三态世界书探针
set -u
cd /opt/marionette || exit 1

PW=$(grep -E '^ACCESS_PASSWORD=' .env | cut -d= -f2-)
echo "=== [1/4] 容器状态 ==="
docker compose ps --format "table {{.Name}}\t{{.Status}}"

echo
echo "=== [2/4] 集成测试（真实 Postgres，MARIONETTE_INTEGRATION=1） ==="
docker compose exec -T -e MARIONETTE_INTEGRATION=1 -e ASSETS_DIR=/tmp/mtest-assets \
  api python -m pytest -q 2>&1 | tail -25

echo
echo "=== [3/4] 中文关键词检索（张晚 / 日常，百分号编码） ==="
LOGIN=$(curl -s -m 10 -c /tmp/j3 -X POST http://127.0.0.1/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"password\":\"$PW\"}" -o /dev/null -w "%{http_code}")
echo "login=$LOGIN"
# 日常 = %E6%97%A5%E5%B8%B8 ; 林晚 = %E6%9E%97%E6%99%9A
for ENC in %E6%97%A5%E5%B8%B8 %E6%9E%97%E6%99%9A %E4%BE%BF%E5%88%A9%E5%BA%97; do
  CODE=$(curl -s -m 10 -b /tmp/j3 -o /tmp/resp.json -w "%{http_code}" \
    "http://127.0.0.1/api/v1/cards?q=$ENC&limit=3")
  TOTAL=$(python3 -c "import json,sys;d=json.load(open('/tmp/resp.json'));print(d.get('data',{}).get('total','?'))" 2>/dev/null || echo "?")
  echo "q=$ENC -> http=$CODE total=$TOTAL"
done
echo "首条命中名称："
curl -s -m 10 -b /tmp/j3 "http://127.0.0.1/api/v1/cards?q=%E6%97%A5%E5%B8%B8&limit=3" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);[print('  -',i['data']['name']) for i in d['data']['items']]" 2>/dev/null

echo
echo "=== [4/4] 世界书三态探针（未命中 / 命中在预算内 / 被预算挤出） ==="
curl -s -m 10 -b /tmp/j3 "http://127.0.0.1/api/v1/worldbooks?limit=3" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print('worldbooks total =',d['data']['total']);[print('  -',i['data']['name'],'| entries=',len(i['data'].get('entries',[]))) for i in d['data']['items']]" 2>/dev/null

echo
echo "=== 服务器资源 ==="
free -h | head -2
df -h / | tail -1
echo "DONE"
