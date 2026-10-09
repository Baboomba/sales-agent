#!/usr/bin/env bash
# 소스 코드 밖의 것을 모두 지운다 — 의존성 · 캐시 · 빌드 · 시드 DB · 테스트 결과 · 이 프로젝트의 도커
# 컨테이너 · 이미지 · 볼륨(모델). 지운 뒤에는 scripts/bootstrap.sh 로 다시 갖춘다.
#
#   scripts/clean.sh                   지울 것과 크기만 보인다 (아무것도 지우지 않는다)
#   scripts/clean.sh --yes             지운다
#   scripts/clean.sh --yes --global    다른 프로젝트와 함께 쓰는 것(테스트 브라우저 · 이 컴퓨터의 Ollama 모델)도
#
# 지우지 않는 것 — git 이 추적하는 파일, 추적하지 않지만 무시되지도 않는 파일(작업 중인 새 파일),
# 설정 파일 .env, git 설정, 다른 프로젝트의 도커 자원.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/common.sh
source "$root/scripts/lib/common.sh"

apply=0
global=0
for arg in "$@"; do
  case "$arg" in
    --yes) apply=1 ;;
    --global) global=1 ;;
    *) echo "알 수 없는 선택: $arg (--yes · --global)" >&2; exit 2 ;;
  esac
done

# 이 프로젝트의 도커 자원 — 이름으로만 고른다. 다른 프로젝트의 것은 건드리지 않는다.
CONTAINERS=("$ollama_container" sales-eval-ollama)
IMAGES=(sales-agent:local)
VOLUMES=(sales-agent_ollama)
OLLAMA_IMAGE="ollama/ollama:latest"
playwright_dir="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/Library/Caches/ms-playwright}"
[[ -d "$playwright_dir" ]] || playwright_dir="$HOME/.cache/ms-playwright"

size_of() { du -sh "$1" 2>/dev/null | cut -f1; }
docker_ready() { has docker && docker info >/dev/null 2>&1; }
# git 이 무시하는 것 가운데 .env 를 뺀 것. 추적하는 파일과 작업 중인 새 파일은 들지 않는다.
ignored() { git -C "$root" clean -ndX -e '!.env' | sed 's/^Would remove //'; }

if [[ "$apply" -eq 0 ]]; then
  printf '\033[33m지울 것을 보이기만 합니다. 지우려면 --yes 를 붙입니다.\033[0m\n'
fi

step "1. 띄운 서버"
if [[ -f "$root/.run/serve.pid" ]] && kill -0 "$(cat "$root/.run/serve.pid")" 2>/dev/null; then
  if [[ "$apply" -eq 1 ]]; then
    "$root/scripts/serve.sh" --stop >/dev/null
    ok "내렸습니다 (scripts/serve.sh 로 띄운 것)"
  else
    echo "  내릴 것: scripts/serve.sh 로 띄운 서버 · 화면"
  fi
else
  ok "scripts/serve.sh 로 띄운 것이 없습니다"
fi

step "2. 저장소 안 (git 이 무시하는 것, .env 는 남긴다)"
# macOS 기본 bash(3.2)에는 mapfile 이 없다 — 줄마다 읽는다.
paths="$(ignored)"
if [[ -z "$paths" ]]; then
  ok "지울 것이 없습니다"
else
  while IFS= read -r path; do
    printf '  %-8s %s\n' "$(size_of "$root/$path")" "$path"
  done <<<"$paths"
  if [[ "$apply" -eq 1 ]]; then
    git -C "$root" clean -fdX -e '!.env' >/dev/null
    ok "지웠습니다"
  fi
fi

step "3. 도커 (이 프로젝트의 것만)"
if ! docker_ready; then
  warn "도커가 꺼져 있거나 없습니다 — 건너뜁니다"
else
  for name in "${CONTAINERS[@]}"; do
    docker container inspect "$name" >/dev/null 2>&1 || continue
    echo "  컨테이너  $name"
    [[ "$apply" -eq 1 ]] && docker rm -f "$name" >/dev/null
  done
  for name in "${VOLUMES[@]}"; do
    docker volume inspect "$name" >/dev/null 2>&1 || continue
    echo "  볼륨      $name (받아 둔 모델)"
    [[ "$apply" -eq 1 ]] && docker volume rm "$name" >/dev/null
  done
  for name in "${IMAGES[@]}"; do
    docker image inspect "$name" >/dev/null 2>&1 || continue
    echo "  이미지    $name ($(docker image inspect -f '{{.Size}}' "$name" | awk '{printf "%.0fMB", $1/1000000}'))"
    [[ "$apply" -eq 1 ]] && docker rmi "$name" >/dev/null
  done
  if docker image inspect "$OLLAMA_IMAGE" >/dev/null 2>&1; then
    # 다른 컨테이너가 쓰고 있으면 남긴다 — 다른 프로젝트의 것일 수 있다.
    users="$(docker ps -a --filter "ancestor=$OLLAMA_IMAGE" --format '{{.Names}}' |
      grep -vxF -f <(printf '%s\n' "${CONTAINERS[@]}") || true)"
    if [[ -n "$users" ]]; then
      warn "이미지 $OLLAMA_IMAGE 는 남깁니다 — 다른 컨테이너가 씁니다: $(echo "$users" | tr '\n' ' ')"
    else
      echo "  이미지    $OLLAMA_IMAGE ($(docker image inspect -f '{{.Size}}' "$OLLAMA_IMAGE" | awk '{printf "%.0fMB", $1/1000000}'))"
      [[ "$apply" -eq 1 ]] && docker rmi "$OLLAMA_IMAGE" >/dev/null
    fi
  fi
  [[ "$apply" -eq 1 ]] && ok "지웠습니다"
fi

step "4. 다른 프로젝트와 함께 쓰는 것"
if [[ "$global" -eq 0 ]]; then
  echo "  건너뜁니다 — 지우려면 --global (테스트 브라우저 $(size_of "$playwright_dir" || echo '-') · 이 컴퓨터의 Ollama 모델)"
else
  if [[ -d "$playwright_dir" ]]; then
    echo "  테스트 브라우저  $(size_of "$playwright_dir")  ${playwright_dir/#$HOME/~}"
    [[ "$apply" -eq 1 ]] && rm -rf "$playwright_dir"
  fi
  if has ollama && ollama list 2>/dev/null | grep -q "^$model"; then
    echo "  이 컴퓨터의 Ollama 모델  $model"
    [[ "$apply" -eq 1 ]] && ollama rm "$model" >/dev/null
  fi
  [[ "$apply" -eq 1 ]] && ok "지웠습니다"
fi

if [[ "$apply" -eq 1 ]]; then
  printf '\n\033[32m✔ 소스 코드만 남았습니다\033[0m — 다시 갖추려면 scripts/bootstrap.sh\n'
else
  printf '\n위 목록을 지우려면: scripts/clean.sh --yes%s\n' "$([[ "$global" -eq 1 ]] && echo ' --global')"
fi
