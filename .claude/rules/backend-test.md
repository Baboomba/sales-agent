---
paths:
  - "backend/tests/**"
---

# 서버 테스트 규칙

## 층

| 층 | 자리 | 무엇을 | 모델 · DB |
|---|---|---|---|
| 단위 | `tests/unit/` | `rules` · `prompt` 순수 함수 | 없음 |
| 그래프 | `tests/unit/test_graph.py` | 재생성 루프 · 이벤트 | 가짜 생성기 · 가짜 DB |
| API | `tests/unit/test_api.py` | 입력 검증 · SSE 순서 | 가짜 생성기 · 가짜 DB |
| 통합 | `tests/integration/` | 읽기 전용 · 제한 시간 | 실제 SQLite (`@pytest.mark.integration`) |

**언어 모델을 부르는 테스트를 쓰지 않는다.** 모델 품질은 테스트가 아니라 평가 세트(`eval` 스킬)가 잰다. CI 에 모델 서버가 없다(NFR-005).

## 작성

* 테스트 이름이나 문서 문자열에 규칙 ID 를 적는다. `test_rule_coverage.py` 가 센다.
* 가짜 생성기는 미리 정한 출력을 차례로 돌려주고, 받은 프롬프트를 기록한다. 호출 횟수와 프롬프트 내용으로 검증한다.
* 하나의 테스트는 하나의 사실을 확인한다. 어떤 값이 와도 통과하는 단언(`assert result`)을 쓰지 않는다.
* 고정값에 실제 규칙 ID 를 쓰지 않는다. 커버리지 검사가 그것을 「덮였다」로 센다. 가짜 ID 는 `ZZZ-R999` 처럼 쓴다.
