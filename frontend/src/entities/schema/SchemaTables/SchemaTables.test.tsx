import { render, screen } from "@testing-library/react";

import type { SchemaTable } from "@/api/types/query";

import { SchemaTables } from "./SchemaTables";

const TABLES: SchemaTable[] = [
  {
    name: "zzz_second",
    description: "zzz 둘째 설명",
    columns: [{ name: "zzz_col", type: "INTEGER", description: "zzz 열 설명" }],
  },
  { name: "zzz_first", description: "zzz 첫째 설명", columns: [] },
];

describe("SchemaTables", () => {
  it("받은 순서대로 표와 업무 설명 · 열 이름과 설명을 보이고, 첫 표만 펼친다 (SCR-R013)", () => {
    const { container } = render(<SchemaTables tables={TABLES} />);
    const details = [...container.querySelectorAll("details")];

    expect(details.map((d) => d.querySelector("summary")?.textContent)).toEqual([
      "zzz_secondzzz 둘째 설명",
      "zzz_firstzzz 첫째 설명",
    ]);
    expect(details.map((d) => d.open)).toEqual([true, false]);
    expect(screen.getByText("zzz_col")).toBeInTheDocument();
    expect(screen.getByText("zzz 열 설명")).toBeInTheDocument();
  });
});
