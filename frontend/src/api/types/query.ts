// 서버 이벤트와 응답의 모양. 이름은 docs/design/query.md 2.2 · 2.4 와 같다.

import type { Stage } from "@/common/values";

export type Cell = string | number | null;

export type QueryEvent =
  | { type: "generated"; attempt: number; sql: string }
  | { type: "rejected"; attempt: number; stage: Stage; reason: string }
  | { type: "validated"; sql: string }
  | { type: "done"; columns: string[]; rows: Cell[][]; truncated: boolean }
  | { type: "failed"; reason: string };

export interface SchemaColumn {
  name: string;
  type: string;
  description: string;
}

export interface SchemaTable {
  name: string;
  description: string;
  columns: SchemaColumn[];
}
