// 질문마다 가짜 모델이 시도 순서대로 낼 것. 마지막 대본은 그 뒤 시도에도 되풀이한다.
//   { sql }              이 SQL 을 낸다
//   { delayMs, sql }     기다렸다가 낸다 — 늦은 응답 · 중지
//   { error }            오류 응답(모델 없음 등) — 모델 서버 장애 (QRY-R013)

export const QUESTIONS = {
  topStores: "매출 상위 3개 매장은?",
  regenerate: "zzz 다시 만드는 질문",
  giveUp: "zzz 끝내 실패하는 질문",
  outage: "zzz 모델 서버 장애 질문",
  slow: "zzz 늦게 답하는 질문",
  hang: "zzz 끝나지 않는 질문",
  truncated: "zzz 잘리는 질문",
};

const TOP_STORES =
  "SELECT s.name, SUM(oi.quantity * oi.unit_price) AS revenue FROM order_items oi " +
  "JOIN orders o ON o.order_id = oi.order_id JOIN stores s ON s.store_id = o.store_id " +
  "GROUP BY s.name ORDER BY revenue DESC LIMIT 3";
const BY_CHANNEL =
  "SELECT channel, COUNT(*) AS orders FROM orders GROUP BY channel ORDER BY channel";

export const SCRIPTS = {
  [QUESTIONS.topStores]: [{ sql: TOP_STORES }],
  [QUESTIONS.regenerate]: [{ sql: "DELETE FROM orders" }, { sql: BY_CHANNEL }],
  [QUESTIONS.giveUp]: [
    { sql: "DELETE FROM orders" },
    { sql: "DROP TABLE orders" },
    { sql: "UPDATE orders SET channel = 'zzz'" },
  ],
  [QUESTIONS.outage]: [{ error: "model 'zzz-model' not found" }],
  [QUESTIONS.slow]: [{ delayMs: 1500, sql: BY_CHANNEL }],
  // 첫 시도는 거부되어 단계가 쌓이고, 다시 만드는 둘째 시도에서 멈춘다 — 받은 단계가 있는 채로 중지한다.
  [QUESTIONS.hang]: [{ sql: "DELETE FROM orders" }, { delayMs: 60000, sql: BY_CHANNEL }],
  [QUESTIONS.truncated]: [{ sql: "SELECT order_id FROM orders ORDER BY order_id" }],
};
