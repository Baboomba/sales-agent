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
log="$(mktemp)"
if ! uv run mutmut run >"$log" 2>&1; then
  tail -40 "$log"
  echo "변이 테스트를 돌리지 못했습니다." >&2
  exit 1
fi
rm -f "$log"

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
