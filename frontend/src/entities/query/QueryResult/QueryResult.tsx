import type { Cell } from "@/api/types/query";

import styles from "./QueryResult.module.css";

// 천 단위 구분만 넣는다. 반올림하지 않는다 — 숫자는 DB 가 낸 그대로 보인다 (NFR-002).
const number = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 20 });

/** 칸 하나를 글로 옮긴다. 표시용 계산이라 엔티티 안에 둔다 (코드 아키텍처 6.2). */
export const formatCell = (value: Cell): string => {
  if (value === null) return "—";
  if (typeof value === "number") return number.format(value);
  return value;
};

interface Props {
  columns: string[];
  rows: Cell[][];
  truncated: boolean;
}

/** 실행 결과. 숫자를 가공하지 않는다 (NFR-002). */
export const QueryResult = ({ columns, rows, truncated }: Props) => {
  if (rows.length === 0) return <p className={styles.empty}>조건에 맞는 데이터가 없습니다.</p>;
  return (
    <div className={styles.wrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, c) => (
                <td key={c} className={typeof cell === "number" ? styles.number : undefined}>
                  {formatCell(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {truncated && (
        <p className={styles.note}>행 상한에 걸려 앞부분만 보여 줍니다. 질문을 더 좁혀 보세요.</p>
      )}
    </div>
  );
};
