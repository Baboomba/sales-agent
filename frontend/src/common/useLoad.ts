// 한 번 불러와 보여 주는 것(표와 열 · 예시 질문 · 모델 이름)의 상태. 못 불러오면 다시 시도한다 (SCR-R014).
// 어느 기능의 것도 아니라 common 에 둔다 (코드 아키텍처 6.1).

import { useEffect, useState } from "react";

type Load<T> = { status: "loading" } | { status: "ok"; value: T } | { status: "failed" };

/** `load` 는 바뀌지 않는 함수여야 한다 — 모듈의 서버 부르기 함수를 그대로 넘긴다. */
export const useLoad = <T>(load: () => Promise<T>) => {
  const [state, setState] = useState<Load<T>>({ status: "loading" });
  const [round, setRound] = useState(0);

  useEffect(() => {
    let alive = true;
    load()
      .then((value) => alive && setState({ status: "ok", value }))
      .catch(() => alive && setState({ status: "failed" }));
    return () => {
      alive = false;
    };
  }, [load, round]);

  const retry = () => {
    setState({ status: "loading" });
    setRound((r) => r + 1);
  };

  return { state, retry };
};
