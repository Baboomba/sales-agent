// 끝단 테스트의 가짜 모델 서버. Ollama 와 같은 주소(/api/chat)로 답한다 — 언어 모델을 부르지 않는다 (NFR-005).
// 프롬프트 끝의 「질문: …」을 읽어, 그 질문의 대본을 시도마다 차례로 낸다. 검증 · 실행 · 재생성 ·
// 화면은 모두 실제 코드가 돈다.
//
//   node e2e/fake-ollama.mjs [포트]      기본 11500
//   POST /__reset                       시도 수를 처음으로

import { createServer } from "node:http";

import { SCRIPTS } from "./scripts.mjs";

const port = Number(process.argv[2] ?? 11500);
const attempts = new Map();

/** 프롬프트의 마지막 「질문: …」. 앞의 예시 질의에도 「질문:」이 있어 마지막 것을 고른다. */
const questionOf = (prompt) => {
  const matches = [...prompt.matchAll(/질문: (.+)\n출력:/g)];
  return matches.at(-1)?.[1]?.trim() ?? "";
};

const readBody = (request) =>
  new Promise((resolve) => {
    let body = "";
    request.on("data", (chunk) => {
      body += chunk;
    });
    request.on("end", () => resolve(body));
  });

// 화면에서 중지하면 서버가 연결을 끊는다 — 기다림도 그만둔다. 요청 본문은 다 읽으면 닫힌 것으로
// 치므로, 끊김은 응답 쪽에서 본다.
const wait = (ms, response) =>
  new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    response.on("close", () => {
      clearTimeout(timer);
      resolve();
    });
  });

const chatLine = (content, done) =>
  JSON.stringify({
    model: "zzz-model",
    created_at: new Date().toISOString(),
    message: { role: "assistant", content },
    done,
    ...(done ? { done_reason: "stop", eval_count: 1, prompt_eval_count: 1 } : {}),
  });

const answer = async (request, response) => {
  const body = JSON.parse(await readBody(request));
  const question = questionOf(body.messages?.at(-1)?.content ?? "");
  const script = SCRIPTS[question];
  const attempt = attempts.get(question) ?? 0;
  attempts.set(question, attempt + 1);
  const step = script?.[Math.min(attempt, script.length - 1)];
  if (!step) {
    response.writeHead(500, { "content-type": "application/json" });
    response.end(JSON.stringify({ error: `대본에 없는 질문: ${question}` }));
    return;
  }
  if (step.delayMs) await wait(step.delayMs, response);
  if (response.destroyed) return;
  if (step.error) {
    response.writeHead(404, { "content-type": "application/json" });
    response.end(JSON.stringify({ error: step.error }));
    return;
  }
  const content = JSON.stringify({ sql: step.sql });
  response.writeHead(200, { "content-type": "application/x-ndjson" });
  if (body.stream === false) {
    response.end(chatLine(content, true));
    return;
  }
  response.write(`${chatLine(content, false)}\n`);
  response.end(`${chatLine("", true)}\n`);
};

createServer((request, response) => {
  if (request.method === "POST" && request.url === "/__reset") {
    attempts.clear();
    response.end("ok");
    return;
  }
  if (request.url === "/__health" || request.url === "/api/tags") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({ models: [{ name: "zzz-model" }] }));
    return;
  }
  if (request.method === "POST" && request.url === "/api/chat") {
    void answer(request, response);
    return;
  }
  response.writeHead(404);
  response.end();
}).listen(port, "127.0.0.1", () => console.log(`가짜 모델 서버 http://127.0.0.1:${port}`));
