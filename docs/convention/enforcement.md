# 검사 장치

규칙을 어느 장치가 막는지의 표다. 규칙의 정본은 [코드 아키텍처](code-architecture.md) · [코드 컨벤션](code-style.md) · [테스트 규칙](testing.md)이다. **장치가 있는 규칙은 사람이 보지 않는다** — 검토(`refactor-review` · `test-review`)는 아래 4절의 규칙에 쓴다.

모든 장치는 `scripts/check.sh` 가 돌린다. CI 도 같은 스크립트를 부른다. 규칙을 더하면 이 표에 장치를 함께 적고, 장치를 둘 수 없으면 4절에 적는다.

## 1. 서버

| 규칙 | 문서 | 장치 |
|---|---|---|
| 계층 방향 api → usecase → rules · dependency → model | 코드 아키텍처 3 | import-linter 「계층」 계약 |
| 모델 · 규칙은 바깥 라이브러리(FastAPI · LangGraph · Ollama · sqlglot …)를 모른다 | 코드 아키텍처 2.1 · 2.2 | import-linter 금지 계약 |
| 모델 · 규칙은 파일 · 시각 · 난수 · DB(`time` · `random` · `datetime` · `os` · `pathlib` · `sqlite3`)를 쓰지 않는다 | 코드 아키텍처 2.2 | import-linter 금지 계약 |
| 구현(`dependency.impl`)은 조립 루트만, API 는 유스케이스만 부른다 | 코드 아키텍처 3 | import-linter 금지 계약 |
| 모델은 메서드 없는 `@dataclass(frozen=True)` 또는 열거 | 코드 아키텍처 2.1 | `scripts/check_structure.py` |
| 규칙의 공개 함수는 문서 문자열 첫 줄에 규칙 ID | 코드 아키텍처 2.2 | `scripts/check_structure.py` |
| 모든 함수에 타입, 열거는 `assert_never` 로 끝까지 | 코드 컨벤션 2 | `mypy --strict` |
| 경고를 끄는 주석(`# noqa` · `# type: ignore`)을 쓰지 않는다 | 코드 컨벤션 1.1 | ruff `PGH` · `RUF100`, `scripts/check_structure.py` |
| 모든 모듈은 `from __future__ import annotations` 로 시작 | 코드 컨벤션 2 | ruff `I002` (`required-imports`) |
| `print` 는 스크립트에서만 | 코드 컨벤션 2 | ruff `T20` (`scripts/` · `evaluation/` 만 예외) |
| 넓은 `except Exception` 은 안전망 한 곳만 | 코드 컨벤션 2 | ruff `BLE001` (`usecase/query_flow.py` 만 예외) |
| 목 라이브러리를 쓰지 않는다 | 테스트 규칙 7.1 | ruff `TID251` (`unittest.mock` · `pytest_mock`) |
| 가짜는 `tests/<도메인>/fake.py` 한 곳에 | 테스트 규칙 7.1 | `scripts/check_structure.py` |
| 통합 테스트에 `pytestmark = pytest.mark.integration` | 테스트 규칙 7.1 | `scripts/check_structure.py` |
| 테스트 함수의 흐름에 if · 반복을 넣지 않는다 | 테스트 규칙 5 | `scripts/check_structure.py` |
| 규칙마다 테스트, 모르는 ID 금지 | 테스트 규칙 8 | `tests/test_rule_coverage.py` |
| 포맷 · 줄 길이 · import 순서 | 코드 컨벤션 머리 | `ruff format` · `ruff check` |

## 2. 화면

| 규칙 | 문서 | 장치 |
|---|---|---|
| 계층 조립 방향, 묶음은 `index.ts` 로만, `../` 금지 | 코드 아키텍처 6.1 · 6.5 · 6.6 | ESLint `no-restricted-imports` |
| 서버는 `api/` 에서만 부른다 | 코드 아키텍처 6.3 | ESLint `no-restricted-globals` (`fetch`) |
| `service.ts` 는 React · 서버 호출을 모른다 | 코드 아키텍처 6.2 | ESLint `no-restricted-imports` (`**/service.ts`) |
| 기능의 `.tsx` 에 훅 정의 · 순수 함수를 두지 않는다 | 코드 아키텍처 6.2 | ESLint `no-restricted-syntax` (`features/**/*.tsx`) |
| 묶음 폴더는 파스칼 · `<이름>.tsx` 와 `index.ts` · 하위 폴더는 `components/` · `__test__/` 뿐 · 부품 · 엔티티에 `hooks.ts` · `service.ts` 없음 | 코드 아키텍처 6.2 · 6.5 | `scripts/check-structure.mjs` |
| 화살표 함수만 | 코드 컨벤션 3 | ESLint `no-restricted-syntax` |
| 이름 있는 내보내기만 (설정 파일 · CSS Modules 선언 예외) | 코드 컨벤션 3 | ESLint `no-restricted-syntax` |
| `as` 단언은 `api/` 에서만 | 코드 컨벤션 3 | ESLint `consistent-type-assertions` |
| props 타입은 `interface` | 코드 컨벤션 3 | ESLint `consistent-type-definitions` |
| 판별 유니온은 `switch` 로 끝까지 | 코드 컨벤션 3 | ESLint `switch-exhaustiveness-check` (타입 정보) |
| 인라인 스타일을 쓰지 않는다 | 코드 컨벤션 3 | ESLint `no-restricted-syntax` (`style` 속성) |
| 색은 `index.css` 의 변수만 | 코드 컨벤션 3 | `scripts/check-structure.mjs` (스타일 파일의 색 값) |
| `any` · `@ts-ignore` · `eslint-disable` 금지 | 코드 컨벤션 1.1 | ESLint `no-explicit-any` · `ban-ts-comment`, `--no-inline-config`, `scripts/check-structure.mjs` |
| 경고로 두지 않는다 (`exhaustive-deps` 등) | 코드 아키텍처 6.6 | ESLint `--max-warnings 0` |
| 접근성 | 코드 컨벤션 3 | ESLint `jsx-a11y` |
| 목을 쓰지 않는다 (`vi.mock` · `vi.fn` · `vi.spyOn`) | 테스트 규칙 7.1 | ESLint `no-restricted-properties` (테스트) |
| 테스트의 흐름에 if · 반복을 넣지 않는다 | 테스트 규칙 5 | ESLint `no-restricted-syntax` (테스트) |
| 스타일(정렬 · 배치 · 크기 · 색)은 테스트하지 않는다 | 테스트 규칙 7.2 | ESLint `no-restricted-syntax` (테스트의 `className` · `style` · `toHaveStyle` · `toHaveClass` · `getComputedStyle`) |
| 화면 규칙마다 테스트 | 테스트 규칙 8 | `tests/test_rule_coverage.py` |
| 타입 엄격 | 코드 컨벤션 3 | TypeScript `strict` · `noUncheckedIndexedAccess` |

## 3. 작업 흐름

| 규칙 | 장치 |
|---|---|
| 본 가지에 직접 커밋 · 올리기 금지, `--no-verify` 금지 | `.claude/hooks/guard-git.sh`(에이전트), `.githooks/pre-commit` · `pre-push`(사람) |
| 고친 파일은 바로 포맷 | `.claude/hooks/format.sh` |
| git 훅이 켜져 있다 | `scripts/bootstrap.sh` 가 켠다. `scripts/check.sh` 가 꺼져 있으면 알린다 |

## 4. 장치가 없는 규칙 — 검토가 본다

기계로 가리기 어려워 검토와 변이 검사(`scripts/mutate.sh`)에 맡긴다.

* 주석은 「왜」를 쓴다, 이름은 뜻이 드러나게, 사용자 문구는 무엇을 할지 드러나게 (코드 컨벤션 1.2 ~ 1.4)
* 판단은 규칙에만 둔다 — 유스케이스 · 구현이 판단하지 않는다 (코드 아키텍처 2.2 · 5.2)
* 모듈 안에서만 쓰는 `_` 이름을 다른 모듈에서 부르지 않는다, 헷갈리는 인자는 키워드로만 (코드 컨벤션 2)
* 숫자를 반올림하지 않는다 (코드 아키텍처 6.3)
* 기대값을 계산하지 않는다, 혼자 참인 단언 금지, 구현에 기대지 않는다, 한 테스트에 한 사실 (테스트 규칙 2 ~ 4)
