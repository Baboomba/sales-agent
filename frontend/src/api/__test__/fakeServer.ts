// 화면 테스트가 함께 쓰는 가짜 서버 (테스트 규칙 7.1 — 가짜는 한 자리에).
// fetch 자리에 끼운다. 주소마다 정해 둔 답을 차례로 돌려주고, 받은 요청을 기록하기만 한다 (5절).

/** 주소 하나가 돌려줄 답. */
export type FakeReply =
  | { json: unknown }
  | { sse: string; status?: 200 }
  | { status: number; text: string }
  | { sseThenDisconnect: string } // SSE 를 보낸 뒤 본문 스트림이 끊긴다
  | { hang: true } // 끊길 때까지 답하지 않는다 — 중지하면 AbortError
  | { disconnect: true }; // 연결이 끊긴다 — fetch 가 TypeError

export interface FakeRequest {
  path: string;
  body: unknown;
}

const reply = (answer: FakeReply, signal: AbortSignal | undefined): Promise<Response> => {
  if ("json" in answer) return Promise.resolve(Response.json(answer.json));
  if ("sse" in answer) return Promise.resolve(new Response(answer.sse));
  if ("text" in answer)
    return Promise.resolve(new Response(answer.text, { status: answer.status }));
  if ("disconnect" in answer) return Promise.reject(new TypeError("zzz 연결 끊김"));
  if ("sseThenDisconnect" in answer) {
    // 첫 읽기에 SSE 를 주고 다음 읽기에서 끊는다. start 에서 바로 error 하면 읽기 전의 조각이 버려진다.
    const chunks = [new TextEncoder().encode(answer.sseThenDisconnect)];
    const body = new ReadableStream<Uint8Array>({
      pull: (controller) => {
        const chunk = chunks.shift();
        if (chunk) controller.enqueue(chunk);
        else controller.error(new TypeError("zzz 연결 끊김"));
      },
    });
    return Promise.resolve(new Response(body));
  }
  return new Promise((_, reject) => {
    signal?.addEventListener("abort", () => reject(new DOMException("zzz", "AbortError")));
  });
};

/** 주소마다 답을 정한 가짜 fetch 와 받은 요청 기록. */
export const fakeServer = (routes: Record<string, FakeReply[]>) => {
  const requests: FakeRequest[] = [];
  const fetch = (path: string, init?: RequestInit): Promise<Response> => {
    requests.push({
      path,
      body: init?.body === undefined ? undefined : JSON.parse(String(init.body)),
    });
    const answer = routes[path]?.shift();
    if (answer === undefined)
      return Promise.reject(new Error(`가짜 서버에 정해 둔 답이 없다: ${path}`));
    return reply(answer, init?.signal ?? undefined);
  };
  return { fetch, requests };
};

/** SSE 본문. 이벤트 하나는 `event:` · `data:` 두 줄이다 (설계서 2.2). */
export const sse = (...events: [string, unknown][]): string =>
  events.map(([name, data]) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`).join("");
