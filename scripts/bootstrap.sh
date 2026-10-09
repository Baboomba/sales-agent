#!/usr/bin/env bash
# 클론 직후 개발 환경을 한 번에 갖춘다. 여러 번 돌려도 결과가 같다 — 이미 된 단계는 건너뛴다.
#
#   scripts/bootstrap.sh              모두 (모델 받기 · 전체 검사 포함)
#   scripts/bootstrap.sh --no-model   모델(약 1GB)을 받지 않는다
#   scripts/bootstrap.sh --no-check   마지막 전체 검사를 건너뛴다
#
# 데이터 · 볼륨을 지우지 않는다. 비밀 값을 만들지 않는다 — 설정은 모두 환경변수이고 기본값이 있다.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$root/scripts/lib/common.sh"
pull_model=1
run_check=1

for arg in "$@"; do
  case "$arg" in
    --no-model) pull_model=0 ;;
    --no-check) run_check=0 ;;
    *) echo "알 수 없는 선택: $arg (--no-model · --no-check)" >&2; exit 2 ;;
  esac
done

step "1. 준비물"
has git || fail "git 이 없습니다 — https://git-scm.com"
ok "git"
has uv || fail "uv 가 없습니다 — curl -LsSf https://astral.sh/uv/install.sh | sh (Python 3.13 은 uv 가 받습니다)"
ok "uv $(uv --version | awk '{print $2}')"
has node || fail "Node 가 없습니다 — Node 24 이상을 설치하세요 (https://nodejs.org)"
node_major="$(node -p 'process.versions.node.split(".")[0]')"
[[ "$node_major" -ge 24 ]] || fail "Node 24 이상이 필요합니다 (지금 $(node --version))"
ok "Node $(node --version)"
has npm || fail "npm 이 없습니다 — Node 와 함께 설치됩니다"
ok "npm $(npm --version)"

step "2. git 훅"
if [[ "$(git -C "$root" config core.hooksPath || true)" == ".githooks" ]]; then
  ok "이미 켜져 있습니다"
else
  git -C "$root" config core.hooksPath .githooks
  ok "켰습니다 — main 직접 커밋 · 푸시와 포맷 안 된 커밋을 막습니다"
fi

step "3. 스킬 링크"
broken=0
for link in "$root"/.claude/skills/*; do
  [[ -d "$link" ]] || { warn "끊긴 링크: ${link#"$root"/}"; broken=1; }
done
if [[ "$broken" -eq 0 ]]; then
  ok "스킬 링크가 모두 이어져 있습니다"
else
  warn "Windows 면 git clone -c core.symlinks=true 로 다시 받으세요 (README 개발 절)"
fi

step "4. 서버 의존성"
(cd "$root/backend" && uv sync --quiet)
ok "uv sync"

step "5. 화면 의존성"
(cd "$root/frontend" && npm ci --silent)
ok "npm ci"

step "6. 시드 데이터"
if [[ -f "$root/backend/data/sales.db" ]]; then
  ok "이미 있습니다 (backend/data/sales.db)"
else
  (cd "$root/backend" && uv run python scripts/seed.py)
  ok "만들었습니다"
fi

step "7. 모델 서버"
ensure_model_server

step "8. 모델 ($model)"
if model_ready; then
  ok "이미 받았습니다"
elif [[ "$pull_model" -eq 0 ]]; then
  warn "받지 않았습니다 (--no-model). 질문하려면 다시 돌리거나 모델을 받으세요"
else
  echo "  모델을 받습니다 (약 1GB, 처음 한 번)…"
  curl -sf "$ollama_url/api/pull" -d "{\"name\":\"$model\",\"stream\":false}" >/dev/null ||
    fail "모델을 받지 못했습니다 — 인터넷 연결과 모델 이름($model)을 확인하세요"
  ok "받았습니다"
fi

if [[ "$run_check" -eq 1 ]]; then
  step "9. 전체 검사"
  "$root/scripts/check.sh"
else
  step "9. 전체 검사"
  warn "건너뛰었습니다 (--no-check)"
fi

printf '\n\033[32m✔ 준비가 끝났습니다\033[0m\n'
cat <<'NEXT'

다음 할 일
  scripts/serve.sh   서버를 띄워 브라우저로 — 화면 http://localhost:5173 (--open 으로 연다)
  scripts/check.sh   전체 검사 — CI 와 같다
  scripts/eval.sh    평가 세트 (모델 서버 필요)
NEXT
