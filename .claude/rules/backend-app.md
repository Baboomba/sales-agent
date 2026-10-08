---
paths:
  - "backend/app/query/**"
---

# 질의 도메인 규칙

근거: `docs/architecture.md` 2절 · `docs/design/query.md`

## 계층

| 파일 | 할 수 있는 것 | 할 수 없는 것 |
|---|---|---|
| `model.py` | 데이터 형태 정의 | 다른 모듈 import |
| `rules.py` · `prompt.py` | 순수 함수. 입력 → 출력 | 파일 · 네트워크 · 시각 · 난수 · 프레임워크 import |
| `ports.py` | Protocol 과 포트가 던지는 예외 | 구현 |
| `graph.py` | 포트를 받아 그래프 조립 | 어댑터 · `langchain_ollama` import |
| `api.py` | HTTP ↔ 그래프 이벤트 변환 | 규칙 판단 (판단은 `rules.py` 에) |
| `adapters/` | 포트 구현. 외부 효과는 여기서만 | 규칙 판단 |

경계는 `import-linter` 가 검사한다. 위반하면 `scripts/check.sh` 가 실패한다.

## 규칙을 코드에 둘 때

* 설계서의 규칙 ID 를 함수 문서 문자열에 적는다. 예: `"""QRY-R005 바깥 LIMIT 을 보정한다."""`
* 한도 · 상한 같은 수는 하드코딩하지 않고 `config.py` 에서 받는다.
* **판정은 모델에게 맡기지 않는다.** SQL 이 안전한지, 결과가 맞는지는 규칙이 정한다.

## 모델 출력을 다룰 때

* 생성기는 날 문자열만 돌려준다. 해석은 `rules.parse_generation` 한 곳에서 한다.
* 모델 출력은 신뢰하지 않는 입력이다. 검증 전에는 실행하지 않는다.
