import { useEffect, useRef } from "react";

import type { QueryEvent } from "@/api/types/query";
import { STAGE_LABEL } from "@/common/values";

import styles from "./ProcessLog.module.css";

interface Props {
  events: QueryEvent[];
  pending: boolean;
  /** 맨 위 요약 — 시도 수 · 다시 만든 수 · 행 수. 단계 칸과 같은 값을 쓴다. */
  summary: { attempts: number; retries: number; rows: number | null };
}

/** 질의 단계를 일어난 순서대로 쌓은 처리 기록 (FR-002 · FR-004 · FR-005). */
export const ProcessLog = ({ events, pending, summary }: Props) => {
  const list = useRef<HTMLOListElement>(null);
  // 노드가 늘면 칸 안에서 아래로 따라간다. 칸 크기는 그대로다 (SCR-R001).
  useEffect(() => {
    if (list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [events.length, pending]);
  return (
    <div className={styles.log}>
      <dl className={styles.summary}>
        <SummaryItem label="시도" value={String(summary.attempts)} />
        <SummaryItem label="다시 만듦" value={String(summary.retries)} />
        <SummaryItem
          label="행"
          value={summary.rows === null ? "—" : summary.rows.toLocaleString("ko-KR")}
        />
      </dl>
      {events.length === 0 && !pending ? (
        <p className={styles.empty}>질문하면 처리 기록이 여기에 쌓입니다.</p>
      ) : (
        <ol ref={list} className={styles.list} aria-label="처리 기록">
          {events.map((event, index) => (
            <Entry key={index} event={event} />
          ))}
          {/* 진행 중 노드는 다음 단계의 자리(같은 key)에 둔다 — 단계가 오면 그 자리에서 상태가 바뀐다 (SCR-R016). */}
          {pending && <Entry key={events.length} event={null} />}
        </ol>
      )}
    </div>
  );
};

interface SummaryItemProps {
  label: string;
  value: string;
}

const SummaryItem = ({ label, value }: SummaryItemProps) => (
  <div>
    <dt>{label}</dt>
    <dd>{value}</dd>
  </div>
);

interface EntryProps {
  /** null 이면 아직 오지 않은 다음 단계 — 진행 중 노드. */
  event: QueryEvent | null;
}

/** 기록 한 줄. 판별 유니온을 끝까지 다룬다. */
const Entry = ({ event }: EntryProps) => {
  if (event === null) return <Row tone="run" title="진행 중…" />;
  switch (event.type) {
    case "generated":
      return (
        <Row tone="gen" title="생성" tag={`시도 ${event.attempt}`} note="SQL 을 만들었습니다">
          <code className={styles.code}>{event.sql}</code>
        </Row>
      );
    case "rejected":
      return (
        <Row
          tone="warn"
          title={`${STAGE_LABEL[event.stage]} 실패`}
          tag={`시도 ${event.attempt}`}
          note="사유를 붙여 다시 만듭니다"
        >
          <p className={styles.why}>{event.reason}</p>
        </Row>
      );
    case "validated":
      return <Row tone="ok" title="검증 통과" note="조회문인지 확인했습니다" />;
    case "done":
      return (
        <Row
          tone="ok"
          title="실행 완료"
          tag={`${event.rows.length.toLocaleString("ko-KR")}행`}
          note="결과를 표로 보여 줍니다"
        />
      );
    case "failed":
      return (
        <Row tone="bad" title="실패">
          <p className={styles.why}>{event.reason}</p>
        </Row>
      );
  }
};

interface RowProps {
  tone: "gen" | "warn" | "ok" | "bad" | "run";
  title: string;
  tag?: string;
  note?: string;
  children?: React.ReactNode;
}

const Row = ({ tone, title, tag, note, children }: RowProps) => (
  <li className={`${styles.entry} ${styles[tone]}`}>
    <span className={styles.icon} aria-hidden="true" />
    <span className={styles.head}>
      <span className={styles.title}>{title}</span>
      {tag && <span className={styles.tag}>{tag}</span>}
    </span>
    {note && <span className={styles.note}>{note}</span>}
    {children}
  </li>
);
