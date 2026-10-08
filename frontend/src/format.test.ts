import { formatCell } from "./format";

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
