#!/usr/bin/env bash
# 서버를 띄워 브라우저에서 볼 수 있게 한다. 서버(8000)와 화면(5173)을 뒤에서 띄우고, 둘 다 답할 때까지
# 기다렸다가 주소를 알린다. 이미 떠 있으면 다시 띄우지 않는다.
#
#   scripts/serve.sh            띄운다
#   scripts/serve.sh --open     띄우고 브라우저로 연다
#   scripts/serve.sh --status   떠 있는지 본다
#   scripts/serve.sh --stop     이 스크립트가 띄운 것을 내린다
#
# 기록은 .run/serve.log 에 남는다. 앞에서 보며 띄우려면 scripts/dev.sh 를 쓴다.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$root/scripts/lib/common.sh"

run_dir="$root/.run"
pid_file="$run_dir/serve.pid"
log_file="$run_dir/serve.log"
screen_url="http://localhost:5173"
server_url="http://localhost:8000"
action="start"
open_browser=0

for arg in "$@"; do
  case "$arg" in
    --open) open_browser=1 ;;
    --status) action="status" ;;
    --stop) action="stop" ;;
    *) echo "알 수 없는 선택: $arg (--open · --status · --stop)" >&2; exit 2 ;;
  esac
done

server_up() { curl -sf -m 2 "$server_url/api/health" >/dev/null; }
screen_up() { curl -sf -m 2 "$screen_url" >/dev/null; }
ours_running() { [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; }

open_url() {
  if has open; then
    open "$screen_url"
  elif has xdg-open; then
    xdg-open "$screen_url" >/dev/null 2>&1
  else
    warn "브라우저를 열 수 없습니다 — $screen_url 을 직접 여세요"
  fi
}

report() {
  printf '\n\033[32m✔ 떠 있습니다\033[0m\n'
  echo "  화면  $screen_url"
  echo "  서버  $server_url  (모델 $(curl -sf -m 2 "$server_url/api/health" | sed -E 's/.*"model":"([^"]*)".*/\1/'))"
  echo "  기록  ${log_file#"$root"/}"
  echo "  내리기  scripts/serve.sh --stop"
}

case "$action" in
  status)
    if server_up && screen_up; then
      report
      ours_running || warn "이 스크립트가 띄운 것이 아닙니다 (scripts/dev.sh 등) — --stop 으로 내릴 수 없습니다"
    else
      echo "떠 있지 않습니다 — scripts/serve.sh 로 띄웁니다"
      exit 1
    fi
    exit 0
    ;;
  stop)
    if ours_running; then
      # 띄울 때 프로세스 묶음을 따로 만들었다 — 묶음째 내려 서버의 자식(다시 읽기 감시)까지 내린다.
      kill -TERM -- "-$(cat "$pid_file")" 2>/dev/null || kill -TERM "$(cat "$pid_file")"
      for _ in $(seq 1 10); do server_up || screen_up || break; sleep 1; done
      rm -f "$pid_file"
      ok "내렸습니다"
    elif server_up || screen_up; then
      warn "이 스크립트가 띄운 것이 아닙니다 — 띄운 곳(scripts/dev.sh 의 터미널 등)에서 내리세요"
      exit 1
    else
      ok "떠 있지 않습니다"
    fi
    exit 0
    ;;
esac

step "1. 이미 떠 있는지"
if server_up && screen_up; then
  ok "이미 떠 있습니다 — 다시 띄우지 않습니다"
  [[ "$open_browser" -eq 1 ]] && open_url
  report
  exit 0
fi
if server_up || screen_up; then
  fail "포트 8000 · 5173 가운데 하나만 쓰이고 있습니다 — lsof -iTCP:8000 -iTCP:5173 -sTCP:LISTEN 으로 확인하세요"
fi
ok "떠 있지 않습니다"

step "2. 준비"
[[ -d "$root/backend/.venv" && -d "$root/frontend/node_modules" ]] ||
  fail "의존성이 없습니다 — scripts/bootstrap.sh 를 먼저 돌리세요"
ok "의존성"
if [[ ! -f "$root/backend/data/sales.db" ]]; then
  (cd "$root/backend" && uv run python scripts/seed.py >/dev/null)
fi
ok "시드 데이터"

step "3. 모델 서버"
ensure_model_server
model_ready || warn "모델($model)이 없습니다 — 화면은 뜨지만 질문하면 실패합니다. scripts/bootstrap.sh 로 받으세요"

step "4. 서버 · 화면"
mkdir -p "$run_dir"
# 작업 제어를 켜 뒤의 작업이 제 프로세스 묶음을 갖게 한다 — 내릴 때 묶음째 내린다.
set -m
nohup "$root/scripts/dev.sh" >"$log_file" 2>&1 &
echo $! >"$pid_file"
set +m
for _ in $(seq 1 60); do server_up && screen_up && break; sleep 1; done
if ! (server_up && screen_up); then
  tail -20 "$log_file" >&2
  fail "60초 안에 뜨지 않았습니다 — 위 기록(${log_file#"$root"/})을 보세요"
fi
ok "서버 8000 · 화면 5173"

[[ "$open_browser" -eq 1 ]] && open_url
report
