import { parseSse } from "./sse";
import type { QueryEvent, SchemaTable } from "./types";

export async function getSchema(): Promise<SchemaTable[]> {
  const response = await fetch("/api/schema");
  const body = (await response.json()) as { tables: SchemaTable[] };
  return body.tables;
}

export async function getExamples(): Promise<string[]> {
  const response = await fetch("/api/examples");
  const body = (await response.json()) as { questions: string[] };
  return body.questions;
}

/** 질문을 보내고 단계 이벤트를 받는 대로 넘긴다. POST 라 EventSource 대신 스트림을 직접 읽는다. */
export async function streamQuery(
  question: string,
  onEvent: (event: QueryEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch("/api/queries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
  });
  if (!response.ok || !response.body) {
    const detail = await response.text();
    onEvent({
      type: "failed",
      reason: `요청을 처리할 수 없습니다 (${response.status}). ${detail}`,
    });
    return;
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    const parsed = parseSse(buffer + value);
    buffer = parsed.rest;
    parsed.events.forEach(onEvent);
  }
}
