import { render, screen } from "@testing-library/react";

import { QueryResult, formatCell } from "./QueryResult";

describe("formatCell", () => {
  it("정수에 천 단위 구분만 넣는다", () => {
    expect(formatCell(2106638050)).toBe("2,106,638,050");
  });

  it("소수를 반올림하지 않는다 (NFR-002)", () => {
    expect(formatCell(12389.000593974395)).toBe("12,389.000593974395");
  });

  it("문자열과 빈 값", () => {
    expect(formatCell("강남점")).toBe("강남점");
    expect(formatCell(null)).toBe("—");
  });
});

describe("QueryResult", () => {
  it("행이 없으면 표 대신 데이터가 없다고 알린다", () => {
    render(<QueryResult columns={["zzz_a"]} rows={[]} truncated={false} />);
    expect(screen.getByText("조건에 맞는 데이터가 없습니다.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("행이 있으면 열 이름과 값을 표로 보인다 — 위 테스트의 짝", () => {
    render(
      <QueryResult columns={["zzz_a", "zzz_b"]} rows={[["zzz 값", 1234]]} truncated={false} />,
    );
    expect(screen.getByRole("columnheader", { name: "zzz_b" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "zzz 값" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "1,234" })).toBeInTheDocument();
  });

  it("잘린 결과면 앞부분만 보인다고 알리고, 잘리지 않았으면 알리지 않는다 (QRY-R005)", () => {
    const { rerender } = render(<QueryResult columns={["zzz_a"]} rows={[[1]]} truncated />);
    expect(screen.getByText(/앞부분만 보여 줍니다/)).toBeInTheDocument();
    rerender(<QueryResult columns={["zzz_a"]} rows={[[1]]} truncated={false} />);
    expect(screen.queryByText(/앞부분만 보여 줍니다/)).not.toBeInTheDocument();
  });
});
