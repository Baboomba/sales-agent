import type { SchemaTable } from "@/api/types/query";

import styles from "./SchemaTables.module.css";

interface Props {
  tables: SchemaTable[];
}

/** 어떤 표와 열에 물어볼 수 있는지. DB 순서대로, 처음에는 첫 표를 펼쳐 둔다 (FR-006 · SCR-R013). */
export const SchemaTables = ({ tables }: Props) => (
  <div className={styles.panel}>
    {tables.map((table, index) => (
      <details key={table.name} className={styles.table} open={index === 0}>
        <summary>
          <span className={styles.icon} aria-hidden="true">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
            >
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <path d="M3 10h18M9 10v10" />
            </svg>
          </span>
          <span>
            <span className={styles.name}>{table.name}</span>
            <span className={styles.desc}>{table.description}</span>
          </span>
        </summary>
        <ul className={styles.cols}>
          {table.columns.map((column) => (
            <li key={column.name}>
              <code>{column.name}</code>
              {column.description && <span>{column.description}</span>}
            </li>
          ))}
        </ul>
      </details>
    ))}
  </div>
);
