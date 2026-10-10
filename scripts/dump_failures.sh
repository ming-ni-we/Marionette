#!/usr/bin/env bash
set -u
cd /opt/marionette || exit 1
echo "=== 完整失败详情（--tb=long，只列失败） ==="
docker compose exec -T -e MARIONETTE_INTEGRATION=1 -e ASSETS_DIR=/tmp/mtest-assets \
  api python -m pytest -q --tb=long -p no:randomly 2>&1 > /tmp/pytest_full.log
echo "--- 摘要 ---"
grep -E "^(FAILED|ERROR|[0-9]+ (failed|passed))" /tmp/pytest_full.log
echo
echo "--- 首个失败完整回溯 ---"
awk '/_ test_assets_empty_page_is_not_500 _/,/^_{10,}/' /tmp/pytest_full.log | head -80
echo
echo "--- worldbook 400 响应体 ---"
awk '/test_worldbook_test_endpoint_three_states/,0' /tmp/pytest_full.log | head -60
