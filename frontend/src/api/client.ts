// 서버를 부르는 공통 처리. fetch 는 api/ 밖에서 쓰지 않는다 (코드 아키텍처 6.3).

/** GET 으로 JSON 을 받는다. 바깥에서 들어온 JSON 이라 여기서만 타입을 단언한다.
 * 오류 응답이면 던진다 — 부르는 쪽이 「불러오지 못했다」를 알 수 있게 (SCR-R014). */
export const getJson = async <T>(path: string): Promise<T> => {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} ${response.status}`);
  return (await response.json()) as T;
};

/** POST 로 JSON 을 보낸다. 본문을 스트림으로 읽어야 해 응답을 그대로 돌려준다. */
export const postJson = (path: string, body: unknown, signal: AbortSignal): Promise<Response> =>
  fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

/** 응답 본문을 글 조각으로 받는 대로 넘긴다. */
export const readText = async (
  body: NonNullable<Response["body"]>,
  onText: (text: string) => void,
): Promise<void> => {
  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    onText(value);
  }
};
