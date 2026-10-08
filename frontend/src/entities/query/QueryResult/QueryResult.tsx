import type { Cell } from "@/api/types/query";

import styles from "./QueryResult.module.css";

// 천 단위 구분만 넣는다. 반올림하지 않는다 — 숫자는 DB 가 낸 그대로 보인다 (NFR-002 · SCR-R011).
const number = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 20 });

/** 칸 하나를 글로 옮긴다. 표시용 계산이라 엔티티 안에 둔다 (코드 아키텍처 6.2). */
export const formatCell = (value: Cell): string => {
  if (value === null) return "—";
  if (typeof value === "number") return number.format(value);
  return value;
};

/** 막대를 그릴 열과 그 최댓값. */
interface Bar {
  index: number;
  max: number;
}

/** 열 하나의 빈 값이 아닌 칸. */
const filledCells = (rows: Cell[][], index: number): Cell[] =>
  rows.map((row) => row[index] ?? null).filter((cell) => cell !== null);

/** 숫자 열 = 빈 값이 아닌 칸이 하나 이상 있고, 모두 수인 열. */
const isNumberColumn = (rows: Cell[][], index: number): boolean => {
  const cells = filledCells(rows, index);
  return cells.length > 0 && cells.every((cell) => typeof cell === "number");
};

/**
 * 막대를 그릴 열과 그 최댓값 (SCR-R012). 숫자 열이 하나뿐이고 값이 모두 0 이상일 때만 그린다.
 * 막대는 그림일 뿐 숫자를 바꾸지 않는다.
 */
export const barColumn = (rows: Cell[][]): Bar | null => {
  const indexes = Array.from({ length: rows[0]?.length ?? 0 }, (_, c) => c);
  const numberColumns = indexes.filter((c) => isNumberColumn(rows, c));
  const [index] = numberColumns;
  if (numberColumns.length !== 1 || index === undefined) return null;
  const values = filledCells(rows, index).filter((cell) => typeof cell === "number");
  if (values.some((value) => value < 0)) return null;
  return { index, max: Math.max(...values) };
};

interface Props {
  columns: string[];
  rows: Cell[][];
  truncated: boolean;
}

/** 실행 결과. 행 번호는 DB 가 낸 순서다. 숫자를 가공하지 않는다 (NFR-002). */
export const QueryResult = ({ columns, rows, truncated }: Props) => {
  if (rows.length === 0) return <p className={styles.empty}>조건에 맞는 데이터가 없습니다.</p>;
  const bar = barColumn(rows);
  return (
    <div className={styles.wrap}>
      <table className={styles.table}>
        <thead>
          <HeadRow columns={columns} />
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <BodyRow key={r} rank={r + 1} row={row} bar={bar} />
          ))}
        </tbody>
      </table>
      {truncated && (
        <p className={styles.note}>행 상한에 걸려 앞부분만 보여 줍니다. 질문을 더 좁혀 보세요.</p>
      )}
    </div>
  );
};

interface HeadRowProps {
  columns: string[];
}

/** 머리 줄 — 행 번호 자리 + 열 이름. 열 이름은 겹칠 수 있어(예: count 둘) 자리로 key 를 삼는다. */
const HeadRow = ({ columns }: HeadRowProps) => (
  <tr>
    <th className={styles.rank}>
      <span className="sr-only">행</span>
    </th>
    {columns.map((column, c) => (
      <th key={c}>{column}</th>
    ))}
  </tr>
);

interface BodyRowProps {
  rank: number;
  row: Cell[];
  bar: Bar | null;
}

/** 행 하나 — 행 번호 + 값 칸. */
const BodyRow = ({ rank, row, bar }: BodyRowProps) => (
  <tr>
    <td className={styles.rank}>
      <span className={styles.rankMark}>{rank}</span>
    </td>
    {row.map((cell, c) => (
      <ValueCell key={c} cell={cell} max={bar?.index === c ? bar.max : null} />
    ))}
  </tr>
);

interface ValueCellProps {
  cell: Cell;
  /** 막대 열이면 그 열의 최댓값, 아니면 null. */
  max: number | null;
}

/** 값 칸. 숫자는 오른쪽에 두고, 막대 열이면 앞에 막대를 그린다. */
const ValueCell = ({ cell, max }: ValueCellProps) => {
  if (typeof cell !== "number") return <td>{formatCell(cell)}</td>;
  return (
    <td className={styles.number}>
      {max !== null && <BarMark ratio={max === 0 ? 0 : cell / max} />}
      {formatCell(cell)}
    </td>
  );
};

interface BarMarkProps {
  ratio: number;
}

/** 최댓값에 견준 막대. 그림이라 읽지 않는다. 길이는 데이터라 그림의 속성으로 준다(인라인 스타일을 쓰지 않는다). */
const BarMark = ({ ratio }: BarMarkProps) => (
  <svg className={styles.bar} data-testid="bar" aria-hidden="true">
    <rect width={`${Math.round(ratio * 100)}%`} height="100%" rx="3" />
  </svg>
);
