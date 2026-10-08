#!/usr/bin/env bash
# 다시 검사할 범위를 기계로 정한다 (docs/convention/review.md 3절).
#
#   scripts/review-scope.sh mark   검사를 맡기기 직전에 지금 작업 트리를 기준점으로 남긴다
#   scripts/review-scope.sh diff   기준점 뒤로 바뀐 것 — 다시 검사의 범위
#
# 커밋하지 않은 파일과 새 파일까지 담는다. 기준점은 .git 안에만 두고 이력에 남기지 않는다.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
point="$(git rev-parse --git-path review-point)"

# 작업 트리 전체(무시 목록 제외)를 임시 색인에 담아 트리 하나로 만든다. 진짜 색인은 건드리지 않는다.
snapshot() {
  local index
  index="$(mktemp -u)"
  GIT_INDEX_FILE="$index" git add -A
  GIT_INDEX_FILE="$index" git write-tree
  rm -f "$index"
}

case "${1:-}" in
  mark)
    snapshot >"$point"
    echo "기준점을 남겼습니다: $(cat "$point")"
    ;;
  diff)
    if [[ ! -f "$point" ]]; then
      echo "기준점이 없습니다. 검사를 맡기기 전에 'scripts/review-scope.sh mark' 를 먼저 돌리세요." >&2
      exit 1
    fi
    now="$(snapshot)"
    git diff --stat "$(cat "$point")" "$now"
    echo
    git diff "$(cat "$point")" "$now"
    ;;
  *)
    sed -n '2,7p' "$0"
    exit 2
    ;;
esac
