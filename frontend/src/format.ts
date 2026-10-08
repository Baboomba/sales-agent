import type { Cell } from "./api/types";

// 천 단위 구분만 넣는다. 반올림하지 않는다 — 숫자는 DB 가 낸 그대로 보인다 (NFR-002).
const number = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 20 });

export function formatCell(value: Cell): string {
  if (value === null) return "—";
  if (typeof value === "number") return number.format(value);
  return value;
}
