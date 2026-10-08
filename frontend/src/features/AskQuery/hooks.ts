import { useEffect, useRef, useState } from "react";

import { getExamples, streamQuery } from "@/api/query";
import type { QueryEvent } from "@/api/types/query";

import { PENDING_DELAY_MS, isAbort, questionToSend } from "./service";

/** 예시 질문을 불러온다. 못 불러오면 빈 목록이다. */
export const useExamples = (): string[] => {
  const [examples, setExamples] = useState<string[]>([]);
  useEffect(() => {
    getExamples()
      .then(setExamples)
      .catch(() => setExamples([]));
  }, []);
  return examples;
};

/**
 * 질문하고 단계 이벤트를 받는 상태.
 *
 * 깜빡이지 않게(#63) 진행 표시는 응답이 늦을 때만 보인다. 새로 물어도 첫 단계가 올 때까지는 앞
 * 질문의 단계를 그대로 두고, 첫 단계가 오면 한 번에 바꾼다. `PENDING_DELAY_MS` 가 지나도 첫 단계가
 * 없으면 그때 앞 단계를 지우고 진행 중(`pending`)을 알린다.
 */
export const useAskQuery = () => {
  const [question, setQuestion] = useState("");
  const [events, setEvents] = useState<QueryEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [slow, setSlow] = useState(false);
  const abort = useRef<AbortController | null>(null);
  // 이번 질문의 첫 단계를 받았는지. 받기 전까지는 앞 질문의 단계가 보인다.
  const received = useRef(false);

  useEffect(() => {
    if (!running) return;
    const timer = setTimeout(() => {
      setSlow(true);
      if (!received.current) setEvents([]);
    }, PENDING_DELAY_MS);
    return () => clearTimeout(timer);
  }, [running]);

  const receive = (event: QueryEvent) => {
    const first = !received.current;
    received.current = true;
    setEvents((prev) => (first ? [event] : [...prev, event]));
  };

  const ask = async (text: string) => {
    const toSend = questionToSend(text);
    if (toSend === null || running) return;
    abort.current = new AbortController();
    received.current = false;
    setSlow(false);
    setRunning(true);
    try {
      await streamQuery(toSend, receive, abort.current.signal);
    } catch (error) {
      if (!isAbort(error)) receive({ type: "failed", reason: "서버와 연결이 끊겼습니다." });
    } finally {
      // 단계를 하나도 받지 못하고 끝났으면(중지) 앞 질문의 단계를 남기지 않는다.
      if (!received.current) setEvents([]);
      setRunning(false);
      setSlow(false);
    }
  };

  const stop = () => abort.current?.abort();

  return { question, setQuestion, events, running, pending: running && slow, ask, stop };
};
