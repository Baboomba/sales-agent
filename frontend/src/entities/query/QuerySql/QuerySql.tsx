import styles from "./QuerySql.module.css";

interface Props {
  sql: string;
}

/** 만든 SQL 또는 실행한 SQL 글 (FR-002). */
export const QuerySql = ({ sql }: Props) => <pre className={styles.sql}>{sql}</pre>;
