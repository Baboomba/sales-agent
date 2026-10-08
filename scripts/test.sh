#!/usr/bin/env bash
# 서버 테스트만 빠르게. 인자는 pytest 로 넘긴다.
#
#   scripts/test.sh                    전체
#   scripts/test.sh tests/unit         단위만
#   scripts/test.sh -k QRY-R006        규칙 하나
set -euo pipefail

cd "$(dirname "$0")/../backend"
[[ -f data/sales.db ]] || uv run python scripts/seed.py
uv run pytest "$@"
