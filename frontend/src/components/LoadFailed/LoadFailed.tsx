import styles from "./LoadFailed.module.css";

interface Props {
  onRetry: () => void;
  className?: string;
}

/** 불러오지 못했다는 안내와 다시 시도 단추. 무엇을 불러오는지는 모른다. */
export const LoadFailed = ({ onRetry, className }: Props) => (
  <div className={[styles.failed, className].filter(Boolean).join(" ")} role="status">
    <span>불러오지 못했습니다</span>
    <button type="button" className={styles.retry} onClick={onRetry}>
      다시 시도
    </button>
  </div>
);
