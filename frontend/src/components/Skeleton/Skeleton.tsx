import styles from "./Skeleton.module.css";

interface Props {
  rows: number;
  columns: number;
}

/** 표 모양의 뼈대. 무엇이 올지 모르고 자리만 잡는다. 그림이라 읽지 않는다. */
export const Skeleton = ({ rows, columns }: Props) => (
  <div className={styles.skeleton} data-testid="skeleton" aria-hidden="true">
    <Line columns={columns} head />
    {Array.from({ length: rows }, (_, r) => (
      <Line key={r} columns={columns} />
    ))}
  </div>
);

interface LineProps {
  columns: number;
  head?: boolean;
}

/** 뼈대 한 줄. 칸마다 폭이 조금씩 다르다(스타일 파일이 순서로 정한다). */
const Line = ({ columns, head = false }: LineProps) => (
  <div className={head ? `${styles.line} ${styles.head}` : styles.line}>
    {Array.from({ length: columns }, (_, c) => (
      <span key={c} className={styles.block} />
    ))}
  </div>
);
