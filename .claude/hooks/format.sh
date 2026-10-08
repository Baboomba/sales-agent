#!/usr/bin/env bash
# PostToolUse(Edit|Write) 훅. 에이전트가 고친 파일을 바로 포맷한다.
# 포맷 차이로 검사가 실패하는 왕복을 없앤다. 포맷이 실패해도 작업은 막지 않는다.
set -uo pipefail

file=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))')
root="${CLAUDE_PROJECT_DIR:-.}"

case "$file" in
  "$root"/backend/*.py)
    (cd "$root/backend" && uv run --quiet ruff format "$file" && uv run --quiet ruff check --fix --quiet "$file") >/dev/null 2>&1
    ;;
  "$root"/frontend/src/*.ts | "$root"/frontend/src/*.tsx | "$root"/frontend/src/*.css)
    (cd "$root/frontend" && npx --no-install prettier --write "$file") >/dev/null 2>&1
    ;;
esac

exit 0
