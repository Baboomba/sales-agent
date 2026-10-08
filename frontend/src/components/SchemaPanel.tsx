import type { SchemaTable } from "../api/types";
import styles from "./SchemaPanel.module.css";

/** 어떤 표와 열에 물어볼 수 있는지 (FR-006). */
export function SchemaPanel({ tables }: { tables: SchemaTable[] }) {
  return (
    <div className={styles.panel}>
      {tables.map((table) => (
        <details key={table.name} className={styles.table}>
          <summary>
            <code>{table.name}</code> {table.description}
          </summary>
          <ul>
            {table.columns.map((column) => (
              <li key={column.name}>
                <code>{column.name}</code>
                {column.description && <span> {column.description}</span>}
              </li>
            ))}
          </ul>
        </details>
      ))}
    </div>
  );
}
