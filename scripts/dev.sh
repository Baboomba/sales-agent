#!/usr/bin/env bash
# 개발 서버. 서버(8000)와 화면(5173)을 함께 띄운다. 화면은 /api 를 서버로 넘긴다.
# 모델 서버는 따로 띄운다 — Mac 이면 `ollama serve`, 아니면 `docker compose up -d ollama`.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
(cd "$root/backend" && { [[ -f data/sales.db ]] || uv run python scripts/seed.py; } && uv run uvicorn --factory app.main:app_from_env --reload --port 8000) &
server=$!
trap 'kill $server 2>/dev/null' EXIT
cd "$root/frontend" && npm run dev
