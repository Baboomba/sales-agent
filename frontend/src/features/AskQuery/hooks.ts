import { useEffect, useRef, useState } from "react";

import { getExamples, streamQuery } from "@/api/query";
import type { QueryEvent } from "@/api/types/query";

import { isAbort, questionToSend } from "./service";

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

/** 질문하고 단계 이벤트를 받는 상태. */
export const useAskQuery = () => {
  const [question, setQuestion] = useState("");
  const [events, setEvents] = useState<QueryEvent[]>([]);
  const [running, setRunning] = useState(false);
  const abort = useRef<AbortController | null>(null);

  const ask = async (text: string) => {
    const toSend = questionToSend(text);
    if (toSend === null || running) return;
    abort.current = new AbortController();
    setEvents([]);
    setRunning(true);
    try {
      await streamQuery(
        toSend,
        (event) => setEvents((prev) => [...prev, event]),
        abort.current.signal,
      );
    } catch (error) {
      if (!isAbort(error)) {
        setEvents((prev) => [...prev, { type: "failed", reason: "서버와 연결이 끊겼습니다." }]);
      }
    } finally {
      setRunning(false);
    }
  };

  const stop = () => abort.current?.abort();

  return { question, setQuestion, events, running, ask, stop };
};
