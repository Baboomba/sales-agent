import { useEffect, useRef, useState } from "react";

import { getExamples, streamQuery } from "@/api/query";
import type { QueryEvent } from "@/api/types/query";
import { useLoad } from "@/common/useLoad";

import { PENDING_DELAY_MS, isAbort, questionToSend } from "./service";

/** 예시 질문을 불러온다. 못 불러오면 실패를 알리고 다시 시도할 수 있다 (SCR-R014). */
export const useExamples = () => useLoad(getExamples);

/**
 * 질문하고 단계 이벤트를 받는 상태.
 *
 * 깜빡이지 않게(SCR-R002 · R003) 진행 표시는 응답이 늦을 때만 보인다. 새로 물어도 첫 단계가 올 때까지는 앞
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
  // 끝(완료 · 실패) 이벤트를 받았는지. 못 받고 닫히면 실패로 알린다.
  const ended = useRef(false);

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
    if (event.type === "done" || event.type === "failed") ended.current = true;
    setEvents((prev) => (first ? [event] : [...prev, event]));
  };

  const ask = async (text: string) => {
    const toSend = questionToSend(text);
    if (toSend === null || running) return;
    abort.current = new AbortController();
    received.current = false;
    ended.current = false;
    setSlow(false);
    setRunning(true);
    try {
      await streamQuery(toSend, receive, abort.current.signal);
      if (!ended.current) receive({ type: "failed", reason: "응답이 끝나지 않고 닫혔습니다." });
    } catch (error) {
      // 중지하면 묻기 전으로 돌아간다 — 앞 질문의 단계도, 받다 만 단계도 남기지 않는다 (2.3).
      if (isAbort(error)) setEvents([]);
      else receive({ type: "failed", reason: "서버와 연결이 끊겼습니다." });
    } finally {
      setRunning(false);
      setSlow(false);
    }
  };

  const stop = () => abort.current?.abort();

  return { question, setQuestion, events, running, pending: running && slow, ask, stop };
};
