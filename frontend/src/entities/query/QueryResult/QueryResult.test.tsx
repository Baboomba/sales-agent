import { render, screen } from "@testing-library/react";

import { QueryResult, barColumn, formatCell } from "./QueryResult";

describe("formatCell", () => {
  it("정수에 천 단위 구분만 넣는다 (SCR-R011)", () => {
    expect(formatCell(2106638050)).toBe("2,106,638,050");
  });

  it("소수를 반올림하지 않는다 (SCR-R011)", () => {
    expect(formatCell(12389.000593974395)).toBe("12,389.000593974395");
  });

  it("문자열은 그대로, 빈 값은 줄표", () => {
    expect(formatCell("강남점")).toBe("강남점");
    expect(formatCell(null)).toBe("—");
  });
});

describe("barColumn", () => {
  it("숫자 열이 하나뿐이고 모두 0 이상이면 그 열과 최댓값 (SCR-R012)", () => {
    expect(
      barColumn([
        ["zzz 서울", 300],
        ["zzz 부산", 100],
      ]),
    ).toEqual({ index: 1, max: 300 });
  });

  it("최댓값이 어느 행에 있든 찾고, 0 도 0 이상에 든다 (SCR-R012)", () => {
    expect(
      barColumn([
        ["zzz", 100],
        ["zzz", 300],
        ["zzz", 50],
      ]),
    ).toEqual({ index: 1, max: 300 });
    expect(
      barColumn([
        ["zzz", 0],
        ["zzz", 5],
      ]),
    ).toEqual({ index: 1, max: 5 });
  });

  it("빈 값만 있는 열은 숫자 열로 치지 않고, 빈 값이 섞인 숫자 열은 숫자 열이다 (SCR-R012)", () => {
    expect(
      barColumn([
        [null, 3],
        [null, null],
      ]),
    ).toEqual({ index: 1, max: 3 });
  });

  it("숫자 열이 둘이거나 음수가 있으면 그리지 않는다 — 위의 짝 (SCR-R012)", () => {
    expect(barColumn([["zzz", 1, 2]])).toBeNull();
    expect(
      barColumn([
        ["zzz", 5],
        ["zzz", -1],
      ]),
    ).toBeNull();
    expect(barColumn([["zzz"]])).toBeNull();
  });
});

describe("QueryResult", () => {
  it("행이 없으면 표 대신 데이터가 없다고 알린다 (SCR-R011)", () => {
    render(<QueryResult columns={["zzz_a"]} rows={[]} truncated={false} />);
    expect(screen.getByText("조건에 맞는 데이터가 없습니다.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("행이 있으면 열 이름과 값, DB 순서의 행 번호를 보인다 — 위의 짝 (SCR-R011)", () => {
    render(
      <QueryResult
        columns={["zzz_a", "zzz_b"]}
        rows={[
          ["zzz 값", 1234],
          ["zzz 둘째", 5],
        ]}
        truncated={false}
      />,
    );
    expect(screen.getByRole("columnheader", { name: "zzz_b" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "zzz 값" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "1,234" })).toBeInTheDocument();
    expect(
      screen
        .getAllByRole("row")
        .slice(1)
        .map((row) => row.firstChild?.textContent),
    ).toEqual(["1", "2"]);
  });

  it("행을 다시 늘어놓지 않고 DB 가 낸 순서대로 보인다 (SCR-R011)", () => {
    render(
      <QueryResult
        columns={["zzz_a", "zzz_b"]}
        rows={[
          ["zzz a", 5],
          ["zzz b", 1234],
          ["zzz c", 30],
        ]}
        truncated={false}
      />,
    );
    const rows = screen.getAllByRole("row").slice(1);

    expect(rows.map((row) => row.lastChild?.textContent)).toEqual(["5", "1,234", "30"]);
  });

  it("잘린 결과면 앞부분만 보인다고 알리고, 잘리지 않았으면 알리지 않는다 (SCR-R011)", () => {
    const { rerender } = render(<QueryResult columns={["zzz_a"]} rows={[[1]]} truncated />);
    expect(screen.getByText(/앞부분만 보여 줍니다/)).toBeInTheDocument();
    rerender(<QueryResult columns={["zzz_a"]} rows={[[1]]} truncated={false} />);
    expect(screen.queryByText(/앞부분만 보여 줍니다/)).not.toBeInTheDocument();
  });

  it("막대는 최댓값에 견준 길이로 그리고, 숫자는 그대로 둔다 (SCR-R012)", () => {
    render(
      <QueryResult
        columns={["zzz_a", "zzz_b"]}
        rows={[
          ["zzz 1", 200],
          ["zzz 2", 50],
        ]}
        truncated={false}
      />,
    );
    const bars = screen.getAllByTestId("bar");

    expect(bars.map((bar) => bar.querySelector("rect")?.getAttribute("width"))).toEqual([
      "100%",
      "25%",
    ]);
    expect(screen.getByRole("cell", { name: "200" })).toBeInTheDocument();
  });

  it("값이 모두 0 이면 막대는 비어 있다 (SCR-R012)", () => {
    render(<QueryResult columns={["zzz_a", "zzz_b"]} rows={[["zzz", 0]]} truncated={false} />);
    expect(screen.getByTestId("bar").querySelector("rect")?.getAttribute("width")).toBe("0%");
  });

  it("숫자 열이 둘이면 막대를 그리지 않는다 — 위의 짝 (SCR-R012)", () => {
    render(<QueryResult columns={["zzz_a", "zzz_b"]} rows={[[1, 2]]} truncated={false} />);
    expect(screen.queryByTestId("bar")).not.toBeInTheDocument();
  });
});
