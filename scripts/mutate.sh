#!/usr/bin/env bash
# 변이 테스트. 판단 코드를 기계로 바꿔 보고, 테스트가 잡지 못한 변이를 보여 준다.
# 바꿔 볼 코드와 돌릴 테스트는 backend/pyproject.toml 의 [tool.mutmut] 이 정한다.
#
#   scripts/mutate.sh
#
# 살아남아도 되는 변이는 문구 · assert_never 갈래 · 동치 변이뿐이다. 그 밖이 살아남으면 테스트가 빠진 것이다
# (docs/convention/testing.md 10절).
set -euo pipefail

cd "$(dirname "$0")/../backend"
rm -rf mutants
# macOS 에서 httpx 가 시스템 프록시 설정을 읽으면(_scproxy), mutmut 이 fork 한 자식이 segfault 로 죽는다.
# 죽은 변이는 「잡힘」으로 셈해져 테스트가 빠진 자리를 가린다. 프록시 환경변수를 두면 시스템 설정을 읽지 않는다.
export no_proxy='*'
log="$(mktemp)"
if ! uv run mutmut run >"$log" 2>&1; then
  tail -40 "$log"
  echo "변이 테스트를 돌리지 못했습니다." >&2
  exit 1
fi
rm -f "$log"

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

for mutant in $survived; do
  echo "=== $mutant"
  uv run mutmut show "$mutant" 2>/dev/null | grep -E '^[-+][^-+]' || true
done
echo
echo "살아남은 변이 $(echo "$survived" | wc -l | tr -d ' ')개. 문구 · assert_never 갈래 · 동치 변이가 아닌 것이 있으면 테스트를 더한다."
