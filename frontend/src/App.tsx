import { useEffect, useRef, useState, type FormEvent } from "react";

import styles from "./App.module.css";
import { getExamples, getSchema, streamQuery } from "./api/client";
import type { QueryEvent, SchemaTable } from "./api/types";
import { ResultTable } from "./components/ResultTable";
import { SchemaPanel } from "./components/SchemaPanel";
import { StepList } from "./components/StepList";

const MAX_LENGTH = 300; // QRY-R001

export function App() {
  const [question, setQuestion] = useState("");
  const [events, setEvents] = useState<QueryEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [tables, setTables] = useState<SchemaTable[]>([]);
  const [examples, setExamples] = useState<string[]>([]);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    getSchema()
      .then(setTables)
      .catch(() => setTables([]));
    getExamples()
      .then(setExamples)
      .catch(() => setExamples([]));
  }, []);

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || running) return;
    abort.current = new AbortController();
    setEvents([]);
    setRunning(true);
    try {
      await streamQuery(
        trimmed,
        (event) => setEvents((prev) => [...prev, event]),
        abort.current.signal,
      );
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        setEvents((prev) => [...prev, { type: "failed", reason: "서버와 연결이 끊겼습니다." }]);
      }
    } finally {
      setRunning(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void ask(question);
  }

  const done = events.find((e) => e.type === "done");
  const sql = [...events].reverse().find((e) => e.type === "validated" || e.type === "generated");

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1>매출 질의 Agent</h1>
        <p>
          2025년 가상 매출 데이터에 자연어로 물어보세요. 로컬 모델이 SQL 을 만들고, 규칙이 검증한 뒤
          실행합니다.
        </p>
      </header>

      <main className={styles.main}>
        <section className={styles.content}>
          <form className={styles.form} onSubmit={onSubmit}>
            <label htmlFor="question" className={styles.srOnly}>
              질문
            </label>
            <input
              id="question"
              value={question}
              maxLength={MAX_LENGTH}
              placeholder="예: 매출 상위 3개 매장은?"
              onChange={(e) => setQuestion(e.target.value)}
              disabled={running}
            />
            {running ? (
              <button type="button" onClick={() => abort.current?.abort()}>
                중지
              </button>
            ) : (
              <button type="submit" disabled={!question.trim()}>
                질문하기
              </button>
            )}
          </form>

          <div className={styles.examples}>
            {examples.map((example) => (
              <button
                key={example}
                type="button"
                disabled={running}
                onClick={() => {
                  setQuestion(example);
                  void ask(example);
                }}
              >
                {example}
              </button>
            ))}
          </div>

          {events.length > 0 && (
            <>
              <h2>진행</h2>
              <StepList events={events} running={running} />
            </>
          )}

          {sql && (
            <>
              <h2>{sql.type === "validated" ? "실행한 SQL" : "만든 SQL"}</h2>
              <pre className={styles.sql}>{sql.sql}</pre>
            </>
          )}

          {done && (
            <>
              <h2>결과</h2>
              <ResultTable columns={done.columns} rows={done.rows} truncated={done.truncated} />
            </>
          )}
        </section>

        <aside className={styles.aside}>
          <h2>데이터</h2>
          <SchemaPanel tables={tables} />
        </aside>
      </main>
    </div>
  );
}
