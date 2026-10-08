#!/usr/bin/env bash
# 평가 세트를 실제 모델로 돌린다. 모델 서버가 떠 있어야 한다.
#
#   scripts/eval.sh                                    기본 모델
#   scripts/eval.sh qwen2.5-coder:0.5b qwen2.5-coder:1.5b
#
# OLLAMA_BASE_URL 로 모델 서버를 고른다. 기본은 http://localhost:11434
set -euo pipefail

cd "$(dirname "$0")/../backend"
[[ -f data/sales.db ]] || uv run python scripts/seed.py
uv run python -m evaluation.run "$@"
