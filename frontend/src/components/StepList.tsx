import type { QueryEvent, Stage } from "../api/types";
import styles from "./StepList.module.css";

const STAGE_LABEL: Record<Stage, string> = {
  generate: "생성",
  validate: "검증",
  execute: "실행",
};

interface Props {
  events: QueryEvent[];
  running: boolean;
}

/** 생성 → 검증 → 실행 과정을 이벤트 순서대로 보여 준다 (FR-002 · FR-004 · FR-005). */
export function StepList({ events, running }: Props) {
  return (
    <ol className={styles.list}>
      {events.map((event, index) => (
        <li key={index} className={styles[event.type]}>
          <Step event={event} />
        </li>
      ))}
      {running && <li className={styles.pending}>진행 중…</li>}
    </ol>
  );
}

function Step({ event }: { event: QueryEvent }) {
  switch (event.type) {
    case "generated":
      return <span>시도 {event.attempt} · SQL 을 만들었습니다</span>;
    case "rejected":
      return (
        <span>
          시도 {event.attempt} · {STAGE_LABEL[event.stage]} 실패, 사유를 붙여 다시 만듭니다
          <span className={styles.reason}>{event.reason}</span>
        </span>
      );
    case "validated":
      return <span>검증 통과 · 조회문만 있고 행 상한이 적용됐습니다</span>;
    case "done":
      return <span>실행 완료 · {event.rows.length.toLocaleString("ko-KR")}행</span>;
    case "failed":
      return (
        <span role="alert">
          실패 <span className={styles.reason}>{event.reason}</span>
        </span>
      );
  }
}
