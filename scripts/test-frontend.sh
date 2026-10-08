#!/usr/bin/env bash
# 화면 테스트만 빠르게. 인자는 vitest 로 넘긴다.
#
#   scripts/test-frontend.sh                                        전체
#   scripts/test-frontend.sh src/features/AskQuery/__test__/service.test.ts   파일 하나
set -euo pipefail

cd "$(dirname "$0")/../frontend"
[[ -d node_modules ]] || npm ci --silent
npm run --silent test -- "$@"
