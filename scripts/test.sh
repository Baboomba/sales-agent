#!/usr/bin/env bash
# 서버 테스트만 빠르게. 인자는 pytest 로 넘긴다.
#
#   scripts/test.sh                    전체
#   scripts/test.sh tests/query        질의 도메인만
#   scripts/test.sh -k qry_r006        규칙 하나 (테스트 이름의 qry_r006 으로 고른다)
set -euo pipefail

cd "$(dirname "$0")/../backend"
[[ -f data/sales.db ]] || uv run python scripts/seed.py
uv run pytest "$@"
