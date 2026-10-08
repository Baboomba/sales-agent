#!/usr/bin/env bash
# 전체 검사. CI 도 이 스크립트를 그대로 부른다 — 「CI 에서만 되는 일」이 생기지 않게.
#
#   scripts/check.sh            서버 + 화면
#   scripts/check.sh backend    서버만
#   scripts/check.sh frontend   화면만
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
target="${1:-all}"

step() { printf '\n\033[1m▶ %s\033[0m\n' "$1"; }

check_backend() {
  cd "$root/backend"
  step "서버 · 의존성"
  uv sync --quiet
  step "서버 · 시드 DB"
  [[ -f data/sales.db ]] || uv run python scripts/seed.py
  step "서버 · 린트"
  uv run ruff check .
  step "서버 · 포맷"
  uv run ruff format --check .
  step "서버 · 타입"
  uv run mypy
  step "서버 · 계층 경계"
  uv run lint-imports
  step "서버 · 구조 (모델 모양 · 규칙 ID · 테스트 흐름 · 경고 끄는 주석)"
  uv run python scripts/check_structure.py
  step "서버 · 테스트 (단위 · 그래프 · API · 통합 · 규칙 커버리지)"
  uv run pytest -q
}

check_frontend() {
  cd "$root/frontend"
  step "화면 · 의존성"
  npm ci --silent
  step "화면 · 린트"
  npm run --silent lint
  step "화면 · 구조 (묶음 폴더 · 색 값 · 경고 끄는 주석)"
  node scripts/check-structure.mjs
  step "화면 · 포맷"
  npm run --silent format:check
  step "화면 · 타입"
  npm run --silent typecheck
  step "화면 · 테스트"
  npm run --silent test
  step "화면 · 빌드"
  npm run --silent build
}

# git 훅이 꺼져 있으면 알린다 — 사람이 직접 커밋할 때 본 가지 보호 · 검사가 돌지 않는다.
if [[ "$(git -C "$root" config core.hooksPath || true)" != ".githooks" ]]; then
  printf '\033[33m⚠ git 훅이 꺼져 있습니다 — git config core.hooksPath .githooks\033[0m\n'
fi

case "$target" in
  backend) check_backend ;;
  frontend) check_frontend ;;
  all) check_backend; check_frontend ;;
  *) echo "알 수 없는 대상: $target (backend · frontend · all)" >&2; exit 1 ;;
esac

printf '\n\033[32m✔ 검사 통과\033[0m\n'
