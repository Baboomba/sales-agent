import { useEffect, useRef, useState } from "react";

import { getExamples, streamQuery } from "@/api/query";
import type { QueryEvent } from "@/api/types/query";
import { useLoad } from "@/common/useLoad";

import { PENDING_DELAY_MS, REVEAL_STEP_MS, isAbort, questionToSend } from "./service";

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

/** 움직임을 줄이도록 설정했는지. 설정을 읽을 수 없는 곳(테스트 등)은 아니라고 본다. */
const prefersReducedMotion = (): boolean =>
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * 받은 단계 가운데 지금 드러낸 것 (SCR-R016).
 *
 * 첫 단계는 받자마자 드러낸다(SCR-R003 의 한 번에 바꾸기 그대로). 다음 단계부터는 앞 단계를 드러낸
 * 뒤 `REVEAL_STEP_MS` 가 지나야 드러낸다 — 이미 그만큼 지났으면 바로. 첫 단계가 바뀌면(새 질문)
 * 처음부터 다시 센다. 움직임을 줄이도록 설정한 사용자에게는 받은 대로 모두 드러낸다.
 */
export const useRevealed = (events: QueryEvent[]): QueryEvent[] => {
  const [reduced] = useState(prefersReducedMotion);
  const [state, setState] = useState<{ first: QueryEvent | undefined; shown: number }>({
    first: undefined,
    shown: 0,
  });
  const lastRevealAt = useRef(0);
  const counted = useRef<QueryEvent | undefined>(undefined);
  const first = events[0];
  // 첫 단계가 바뀌었으면(새 질문) 아직 상태에 남은 앞 질문의 수를 쓰지 않는다.
  const shown =
    state.first === first ? Math.min(state.shown, events.length) : Math.min(events.length, 1);
  const behind = shown < events.length;

  useEffect(() => {
    if (counted.current !== first) {
      counted.current = first;
      lastRevealAt.current = Date.now();
    }
    if (!behind) return;
    const wait = Math.max(0, lastRevealAt.current + REVEAL_STEP_MS - Date.now());
    const timer = setTimeout(() => {
      lastRevealAt.current = Date.now();
      setState({ first, shown: shown + 1 });
    }, wait);
    return () => clearTimeout(timer);
  }, [first, shown, behind]);

  return reduced ? events : events.slice(0, shown);
};
