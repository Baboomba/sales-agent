// 질의 도메인의 서버 주소. 주소 하나에 함수 하나 (코드 아키텍처 6.3).

import { getJson, postJson, readText } from "@/api/client";
import { parseSse } from "@/api/sse";
import type { QueryEvent, SchemaTable } from "@/api/types/query";

export const getSchema = async (): Promise<SchemaTable[]> => {
  const body = await getJson<{ tables: SchemaTable[] }>("/api/schema");
  return body.tables;
};

/** 쓰는 모델 이름 (설계서 2.4 `/api/health`). */
export const getModelName = async (): Promise<string> => {
  const body = await getJson<{ status: string; model: string }>("/api/health");
  return body.model;
};

export const getExamples = async (): Promise<string[]> => {
  const body = await getJson<{ questions: string[] }>("/api/examples");
  return body.questions;
};

/** 질문을 보내고 단계 이벤트를 받는 대로 넘긴다. POST 라 EventSource 대신 스트림을 직접 읽는다. */
export const streamQuery = async (
  question: string,
  onEvent: (event: QueryEvent) => void,
  signal: AbortSignal,
): Promise<void> => {
  const response = await postJson("/api/queries", { question }, signal);
  if (!response.ok || !response.body) {
    const detail = await response.text();
    onEvent({
      type: "failed",
      reason: `요청을 처리할 수 없습니다 (${response.status}). ${detail}`,
    });
    return;
  }
  let buffer = "";
  await readText(response.body, (text) => {
    const parsed = parseSse(buffer + text);
    buffer = parsed.rest;
    parsed.events.forEach(onEvent);
  });
};
