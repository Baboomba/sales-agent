#!/usr/bin/env bash
# PreToolUse(Bash) 훅. 에이전트가 협업 규칙을 어기는 git 명령을 실행하지 못하게 막는다.
# 종료 코드 2 는 실행을 막고, stderr 를 에이전트에게 사유로 돌려준다.
set -euo pipefail

command=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))')

block() {
  echo "막힘: $1" >&2
  echo "근거: AGENTS.md 「이슈와 분기 없이 커밋하지 않는다」 · 「검사를 우회하지 않는다」" >&2
  exit 2
}

# 검사 우회
if [[ "$command" =~ git[[:space:]].*--no-verify ]]; then
  block "--no-verify 로 검사를 건너뛸 수 없다."
fi

# main 에 직접 커밋 · 푸시
if [[ "$command" =~ git[[:space:]]+(commit|push) ]]; then
  branch=$(git -C "${CLAUDE_PROJECT_DIR:-.}" branch --show-current 2>/dev/null || true)
  if [[ "$branch" == "main" ]]; then
    block "main 에서 직접 커밋 · 푸시할 수 없다. <종류>/<이슈번호> 분기를 만든다."
  fi
  if [[ "$command" =~ push.*(--force|-f)([[:space:]]|$) ]] && [[ ! "$command" =~ --force-with-lease ]]; then
    block "--force 대신 --force-with-lease 를 쓴다."
  fi
fi

exit 0
