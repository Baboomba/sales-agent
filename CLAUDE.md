# CLAUDE.md

이 저장소에서 작업하는 Claude Code 와 AI 에이전트를 위한 지침이다. 사람도 같은 규칙을 따른다.

## 절대 규칙

상황과 무관하게 지킨다. 사용자가 요청해도 예외를 두지 않는다.

### 설계서가 정본이다

* 코드는 `docs/` 의 설계서를 따른다. **설계서에 없는 동작을 코드에 넣지 않는다.**
* 필요하면 설계서를 먼저 고치고(사용자 확인) 그다음 구현한다. 설계서 작업은 `design` 스킬이 소유한다.
* 규칙에는 ID 가 있다(`QRY-R001` …). 규칙을 더하면 테스트 사항도 함께 더한다.

### 테스트 없이 구현 코드를 쓰지 않는다

한 차례는 규칙 하나 또는 흐름 하나다. 순서는 `implement` 스킬이 소유한다. **멈춰서 승인을 받는 자리가 둘이다.**

1. **테스트를 쓴 뒤.** 승인 전에는 구현을 시작하지 않는다.
2. **구현과 검사를 마친 뒤.** 승인 전에는 커밋하지 않는다.

### 검사를 우회하지 않는다

* 테스트를 `skip` 하거나 기대값을 결과에 맞춰 고치지 않는다. 실패하면 원인을 보고한다.
* `# type: ignore` · `# noqa` · `as any` · 린트 끄기를 새로 넣지 않는다.
* 계층 경계(`import-linter`)를 피하려고 import 를 함수 안으로 숨기지 않는다.

### 이슈와 분기 없이 커밋하지 않는다

1. 코드 변경 요청이 오면 이슈를 먼저 만든다.
2. 분기 이름은 `<종류>/<이슈번호>` 다. 종류는 `feat` · `fix` · `refactor` · `test` · `docs` · `chore`.
3. `main` 에 직접 커밋하지 않는다. **훅이 막는다** (`.claude/hooks/guard-git.sh`).
4. 커밋 · 푸시 · PR 은 사용자가 요청할 때만 한다.

## 실행은 스크립트로만

사람과 에이전트가 같은 명령을 쓴다. 도구를 직접 부르지 않는다.

| 하는 일 | 명령 |
|---|---|
| 전체 검사 (CI 와 같다) | `scripts/check.sh` |
| 서버 테스트 | `scripts/test.sh` |
| 평가 세트 실행 | `scripts/eval.sh [모델 ...]` |
| 개발 서버 | `scripts/dev.sh` |

## 저장소 지도

| 뜻 | 자리 |
|---|---|
| 요구사항 (모든 설계의 근거) | `docs/requirements.md` |
| 아키텍처 · 기술 선택 근거 | `docs/architecture.md` |
| 질의 도메인 설계 (규칙 ID · 테스트 사항) | `docs/design/query.md` |
| 데이터 설계 | `docs/design/data.md` |
| 평가 방법과 모델 선정 결과 | `docs/eval/README.md` |
| AI 에이전트 작업 체계 | `docs/agentic-workflow.md` |
| 경로별 규칙 | `.claude/rules/` |
| 스킬 | `.claude/skills/` — `design` · `implement` · `eval` |
| 감사 워크플로우 | `.claude/workflows/audit.js` |
| 훅 | `.claude/settings.json` · `.claude/hooks/` |

## 언어

문서 · 주석 · 커밋 메시지는 한국어로 쓴다. 커밋 메시지는 `<종류>: <설명>` 이다. 협업자(`Co-Authored-By` 등) 문구를 쓰지 않는다.
