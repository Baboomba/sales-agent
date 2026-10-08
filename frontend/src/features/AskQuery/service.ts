// 질문하기의 순수 로직. React 도 서버 호출도 부르지 않는다 (코드 아키텍처 6.2).

import type { QueryEvent } from "@/api/types/query";

/** 질문 길이 상한 (QRY-R001). 입력칸이 이보다 길게 받지 않는다. */
export const QUESTION_MAX_LENGTH = 300;

/** 응답이 이보다 늦을 때만 진행 표시를 보인다. 빠른 응답에 진행 표시가 번쩍이지 않게 (#63). */
export const PENDING_DELAY_MS = 300;

export type SqlEvent = Extract<QueryEvent, { type: "generated" | "validated" }>;
export type DoneEvent = Extract<QueryEvent, { type: "done" }>;

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

/** SQL 머리글. 검증을 통과해 실행한 것인지, 만들기만 한 것인지 가른다. */
export const sqlHeading = (event: SqlEvent): string =>
  event.type === "validated" ? "실행한 SQL" : "만든 SQL";

/** 완료 이벤트. 없으면 null. */
export const doneEvent = (events: QueryEvent[]): DoneEvent | null =>
  events.find((event): event is DoneEvent => event.type === "done") ?? null;

/** 사용자가 멈춰 난 오류인지. 멈춘 것은 실패로 알리지 않는다. */
export const isAbort = (error: unknown): boolean =>
  error instanceof DOMException && error.name === "AbortError";
