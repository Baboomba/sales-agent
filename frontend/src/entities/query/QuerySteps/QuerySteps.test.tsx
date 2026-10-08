import { render, screen } from "@testing-library/react";

import type { QueryEvent } from "@/api/types/query";

import { QuerySteps } from "./QuerySteps";

describe("QuerySteps", () => {
  it("재생성 사유를 시도 번호와 함께 보여 준다 (FR-002 · FR-004)", () => {
    const events: QueryEvent[] = [
      { type: "generated", attempt: 1, sql: "DELETE FROM orders" },
      {
        type: "rejected",
        attempt: 1,
        stage: "validate",
        reason: "조회(SELECT) 문만 실행할 수 있습니다.",
      },
      { type: "generated", attempt: 2, sql: "SELECT 1" },
    ];
    render(<QuerySteps events={events} running />);
    expect(screen.getByText("조회(SELECT) 문만 실행할 수 있습니다.")).toBeInTheDocument();
    expect(screen.getAllByText(/시도 2/)).not.toHaveLength(0);
  });

  it("실패 사유를 알린다 (FR-005)", () => {
    render(
      <QuerySteps
        events={[{ type: "failed", reason: "모델 서버에 연결할 수 없습니다." }]}
        running={false}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("모델 서버에 연결할 수 없습니다.");
  });
});
