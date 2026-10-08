import type { QueryEvent } from "@/api/types/query";

import {
  attemptSummary,
  doneEvent,
  isAbort,
  latestSql,
  questionToSend,
  sqlHeading,
} from "@/features/AskQuery/service";

const GENERATED_1: QueryEvent = { type: "generated", attempt: 1, sql: "zzz sql 1" };
const REJECTED_1: QueryEvent = {
  type: "rejected",
  attempt: 1,
  stage: "validate",
  reason: "zzz 사유",
};
const GENERATED_2: QueryEvent = { type: "generated", attempt: 2, sql: "zzz sql 2" };
const VALIDATED_2: QueryEvent = { type: "validated", sql: "zzz sql 2 LIMIT 201" };
const DONE: QueryEvent = { type: "done", columns: ["zzz_a"], rows: [[1]], truncated: false };

describe("questionToSend", () => {
  it("앞뒤 공백을 떼고 보낸다", () => {
    expect(questionToSend("  zzz 매출  ")).toBe("zzz 매출");
  });

  it("공백뿐이면 보내지 않는다 — 위의 짝", () => {
    expect(questionToSend("   ")).toBeNull();
    expect(questionToSend("")).toBeNull();
  });
});

describe("latestSql", () => {
  it("가장 나중의 SQL 이벤트를 고른다 — 재생성 뒤 검증까지 갔으면 검증된 SQL", () => {
    expect(latestSql([GENERATED_1, REJECTED_1, GENERATED_2, VALIDATED_2, DONE])).toEqual(
      VALIDATED_2,
    );
  });

  it("실행에서 실패해 다시 만들었으면, 앞서 검증된 SQL 이 아니라 새로 만든 SQL", () => {
    const validated1: QueryEvent = { type: "validated", sql: "zzz sql 1 LIMIT 201" };
    const executeFailed: QueryEvent = {
      type: "rejected",
      attempt: 1,
      stage: "execute",
      reason: "zzz 실행 실패",
    };
    expect(latestSql([GENERATED_1, validated1, executeFailed, GENERATED_2])).toEqual(GENERATED_2);
  });

  it("검증 전이면 가장 나중에 만든 SQL", () => {
    expect(latestSql([GENERATED_1, REJECTED_1, GENERATED_2])).toEqual(GENERATED_2);
  });

  it("SQL 이벤트가 없으면 null", () => {
    expect(latestSql([{ type: "failed", reason: "zzz" }])).toBeNull();
  });
});

describe("sqlHeading", () => {
  it("검증된 SQL 은 실행한 SQL, 만든 것은 만든 SQL", () => {
    expect(sqlHeading(VALIDATED_2)).toBe("실행한 SQL");
    expect(sqlHeading(GENERATED_1)).toBe("만든 SQL");
  });
});

describe("doneEvent", () => {
  it("완료 이벤트를 고른다", () => {
    expect(doneEvent([GENERATED_1, VALIDATED_2, DONE])).toEqual(DONE);
  });

  it("완료가 없으면 null — 위의 짝", () => {
    expect(doneEvent([GENERATED_1, REJECTED_1])).toBeNull();
  });
});

describe("isAbort", () => {
  it("사용자가 멈춘 오류만 가른다", () => {
    expect(isAbort(new DOMException("zzz", "AbortError"))).toBe(true);
    expect(isAbort(new DOMException("zzz", "NetworkError"))).toBe(false);
    expect(isAbort(new TypeError("zzz"))).toBe(false);
  });
});

describe("attemptSummary", () => {
  it("시도 번호 · 다시 만든 수 · 행 수를 센다 (SCR-R008)", () => {
    expect(attemptSummary([GENERATED_1, REJECTED_1, GENERATED_2, VALIDATED_2, DONE])).toEqual({
      attempts: 2,
      retries: 1,
      rows: 1,
    });
  });

  it("시도 번호는 가장 큰 값이고, 끝나지 않았으면 행 수가 없다 — 위의 짝 (SCR-R008)", () => {
    expect(attemptSummary([GENERATED_2, REJECTED_1])).toEqual({
      attempts: 2,
      retries: 1,
      rows: null,
    });
    expect(attemptSummary([])).toEqual({ attempts: 0, retries: 0, rows: null });
  });
});
