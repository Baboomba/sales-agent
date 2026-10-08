import type { Cell } from "../api/types";
import { formatCell } from "../format";
import styles from "./ResultTable.module.css";

interface Props {
  columns: string[];
  rows: Cell[][];
  truncated: boolean;
}

/** 실행 결과. 숫자를 가공하지 않는다 (NFR-002). */
export function ResultTable({ columns, rows, truncated }: Props) {
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
}
