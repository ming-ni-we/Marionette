#!/usr/bin/env bash
# 第四轮验证：证明「集成测试不再污染生产库」且「9 项失败全部转绿」。
# 判据一：跑集成测试前后，public 里的行数必须完全不变。
# 判据二：集成测试结果应为 0 failed。
# 判据三：跑完后不应残留 mtest_* schema。
set -u
cd /opt/marionette || exit 1

PSQL="docker compose exec -T db psql -U postgres -d marionette -tAc"

count_public() {
  $PSQL "select
      (select count(*) from public.cards)
    ||'/'|| (select count(*) from public.worldbooks)
    ||'/'|| (select count(*) from public.presets)
    ||'/'|| (select count(*) from public.assets)
    ||'/'|| (select count(*) from public.sessions)"
}

echo "=== [1/6] 部署新代码后的容器状态 ==="
docker compose ps --format "table {{.Name}}\t{{.Status}}"

echo
echo "=== [2/6] 集成测试前 public 基线（cards/worldbooks/presets/assets/sessions） ==="
BEFORE=$(count_public)
echo "BEFORE = $BEFORE"

echo
echo "=== [3/6] 集成测试（真实 Postgres + 隔离守卫） ==="
docker compose exec -T -e MARIONETTE_INTEGRATION=1 -e ASSETS_DIR=/tmp/mtest-assets \
  api python -m pytest -q 2>&1 | tail -20

echo
echo "=== [4/6] 集成测试后 public 复核 ==="
AFTER=$(count_public)
echo "AFTER  = $AFTER"
if [ "$BEFORE" = "$AFTER" ]; then
  echo ">>> 判据一 PASS：集成测试对 public 零写入"
else
  echo ">>> 判据一 FAIL：public 行数发生变化（$BEFORE -> $AFTER），隔离仍未生效！"
fi

echo
echo "=== [5/6] 残留临时 schema 检查（应为空） ==="
LEFT=$($PSQL "select coalesce(string_agg(nspname,','),'(none)') from pg_namespace where nspname like 'mtest_%' or nspname like 'probe_%'")
echo "残留 = $LEFT"

echo
echo "=== [6/6] 线上创作侧端到端抽查 ==="
PW=$(grep -E '^ACCESS_PASSWORD=' .env | cut -d= -f2-)
LOGIN=$(curl -s -m 10 -c /tmp/j4 -X POST http://127.0.0.1/api/v1/auth/login \
  -H "Content-Type: application/json" -d "{\"password\":\"$PW\"}" -o /dev/null -w "%{http_code}")
echo "login=$LOGIN"
# 中文检索（百分号编码，绕开终端编码）：日常 / 林晚
for ENC in %E6%97%A5%E5%B8%B8 %E6%9E%97%E6%99%9A; do
  echo "q=$ENC -> $(curl -s -m 10 -b /tmp/j4 -o /dev/null -w '%{http_code}' "http://127.0.0.1/api/v1/cards?q=$ENC&limit=3")"
done
# 挑一张中文名卡片，验证导出不再 500（缺陷 1 的线上证据）
CID=$(curl -s -m 10 -b /tmp/j4 "http://127.0.0.1/api/v1/cards?limit=1" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['items'][0]['id'])" 2>/dev/null)
echo "sample card = $CID"
if [ -n "${CID:-}" ]; then
  echo "export json  -> $(curl -s -m 15 -b /tmp/j4 -o /tmp/exp.json -w '%{http_code}' "http://127.0.0.1/api/v1/export/card/$CID?format=json")"
  echo "  Content-Disposition: $(curl -s -m 15 -b /tmp/j4 -D - -o /dev/null "http://127.0.0.1/api/v1/export/card/$CID?format=json" | grep -i '^content-disposition' | tr -d '\r')"
  echo "export png   -> $(curl -s -m 20 -b /tmp/j4 -o /tmp/exp.png -w '%{http_code}' "http://127.0.0.1/api/v1/export/card/$CID?format=png")"
fi

echo
echo "DONE"
