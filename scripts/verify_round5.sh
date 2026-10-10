#!/usr/bin/env bash
# 第五轮验证（严谨版）：上一轮因新镜像里没装 pytest，集成测试根本没跑，
# 所以"零写入 PASS"是空过的。这一轮先装 pytest 再跑，并且用中文名卡片验导出。
set -u
cd /opt/marionette || exit 1

PSQL="docker compose exec -T db psql -U postgres -d marionette -tAc"
count_public() {
  $PSQL "select (select count(*) from public.cards)||'/'||(select count(*) from public.worldbooks)||'/'||(select count(*) from public.presets)||'/'||(select count(*) from public.assets)||'/'||(select count(*) from public.sessions)"
}

echo "=== [0/7] 清理历史残留临时 schema ==="
$PSQL "select nspname from pg_namespace where nspname like 'mtest_%' or nspname like 'probe_%'" | while read -r s; do
  [ -z "$s" ] && continue
  echo "  drop $s"
  $PSQL "drop schema if exists \"$s\" cascade" >/dev/null
done
echo "  清理后残留 = $($PSQL "select coalesce(string_agg(nspname,','),'(none)') from pg_namespace where nspname like 'mtest_%' or nspname like 'probe_%'")"

echo
echo "=== [1/7] 容器内安装测试依赖 ==="
docker compose exec -T api sh -c "pip install -q pytest pytest-asyncio" 2>&1 | grep -v "WARNING: Running pip" | tail -3
echo "  pytest 版本: $(docker compose exec -T api python -m pytest --version 2>&1 | head -1)"

echo
echo "=== [2/7] 集成测试前 public 基线 ==="
BEFORE=$(count_public)
echo "BEFORE = $BEFORE"

echo
echo "=== [3/7] 集成测试（真实 Postgres + 隔离守卫） ==="
docker compose exec -T -e MARIONETTE_INTEGRATION=1 -e ASSETS_DIR=/tmp/mtest-assets \
  api python -m pytest -q 2>&1 | tail -18

echo
echo "=== [4/7] 集成测试后 public 复核（硬判据） ==="
AFTER=$(count_public)
echo "AFTER  = $AFTER"
if [ "$BEFORE" = "$AFTER" ]; then
  echo ">>> 判据一 PASS：集成测试对 public 零写入"
else
  echo ">>> 判据一 FAIL：public 行数变化（$BEFORE -> $AFTER），隔离仍未生效！"
fi

echo
echo "=== [5/7] 残留临时 schema（应为 none） ==="
echo "残留 = $($PSQL "select coalesce(string_agg(nspname,','),'(none)') from pg_namespace where nspname like 'mtest_%' or nspname like 'probe_%'")"

echo
echo "=== [6/7] 中文名卡片导出（缺陷 1 的真实验证） ==="
PW=$(grep -E '^ACCESS_PASSWORD=' .env | cut -d= -f2-)
echo "login=$(curl -s -m 10 -c /tmp/j5 -X POST http://127.0.0.1/api/v1/auth/login -H 'Content-Type: application/json' -d "{\"password\":\"$PW\"}" -o /dev/null -w '%{http_code}')"
# 取一张中文名卡（日常向样例名字都是中文）
curl -s -m 10 -b /tmp/j5 "http://127.0.0.1/api/v1/cards?q=%E6%97%A5%E5%B8%B8&limit=1" -o /tmp/c.json
CID=$(python3 -c "import json;d=json.load(open('/tmp/c.json'));print(d['data']['items'][0]['id'])" 2>/dev/null)
CNAME=$(python3 -c "import json;d=json.load(open('/tmp/c.json'));print(d['data']['items'][0]['data']['name'])" 2>/dev/null)
echo "sample card = $CNAME ($CID)"
if [ -n "${CID:-}" ]; then
  echo "export json  -> $(curl -s -m 15 -b /tmp/j5 -o /tmp/e.json -w '%{http_code}' "http://127.0.0.1/api/v1/export/card/$CID?format=json")"
  echo "  header: $(curl -s -m 15 -b /tmp/j5 -D - -o /dev/null "http://127.0.0.1/api/v1/export/card/$CID?format=json" | grep -i '^content-disposition' | tr -d '\r')"
  echo "export png   -> $(curl -s -m 20 -b /tmp/j5 -o /tmp/e.png -w '%{http_code}' "http://127.0.0.1/api/v1/export/card/$CID?format=png")"
  echo "bundle zip   -> $(curl -s -m 20 -b /tmp/j5 -o /tmp/e.zip -w '%{http_code}' -X POST http://127.0.0.1/api/v1/export/bundle -H 'Content-Type: application/json' -d "{\"card_ids\":[\"$CID\"]}")"
fi

echo
echo "=== [7/7] 世界书导入 + 三态命中测试（缺陷 3/4 的真实验证） ==="
cat > /tmp/wb.json <<'JSON'
{"name":"验证用世界书","entries":[
 {"id":"c","keys":[],"content":"常驻设定","constant":true,"priority":100},
 {"id":"h","keys":["咖啡馆"],"content":"命中且在预算内","priority":50}]}
JSON
curl -s -m 15 -b /tmp/j5 -X POST http://127.0.0.1/api/v1/import/worldbook -F "file=@/tmp/wb.json;type=application/json" -F "on_conflict=rename" -o /tmp/wb_resp.json -w "import/worldbook -> %{http_code}\n"
python3 -c "
import json
d=json.load(open('/tmp/wb_resp.json'))
dd=d.get('data') or {}
print('  source_format =', dd.get('source_format'))
print('  object_id     =', dd.get('object_id'))
" 2>/dev/null

echo
echo "DONE"
