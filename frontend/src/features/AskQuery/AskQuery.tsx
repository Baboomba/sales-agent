import { useState, type FormEvent, type ReactNode } from "react";

import type { QueryEvent } from "@/api/types/query";
import { LoadFailed } from "@/components/LoadFailed";
import { Skeleton } from "@/components/Skeleton";
import { ProcessLog } from "@/entities/query/ProcessLog";
import { QueryResult } from "@/entities/query/QueryResult";
import { QuerySql } from "@/entities/query/QuerySql";
import { StageCards } from "@/entities/query/StageCards";

import styles from "./AskQuery.module.css";
import { useAskQuery, useExamples, useRevealed } from "./hooks";
import {
  QUESTION_MAX_LENGTH,
  attemptSummary,
  doneEvent,
  failedEvent,
  latestSql,
  progressText,
  questionToSend,
  sqlHeading,
} from "./service";

interface Props {
  /** 화면이 그린 휴대폰 탭. 단계 칸과 결과 카드 사이에 놓는다 (SCR-R015). */
  mobileTabs: ReactNode;
  /** 휴대폰에서 숨길 칸. 화면이 고른 탭에 따라 정한다. */
  mobileHidden: { result: boolean; log: boolean };
}

/** 질문하고 단계 · SQL · 결과 · 처리 기록을 받아 본다 (FR-001 · FR-002 · FR-007). */
export const AskQuery = ({ mobileTabs, mobileHidden }: Props) => {
  const { question, setQuestion, events: received, running, pending, ask, stop } = useAskQuery();
  // 세 칸은 드러낸 단계만 본다 — 처리 기록만 앞서거나 결과 표가 먼저 뜨지 않게 (SCR-R016).
  const events = useRevealed(received);
  // 늦은 응답이거나, 받은 단계를 아직 다 드러내지 않았으면 진행 중이다. 드러내는 사이에 진행 표시가
  // 꺼졌다 켜지면 한 프레임씩 번쩍인다 (SCR-R002 · R016).
  const waiting = pending || events.length < received.length;
  const summary = attemptSummary(events);

  const askExample = (example: string) => {
    // 묻는 동안에는 단추를 끄지 않고 누름을 버린다 (SCR-R004).
    if (running) return;
    setQuestion(example);
    void ask(example);
  };

  return (
    <div className={styles.ask}>
      <div className={styles.main}>
        <QuestionForm
          question={question}
          pending={pending}
          onChange={setQuestion}
          onAsk={() => void ask(question)}
          onStop={stop}
        />
        <Examples question={question} onPick={askExample} />
        <StageCards events={events} pending={waiting} summary={summary} />
        {mobileTabs}
        <ResultCard events={events} pending={waiting} hidden={mobileHidden.result} />
      </div>
      <aside className={styles.log} aria-label="처리 기록" data-mobile-hidden={mobileHidden.log}>
        <div className={styles.logHead}>
          <h2>처리 기록</h2>
          <span>생성 → 검증 → 실행</span>
        </div>
        <ProcessLog events={events} pending={waiting} summary={summary} />
      </aside>
    </div>
  );
};

interface QuestionFormProps {
  question: string;
  /** 응답이 늦어 중지를 보일 때. 빠른 응답에는 단추가 바뀌지 않는다 (SCR-R002). */
  pending: boolean;
  onChange: (question: string) => void;
  onAsk: () => void;
  onStop: () => void;
}

/** 질문 입력칸과 질문하기 · 중지 단추. 두 단추는 폭이 같다. */
const QuestionForm = ({ question, pending, onChange, onAsk, onStop }: QuestionFormProps) => {
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    onAsk();
  };

  return (
    <form className={styles.form} onSubmit={onSubmit}>
      <label className={styles.box}>
        <SearchIcon />
        <span className="sr-only">질문</span>
        <input
          value={question}
          maxLength={QUESTION_MAX_LENGTH}
          placeholder="예: 매출 상위 3개 매장은?"
          onChange={(e) => onChange(e.target.value)}
        />
      </label>
      {/* 단추 하나가 질문하기 ↔ 중지를 오간다 — 갈아 끼우면 포커스를 잃는다. 묻는 동안 끄지 않는다 (SCR-R004).
          두 번 보내기는 ask 가 막는다. */}
      <button
        type={pending ? "button" : "submit"}
        className={styles.submit}
        disabled={!pending && questionToSend(question) === null}
        onClick={pending ? onStop : undefined}
      >
        {pending && <span className={styles.spinner} aria-hidden="true" />}
        {pending ? "중지" : "질문하기"}
      </button>
    </form>
  );
};

const SearchIcon = () => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    aria-hidden="true"
  >
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

interface ExamplesProps {
  question: string;
  onPick: (example: string) => void;
}

/** 누르면 바로 묻는 예시 질문. 질문칸의 글과 같은 예시를 강조한다 (FR-007 · SCR-R006). */
const Examples = ({ question, onPick }: ExamplesProps) => {
  const { state, retry } = useExamples();
  if (state.status === "failed") return <LoadFailed className={styles.examples} onRetry={retry} />;
  const examples = state.status === "ok" ? state.value : [];
  return (
    <div className={styles.examples}>
      {examples.map((example) => (
        <button
          key={example}
          type="button"
          className={styles.chip}
          aria-pressed={example === question}
          onClick={() => onPick(example)}
        >
          {example}
        </button>
      ))}
    </div>
  );
};

type ResultTab = "table" | "sql";

interface ResultCardProps {
  events: QueryEvent[];
  pending: boolean;
  hidden: boolean;
}

/** 결과 카드 — 표와 SQL 을 탭으로 나눈다. 높이는 늘 같다 (SCR-R001). */
const ResultCard = ({ events, pending, hidden }: ResultCardProps) => {
  const [tab, setTab] = useState<ResultTab>("table");
  const sql = latestSql(events);
  const failed = failedEvent(events);
  const sqlLabel = sql ? sqlHeading(sql) : "실행한 SQL";
  // 진행 표시는 늦은 응답에만 보인다 — 빠른 응답에 뼈대가 번쩍이지 않게 (SCR-R002).
  const loading = pending;
  return (
    <section
      className={styles.result}
      aria-label="결과"
      aria-busy={loading}
      data-mobile-hidden={hidden}
    >
      {/* 기다리는 동안 카드 위 가장자리를 따라 막대가 흐른다. */}
      {loading && <span className={styles.progressBar} data-testid="progress-bar" />}
      <div className={styles.resultHead}>
        <div>
          <h2>결과</h2>
          <p>숫자는 DB 가 낸 그대로입니다</p>
        </div>
        <div className={styles.tabs} role="tablist" aria-label="결과 보기">
          <ResultTabButton selected={tab === "table"} onClick={() => setTab("table")}>
            표
          </ResultTabButton>
          <ResultTabButton selected={tab === "sql"} onClick={() => setTab("sql")}>
            {sqlLabel}
          </ResultTabButton>
        </div>
      </div>
      <div className={styles.resultBody} role="tabpanel">
        {/* 실패 사유는 어느 탭을 보든 읽힌다 (SCR-R010). */}
        {failed && (
          <p className={styles.alert} role="alert">
            {failed.reason}
          </p>
        )}
        {tab === "table" ? (
          <ResultBody events={events} loading={loading} />
        ) : sql ? (
          <QuerySql sql={sql.sql} />
        ) : (
          <p className={styles.guide}>질문하면 만든 SQL 이 여기에 보입니다.</p>
        )}
      </div>
    </section>
  );
};

interface ResultTabButtonProps {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

const ResultTabButton = ({ selected, onClick, children }: ResultTabButtonProps) => (
  <button
    type="button"
    role="tab"
    className={styles.tab}
    aria-selected={selected}
    onClick={onClick}
  >
    {children}
  </button>
);

interface ResultBodyProps {
  events: QueryEvent[];
  loading: boolean;
}

/** 표 탭의 내용 — 결과 표 · 기다림 · 안내 가운데 하나. 실패면 위의 알림만 둔다. */
const ResultBody = ({ events, loading }: ResultBodyProps) => {
  if (failedEvent(events)) return null;
  const done = doneEvent(events);
  if (done)
    return <QueryResult columns={done.columns} rows={done.rows} truncated={done.truncated} />;
  if (loading) return <Waiting text={progressText(events)} />;
  // 단계를 받았지만 300ms 전이면 비워 둔다 — 곧 끝나거나 곧 뼈대가 뜬다.
  if (events.length > 0) return null;
  return <p className={styles.guide}>질문하거나 예시 질문을 눌러 보세요.</p>;
};

interface WaitingProps {
  text: string;
}

/** 기다리는 동안의 표 자리 — 도는 표시와 지금 단계, 그 아래 표 모양의 뼈대. */
const Waiting = ({ text }: WaitingProps) => (
  <div className={styles.waiting}>
    <p className={styles.waitingText} role="status">
      <span className={styles.spinner} aria-hidden="true" />
      {text}
    </p>
    <Skeleton rows={6} columns={3} />
  </div>
);
