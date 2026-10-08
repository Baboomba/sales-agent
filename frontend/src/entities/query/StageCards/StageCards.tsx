import type { QueryEvent } from "@/api/types/query";
import { STAGE_LABEL, type Stage } from "@/common/values";

import styles from "./StageCards.module.css";

/** 단계 하나의 상태 (screen.md SCR-R007). */
type StageStatus = "wait" | "run" | "done" | "fail";

const STATUS_TEXT: Record<StageStatus, string> = {
  wait: "대기",
  run: "진행 중",
  done: "완료",
  fail: "실패",
};

/**
 * 받은 단계에서 생성 · 검증 · 실행의 지금 상태를 읽는다. 표시용 계산이다 (코드 아키텍처 6.2).
 *
 * 마지막 거부됨 뒤의 단계만 지금 시도로 본다. 끝내 실패하면 실패 이벤트에 단계가 없으므로,
 * 지금 시도가 어디까지 왔는지로 실패한 단계를 가린다.
 */
export const stageStatuses = (
  events: QueryEvent[],
  pending: boolean,
): Record<Stage, StageStatus> => {
  const lastRejected = events.findLastIndex((event) => event.type === "rejected");
  const current = events.slice(lastRejected + 1);
  const has = (type: QueryEvent["type"]) => current.some((event) => event.type === type);
  const failed = has("failed");
  const step = (reached: boolean, done: boolean): StageStatus => {
    if (done) return "done";
    if (reached && failed) return "fail";
    if (reached && pending) return "run";
    return "wait";
  };
  return {
    generate: step(true, has("generated")),
    validate: step(has("generated"), has("validated")),
    execute: step(has("validated"), has("done")),
  };
};

/** 생성 칸의 덧말 — 시도 번호와 다시 만든 횟수. 다시 만든 적이 없으면 시도 번호만, 시도 전이면 비운다. */
export const attemptText = (attempts: number, retries: number): string => {
  if (attempts === 0) return "";
  const attempt = `시도 ${attempts}`;
  return retries === 0 ? attempt : `${attempt} · ${retries}번 다시 만듦`;
};

const doneText = (stage: Stage, rows: number | null): string => {
  if (stage === "validate") return "조회문 확인";
  if (stage === "execute" && rows !== null) return `완료 · ${rows.toLocaleString("ko-KR")}행`;
  return "완료";
};

interface Props {
  events: QueryEvent[];
  pending: boolean;
  /** 시도 번호 · 다시 만든 수 · 행 수. 처리 기록과 같은 값을 쓴다. */
  summary: { attempts: number; retries: number; rows: number | null };
}

/** 생성 · 검증 · 실행 세 칸. 받은 단계로 지금 상태를 보인다 (FR-002 · FR-004). */
export const StageCards = ({ events, pending, summary }: Props) => {
  const statuses = stageStatuses(events, pending);
  const attempt = attemptText(summary.attempts, summary.retries);
  const note = (stage: Stage): string => {
    const status = statuses[stage];
    if (stage === "generate" && attempt !== "" && status !== "fail") return attempt;
    if (status === "done") return doneText(stage, summary.rows);
    return STATUS_TEXT[status];
  };
  return (
    <ol className={styles.cards} aria-label="진행 단계">
      {(["generate", "validate", "execute"] as const).map((stage, index) => (
        <StageCard
          key={stage}
          number={index + 1}
          stage={stage}
          status={statuses[stage]}
          note={note(stage)}
        />
      ))}
    </ol>
  );
};

interface StageCardProps {
  number: number;
  stage: Stage;
  status: StageStatus;
  note: string;
}

const StageCard = ({ number, stage, status, note }: StageCardProps) => (
  <li className={`${styles.card} ${styles[status] ?? ""}`} data-status={status}>
    <span className={styles.mark} aria-hidden="true">
      {status === "done" ? <Check /> : number}
    </span>
    <span className={styles.text}>
      <span className={styles.title}>{STAGE_LABEL[stage]}</span>
      <span className={styles.note}>{note}</span>
    </span>
  </li>
);

const Check = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.4"
    strokeLinecap="round"
  >
    <path d="m5 12 5 5 9-10" />
  </svg>
);
