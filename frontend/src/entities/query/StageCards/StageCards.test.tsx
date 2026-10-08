import { render, screen, within } from "@testing-library/react";

import type { QueryEvent } from "@/api/types/query";

import { StageCards, attemptText, stageStatuses } from "./StageCards";

const GENERATED_1: QueryEvent = { type: "generated", attempt: 1, sql: "zzz sql 1" };
const REJECTED_1: QueryEvent = { type: "rejected", attempt: 1, stage: "validate", reason: "zzz" };
const GENERATED_2: QueryEvent = { type: "generated", attempt: 2, sql: "zzz sql 2" };
const VALIDATED: QueryEvent = { type: "validated", sql: "zzz sql 2 LIMIT 201" };
const DONE: QueryEvent = { type: "done", columns: ["zzz_a"], rows: [[1], [2]], truncated: false };
const FAILED: QueryEvent = { type: "failed", reason: "zzz 사유" };

describe("stageStatuses", () => {
  it("묻기 전에는 셋 다 대기 (SCR-R007)", () => {
    expect(stageStatuses([], false)).toEqual({
      generate: "wait",
      validate: "wait",
      execute: "wait",
    });
  });

  it("늦은 응답에는 다다른 단계가 진행 중이다 — 위의 짝 (SCR-R007)", () => {
    expect(stageStatuses([], true).generate).toBe("run");
    expect(stageStatuses([GENERATED_1], true)).toEqual({
      generate: "done",
      validate: "run",
      execute: "wait",
    });
  });

  it("다시 만들면 거부 뒤의 시도만 본다 — 검증에서 거부되면 생성부터 다시 (SCR-R007)", () => {
    expect(stageStatuses([GENERATED_1, REJECTED_1], true)).toEqual({
      generate: "run",
      validate: "wait",
      execute: "wait",
    });
  });

  it("여러 번 거부되면 마지막 거부 뒤의 시도만 본다 (SCR-R007)", () => {
    const rejected2: QueryEvent = { type: "rejected", attempt: 2, stage: "execute", reason: "zzz" };
    expect(
      stageStatuses([GENERATED_1, REJECTED_1, GENERATED_2, VALIDATED, rejected2], true),
    ).toEqual({
      generate: "run",
      validate: "wait",
      execute: "wait",
    });
  });

  it("완료면 셋 다 완료 (SCR-R007)", () => {
    expect(stageStatuses([GENERATED_1, REJECTED_1, GENERATED_2, VALIDATED, DONE], false)).toEqual({
      generate: "done",
      validate: "done",
      execute: "done",
    });
  });

  it("끝내 실패하면 지금 시도가 다다른 단계에 실패를 보인다 (SCR-R007)", () => {
    expect(stageStatuses([FAILED], false).generate).toBe("fail");
    expect(stageStatuses([GENERATED_1, FAILED], false)).toEqual({
      generate: "done",
      validate: "fail",
      execute: "wait",
    });
  });
});

describe("attemptText", () => {
  it("시도 번호와 다시 만든 횟수를 적는다 (SCR-R007)", () => {
    expect(attemptText(2, 1)).toBe("시도 2 · 1번 다시 만듦");
  });

  it("다시 만든 적이 없으면 시도 번호만, 시도가 없으면 비운다 — 위의 짝 (SCR-R007)", () => {
    expect(attemptText(1, 0)).toBe("시도 1");
    expect(attemptText(0, 0)).toBe("");
  });
});

describe("StageCards", () => {
  it("세 칸에 상태와 덧말을 보인다 (SCR-R007)", () => {
    render(
      <StageCards
        events={[GENERATED_1, REJECTED_1, GENERATED_2, VALIDATED, DONE]}
        pending={false}
        summary={{ attempts: 2, retries: 1, rows: 2 }}
      />,
    );
    const cards = within(screen.getByRole("list", { name: "진행 단계" })).getAllByRole("listitem");

    expect(cards.map((card) => card.dataset.status)).toEqual(["done", "done", "done"]);
    expect(cards[0]).toHaveTextContent("시도 2 · 1번 다시 만듦");
    expect(cards[2]).toHaveTextContent("완료 · 2행");
  });

  it("생성에서 끝내 실패하면 생성 칸에 시도 대신 실패를 적는다 (SCR-R007)", () => {
    render(
      <StageCards
        events={[GENERATED_1, REJECTED_1, FAILED]}
        pending={false}
        summary={{ attempts: 1, retries: 1, rows: null }}
      />,
    );
    const cards = within(screen.getByRole("list", { name: "진행 단계" })).getAllByRole("listitem");

    expect(cards[0]?.dataset.status).toBe("fail");
    expect(cards[0]).toHaveTextContent("실패");
    expect(cards[0]).not.toHaveTextContent("시도");
  });
});
