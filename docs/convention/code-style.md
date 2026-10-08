# 코드 컨벤션

코드를 어떻게 쓰는지의 정본이다. 코드를 어떻게 나누는지는 [코드 아키텍처](code-architecture.md)가, 테스트는 [테스트 규칙](testing.md)(#38 에서 만든다)이 갖는다.

**포맷과 린트는 도구가 정한다.** 사람이 맞추지 않는다. 아래 표의 도구가 통과하면 포맷 · 린트는 맞는 것이다. 이 문서는 도구가 잡지 못하는 것을 적는다.

| | 서버 | 화면 |
|---|---|---|
| 포맷 | `ruff format` (줄 100자) | Prettier (줄 100자) |
| 린트 | `ruff check` — `E` · `F` · `W` · `I` · `B` · `UP` · `SIM` · `RUF` | ESLint — `typescript-eslint` strict · `jsx-a11y` · `react-hooks` |
| 타입 | `mypy --strict` | TypeScript `strict` · `noUncheckedIndexedAccess` |
| 설정 | `backend/pyproject.toml` | `frontend/eslint.config.js` · `tsconfig.json` · `.prettierrc.json` |

전부 `scripts/check.sh` 가 돌린다. 고친 파일은 Claude Code 훅(`.claude/hooks/format.sh`)이 바로 포맷하고, 커밋할 때 git 훅(`.githooks/pre-commit`)이 한 번 더 본다.

## 1. 공통

### 1.1 우회하지 않는다

* 타입 · 린트 검사를 끄지 않는다: `# type: ignore` · `# noqa` · `any` · `@ts-ignore` · `eslint-disable` 를 넣지 않는다.
* 검사를 통과하려고 구조를 비틀지 않는다 — 계층 경계를 피하려고 import 를 함수 안으로 숨기는 것 등.

### 1.2 이름

* 이름은 영어로, 뜻이 드러나게 짓는다. 줄임말을 쓰지 않는다 (`sql` · `id` 처럼 굳어진 것은 쓴다).
* 업무 용어는 설계서의 용어와 한 단어씩 맞춘다: 생성 `generate`, 검증 `validate`, 실행 `execute`, 재생성의 사유 `feedback`, 실패 사유 `reason`, 시도 `attempt`.

### 1.3 주석 · 문서 문자열

* 한국어로 쓴다. **"무엇을" 이 아니라 "왜" 를 쓴다.** 코드로 읽히는 것은 쓰지 않는다.
* 규칙을 구현한 함수는 첫 줄에 설계서의 규칙 ID 를 적는다.

  ```python
  def check_question(question: str) -> str | None:
      """QRY-R001 질문이 받을 수 있는 모양인지 본다. 문제가 있으면 사유, 없으면 None."""
  ```

* 비틀어 보이는 선택에는 이유를 남긴다 — 예: `# ParseError 만 잡으면 TokenError(닫히지 않은 따옴표 등)가 그래프 밖으로 샌다.`
* 감사 · 평가에서 나온 결정은 이슈 번호나 문서를 가리킨다 — 예: `(#19)`, `(docs/eval/README.md)`.

### 1.4 사용자에게 보이는 문구

* 실패 사유 · 안내는 한국어 문장으로, **무엇을 하면 되는지**가 드러나게 쓴다.
  * 나쁨: `connection error`
  * 좋음: `모델 서버에 연결할 수 없습니다. Ollama 가 떠 있는지 확인하세요.`
* 재생성 사유는 다음 프롬프트에 그대로 붙는다. 모델이 고칠 곳을 찾을 수 있게 구체적으로 쓴다 (`QRY-R015`).

### 1.5 수와 상수

* 상한 · 제한 시간 · 횟수는 코드에 박지 않는다. 설정(`config.Settings`)으로 받는다 — [코드 아키텍처](code-architecture.md) 5절.
* 바뀌지 않는 값(정규식 · 금지 구문 목록 · 문구)은 모듈 위쪽에 대문자 상수로 둔다. 정규식은 모듈을 읽을 때 한 번 컴파일한다.

## 2. 서버 (Python 3.13)

* **모든 모듈 첫 줄에 `from __future__ import annotations`.**
* **모든 함수에 타입을 단다.** 반환이 없으면 `-> None`. `object` 는 정말 아무 값이나 받을 때만 쓴다(`sanitize_value`).
* **값 객체는 `@dataclass(frozen=True)`.** 상태와 이벤트, 설정이 그렇다. 그래프 상태처럼 일부만 갱신하는 딕셔너리는 `TypedDict(total=False)`.
* **인터페이스는 `typing.Protocol`.** 구현이 상속하지 않아도 된다(구조적 타입).
* **헷갈릴 수 있는 인자는 키워드로만 받는다** — `validate_sql(sql, *, allowed_tables, row_limit)`.
* **모듈 안에서만 쓰는 것은 `_` 로 시작한다** — `_single_statement` · `_route_to`. 다른 모듈에서 부르지 않는다.
* **예외는 도메인 예외로 옮긴다.** 바깥 라이브러리의 예외를 잡아 `raise 도메인예외(...) from error` 로 원인을 이어 둔다. 사유가 필요한 예외는 `reason` 속성을 갖는다.
* **넓은 `except Exception` 은 안전망 한 곳에만 둔다** — 유스케이스의 입구 ([코드 아키텍처](code-architecture.md) 4절). 그 밖에서는 잡을 예외를 좁혀 쓴다.
* **모델은 메서드 없는 `@dataclass(frozen=True)`** 다. 판단 · 계산을 모델에 두지 않는다 ([코드 아키텍처](code-architecture.md) 2.1).
* **로그는 `logging.getLogger(__name__)`.** 버그로 보는 실패만 `logger.exception` 으로 남긴다. `print` 는 스크립트(`scripts/` · `evaluation/`)에서만 쓴다.

## 3. 화면 (TypeScript · React)

계층 · 묶음 · 파일을 어떻게 나누는지는 [코드 아키텍처](code-architecture.md) 6절이 갖는다.

* **함수는 `function` 선언으로 쓴다.** 컴포넌트도 같다 (`export function App()`).
* **이름 있는 내보내기만 쓴다.** 묶음은 `index.ts` 로 내보낸다. `export default` 는 도구 설정 파일(`vite.config.ts` · `eslint.config.js`)과 CSS Modules 타입 선언에만 쓴다.
* **`as` 단언은 바깥에서 들어온 JSON 의 경계(`api/`)에서만 쓴다.** 그 밖에서는 타입을 좁혀 쓴다.
* **props 타입은 컴포넌트 옆에 `interface Props`** 로 둔다. 서버 타입은 `api/types/` 에서만 가져온다.
* **판별 유니온은 `switch` 로 끝까지 다룬다.** 새 이벤트가 생기면 타입 검사가 빠진 자리를 알려 준다.
* **제 폴더 밖은 `@/` 로 가리킨다.** `../` 로 올라가지 않는다.
* **스타일은 CSS Modules.** 묶음마다 `<묶음>.module.css`, 색 · 간격은 `index.css` 의 변수(`--accent` 등)만 쓴다. 인라인 스타일을 쓰지 않는다.
* **접근성은 린트가 지킨다** (`jsx-a11y`). 입력에는 `label`, 실패 알림에는 `role="alert"`.

## 4. 바꿀 때

* 도구 설정을 바꾸면 이 문서의 표를 함께 고친다.
