#!/usr/bin/env bash
# 변이 테스트. 판단 코드를 기계로 바꿔 보고, 테스트가 잡지 못한 변이를 보여 준다.
# 바꿔 볼 코드와 돌릴 테스트는 backend/pyproject.toml 의 [tool.mutmut] 이 정한다.
#
#   scripts/mutate.sh            소스가 바뀐 함수의 변이만 돈다 (수 초)
#   scripts/mutate.sh --recheck  살아남은 변이도 다시 돈다 (1분 안쪽). 살아남은 변이를 잡으려고 테스트를 더한 뒤
#   scripts/mutate.sh --full     처음부터 모두 돈다 (2분 안팎). PR 을 열기 전에 돌린다
#
# mutmut 은 소스가 그대로인 함수의 결과를 다시 쓰지 않는다. 그래서 기본 실행은
# * 테스트를 더해도 지난번 「살아남음」을 그대로 보인다 — 실제보다 더 보고하는 쪽이라 놓치지 않는다. --recheck 로 지운다.
# * 테스트를 지우거나 약하게 바꿔도 지난번 「잡힘」을 그대로 보인다 — 놓치는 쪽이다. 그래서 PR 전에는 --full 로 돈다.
#
# 살아남아도 되는 변이는 문구 · assert_never 갈래 · 동치 변이뿐이다. 그 밖이 살아남으면 테스트가 빠진 것이다
# (docs/convention/testing.md 10절).
set -euo pipefail

cd "$(dirname "$0")/../backend"
# macOS 에서 httpx 가 시스템 프록시 설정을 읽으면(_scproxy), mutmut 이 fork 한 자식이 segfault 로 죽는다.
# 죽은 변이는 「잡힘」으로 셈해져 테스트가 빠진 자리를 가린다. 프록시 환경변수를 두면 시스템 설정을 읽지 않는다.
export no_proxy='*'

mode="${1:-}"
case "$mode" in
  "" | --recheck | --full) ;;
  *) echo "모르는 인자: $mode (--recheck · --full)" >&2; exit 2 ;;
esac
if [[ "$mode" == "--full" ]]; then
  rm -rf mutants
fi

run_mutmut() {
  local log
  log="$(mktemp)"
  if ! uv run mutmut run "$@" >"$log" 2>&1; then
    tail -40 "$log"
    echo "변이 테스트를 돌리지 못했습니다." >&2
    exit 1
  fi
  rm -f "$log"
}

# 살아남은 변이(종료 코드 0)의 결과를 비워 다시 돌게 한다. 이름으로 넘기면 테스트 시간 수집부터 다시 한다.
if [[ "$mode" == "--recheck" && -d mutants ]]; then
  find mutants -name '*.meta' -print0 | xargs -0 python3 -c '
import json, sys
for path in sys.argv[1:]:
    with open(path, encoding="utf-8") as f:
        meta = json.load(f)
    codes = meta["exit_code_by_key"]
    meta["exit_code_by_key"] = {key: (None if code == 0 else code) for key, code in codes.items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
'
fi
run_mutmut

# 테스트가 잡은 것(killed)과 살아남은 것(survived) 말고는 결과를 믿을 수 없다. 시간 초과는 끝나지 않는
# 변이라 잡힌 것으로 보되 수를 알린다. 그 밖(segfault · suspicious 등)이 있으면 멈춘다.
statuses="$(uv run mutmut results --all true 2>/dev/null | awk -F': ' '{print $NF}' | sort | uniq -c)"
echo "$statuses"
if echo "$statuses" | grep -vqE ' (killed|survived|timeout)$'; then
  echo "잡힘 · 살아남음 · 시간 초과가 아닌 결과가 있습니다. 테스트가 잡은 것이 아니라 변이가 죽은 것이라 결과를 믿을 수 없습니다." >&2
  exit 1
fi

survived="$(uv run mutmut results 2>/dev/null | awk -F: '/: survived/ {print $1}')"
if [[ -z "$survived" ]]; then
  echo "살아남은 변이 없음"
  exit 0
fi

# 변이마다 mutmut 을 따로 띄우면 하나에 0.5초씩 든다. 한 프로세스에서 모두 보인다.
# shellcheck disable=SC2086
uv run python - $survived <<'PY' 2>/dev/null | grep -E '^(===|[-+][^-+])' || true
import contextlib, io, sys
from mutmut.__main__ import cli

for name in sys.argv[1:]:
    print(f"=== {name}")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        cli.main(["show", name], standalone_mode=False)
    print(out.getvalue())
PY
echo
echo "살아남은 변이 $(echo "$survived" | wc -l | tr -d ' ')개. 문구 · assert_never 갈래 · 동치 변이가 아닌 것이 있으면 테스트를 더한다."
