import { LoadFailed } from "@/components/LoadFailed";

import styles from "./ModelStatus.module.css";
import { useModelName } from "./hooks";

/** 상단바의 모델 이름 (SCR-R014). */
export const ModelStatus = () => {
  const { state, retry } = useModelName();
  if (state.status === "failed") return <LoadFailed onRetry={retry} />;
  return (
    <span className={styles.status}>
      <span className={styles.dot} aria-hidden="true" />
      {state.status === "ok" ? `모델 ${state.value}` : "모델 확인 중"}
    </span>
  );
};
