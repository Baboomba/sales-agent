// 질문하기의 순수 로직. React 도 서버 호출도 부르지 않는다 (코드 아키텍처 6.2).

import type { QueryEvent } from "@/api/types/query";

/** 질문 길이 상한 (QRY-R001 · SCR-R005). 입력칸이 이보다 길게 받지 않는다. */
export const QUESTION_MAX_LENGTH = 300;

/** 응답이 이보다 늦을 때만 진행 표시를 보인다. 빠른 응답에 진행 표시가 번쩍이지 않게 (SCR-R002). */
export const PENDING_DELAY_MS = 300;

type SqlEvent = Extract<QueryEvent, { type: "generated" | "validated" }>;
type DoneEvent = Extract<QueryEvent, { type: "done" }>;
type FailedEvent = Extract<QueryEvent, { type: "failed" }>;

/** 보낼 질문. 앞뒤 공백만 있으면 보내지 않는다(null). */
export const questionToSend = (text: string): string | null => {
  const trimmed = text.trim();
  return trimmed === "" ? null : trimmed;
};

/** 가장 나중에 만들었거나 실행한 SQL. 없으면 null. */
export const latestSql = (events: QueryEvent[]): SqlEvent | null => {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (event?.type === "generated" || event?.type === "validated") return event;
  }
  return null;
};

/** SQL 머리글. 검증을 통과해 실행한 것인지, 만들기만 한 것인지 가른다 (SCR-R009). */
export const sqlHeading = (event: SqlEvent): string =>
  event.type === "validated" ? "실행한 SQL" : "만든 SQL";

/** 완료 이벤트. 없으면 null. */
export const doneEvent = (events: QueryEvent[]): DoneEvent | null =>
  events.find((event): event is DoneEvent => event.type === "done") ?? null;

/** 사용자가 멈춰 난 오류인지. 멈춘 것은 실패로 알리지 않는다. */
export const isAbort = (error: unknown): boolean =>
  error instanceof DOMException && error.name === "AbortError";

/** 실패 이벤트. 없으면 null. */
export const failedEvent = (events: QueryEvent[]): FailedEvent | null =>
  events.find((event): event is FailedEvent => event.type === "failed") ?? null;

/** 단계 칸과 처리 기록이 함께 보이는 요약 — 시도 번호 · 다시 만든 수 · 행 수 (SCR-R007 · R008). */
export const attemptSummary = (events: QueryEvent[]) => {
  const attempts = events.flatMap((event) =>
    event.type === "generated" || event.type === "rejected" ? [event.attempt] : [],
  );
  return {
    attempts: attempts.length === 0 ? 0 : Math.max(...attempts),
    retries: events.filter((event) => event.type === "rejected").length,
    rows: doneEvent(events)?.rows.length ?? null,
  };
};

/** 기다리는 동안 결과 카드에 적을 지금 단계. 마지막으로 받은 단계의 다음 일이다 (SCR-R002). */
export const progressText = (events: QueryEvent[]): string => {
  switch (events.at(-1)?.type) {
    case "generated":
      return "SQL 을 검증하는 중";
    case "validated":
      return "SQL 을 실행하는 중";
    case "rejected":
      return "사유를 붙여 SQL 을 다시 만드는 중";
    // 아직 받은 단계가 없으면 첫 생성 중이다. 완료 · 실패 뒤에는 기다리지 않으므로 이 글을 보이지 않는다.
    case undefined:
    case "done":
    case "failed":
      return "SQL 을 만드는 중";
  }
};
