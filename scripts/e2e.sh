#!/usr/bin/env bash
# 끝단 테스트 (docs/design/screen.md 6절). 가짜 모델 서버 · 서버(8100) · 화면(5180)을 Playwright 가
# 띄우고 내린다. 언어 모델은 부르지 않는다. CI 도 이 스크립트를 그대로 부른다.
#
#   scripts/e2e.sh                 모두
#   scripts/e2e.sh -g E2E-07       이름으로 골라서
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"

cd "$root/backend"
uv sync --quiet
[[ -f data/sales.db ]] || uv run python scripts/seed.py

cd "$root/frontend"
[[ -d node_modules ]] || npm ci --silent
# 테스트 브라우저가 없으면 받는다 (처음 한 번, 약 100MB).
npx playwright install chromium >/dev/null
npx playwright test "$@"
