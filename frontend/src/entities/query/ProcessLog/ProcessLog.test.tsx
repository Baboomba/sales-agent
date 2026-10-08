import { render, screen, within } from "@testing-library/react";

import type { QueryEvent } from "@/api/types/query";

import { ProcessLog } from "./ProcessLog";

const GENERATED_1: QueryEvent = { type: "generated", attempt: 1, sql: "zzz sql 1" };
const REJECTED_1: QueryEvent = {
  type: "rejected",
  attempt: 1,
  stage: "validate",
  reason: "zzz 거부 사유",
};
const GENERATED_2: QueryEvent = { type: "generated", attempt: 2, sql: "zzz sql 2" };
const VALIDATED: QueryEvent = { type: "validated", sql: "zzz sql 2 LIMIT 201" };
const DONE: QueryEvent = {
  type: "done",
  columns: ["zzz_a"],
  rows: [[1], [2], [3]],
  truncated: false,
};

const NONE = { attempts: 0, retries: 0, rows: null };

describe("ProcessLog", () => {
  it("받은 순서대로 쌓고, 거부됨에는 실패한 단계와 사유가 있다 (SCR-R008)", () => {
    render(
      <ProcessLog
        events={[GENERATED_1, REJECTED_1, GENERATED_2, VALIDATED, DONE]}
        pending={false}
        summary={NONE}
      />,
    );
    const entries = within(screen.getByRole("list", { name: "처리 기록" })).getAllByRole(
      "listitem",
    );

    expect(entries.map((entry) => entry.textContent)).toEqual([
      expect.stringContaining("생성시도 1"),
      expect.stringContaining("검증 실패시도 1"),
      expect.stringContaining("생성시도 2"),
      expect.stringContaining("검증 통과"),
      expect.stringContaining("실행 완료3행"),
    ]);
    expect(entries[1]).toHaveTextContent("zzz 거부 사유");
  });

  it("거부됨은 실패한 단계 이름을 그대로 보인다 (SCR-R008)", () => {
    render(
      <ProcessLog
        events={[
          { type: "rejected", attempt: 1, stage: "generate", reason: "zzz" },
          { type: "rejected", attempt: 2, stage: "execute", reason: "zzz" },
        ]}
        pending={false}
        summary={NONE}
      />,
    );
    const entries = screen.getAllByRole("listitem");

    expect(entries[0]).toHaveTextContent("생성 실패");
    expect(entries[1]).toHaveTextContent("실행 실패");
  });

  it("맨 위 요약에 시도 · 다시 만듦 · 행 수를 보인다 (SCR-R008)", () => {
    render(
      <ProcessLog
        events={[GENERATED_1, REJECTED_1, GENERATED_2, VALIDATED, DONE]}
        pending={false}
        summary={{ attempts: 2, retries: 1, rows: 1234 }}
      />,
    );
    const value = (label: string) => screen.getByText(label).nextSibling?.textContent;

    expect([value("시도"), value("다시 만듦"), value("행")]).toEqual(["2", "1", "1,234"]);
  });

  it("끝나지 않았으면 행 수 자리에 줄표를 둔다 — 위의 짝 (SCR-R008)", () => {
    render(
      <ProcessLog
        events={[GENERATED_1]}
        pending={false}
        summary={{ attempts: 1, retries: 0, rows: null }}
      />,
    );
    expect(screen.getByText("행").nextSibling?.textContent).toBe("—");
  });

  it("묻기 전에는 비어 있다고 안내하고, 늦은 응답에는 진행 중을 덧붙인다", () => {
    const { rerender } = render(<ProcessLog events={[]} pending={false} summary={NONE} />);
    expect(screen.getByText("질문하면 처리 기록이 여기에 쌓입니다.")).toBeInTheDocument();

    rerender(<ProcessLog events={[GENERATED_1]} pending summary={NONE} />);
    expect(screen.getAllByRole("listitem").at(-1)).toHaveTextContent("진행 중…");
  });

  it("단계가 없어도 늦은 응답이면 빈 안내 대신 진행 중을 보인다 — 위의 짝", () => {
    render(<ProcessLog events={[]} pending summary={NONE} />);
    expect(screen.queryByText("질문하면 처리 기록이 여기에 쌓입니다.")).not.toBeInTheDocument();
    expect(screen.getByRole("listitem")).toHaveTextContent("진행 중…");
  });

  it("실패하면 기록 끝에 사유를 남긴다 (SCR-R010)", () => {
    render(
      <ProcessLog
        events={[GENERATED_1, { type: "failed", reason: "zzz 끝 사유" }]}
        pending={false}
        summary={NONE}
      />,
    );
    expect(screen.getAllByRole("listitem").at(-1)).toHaveTextContent("zzz 끝 사유");
  });
});
