import type { FormEvent } from "react";

import type { QueryEvent } from "@/api/types/query";
import { QueryResult } from "@/entities/query/QueryResult";
import { QuerySql } from "@/entities/query/QuerySql";
import { QuerySteps } from "@/entities/query/QuerySteps";

import styles from "./AskQuery.module.css";
import { useAskQuery, useExamples } from "./hooks";
import {
  QUESTION_MAX_LENGTH,
  doneEvent,
  latestSql,
  questionToSend,
  sqlHeading,
  type DoneEvent,
  type SqlEvent,
} from "./service";

/** 질문하고 진행 · SQL · 결과를 받아 본다 (FR-001 · FR-002 · FR-007). */
export const AskQuery = () => {
  const { question, setQuestion, events, running, pending, ask, stop } = useAskQuery();
  const examples = useExamples();
  const sql = latestSql(events);
  const done = doneEvent(events);

  const askExample = (example: string) => {
    setQuestion(example);
    void ask(example);
  };

  return (
    <div className={styles.ask}>
      <QuestionForm
        question={question}
        running={running}
        pending={pending}
        onChange={setQuestion}
        onAsk={() => void ask(question)}
        onStop={stop}
      />
      <Examples examples={examples} running={running} onPick={askExample} />
      <div className={styles.output}>
        {(pending || events.length > 0) && <Progress events={events} pending={pending} />}
        {sql && <SqlSection event={sql} />}
        {done && <ResultSection event={done} />}
      </div>
    </div>
  );
};

interface QuestionFormProps {
  question: string;
  running: boolean;
  /** 응답이 늦어 중지를 보일 때. 빠른 응답에는 단추가 바뀌지 않는다 (#63). */
  pending: boolean;
  onChange: (question: string) => void;
  onAsk: () => void;
  onStop: () => void;
}

/** 질문 입력칸과 질문하기 · 중지 단추. */
const QuestionForm = ({
  question,
  running,
  pending,
  onChange,
  onAsk,
  onStop,
}: QuestionFormProps) => {
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    onAsk();
  };

  return (
    <form className={styles.form} onSubmit={onSubmit}>
      <label htmlFor="question" className={styles.srOnly}>
        질문
      </label>
      <input
        id="question"
        value={question}
        maxLength={QUESTION_MAX_LENGTH}
        placeholder="예: 매출 상위 3개 매장은?"
        onChange={(e) => onChange(e.target.value)}
        disabled={running}
      />
      {pending ? (
        <button type="button" onClick={onStop}>
          중지
        </button>
      ) : (
        // 묻는 동안 끄지 않는다 — 빠른 응답에 단추가 흐려졌다 돌아와 깜빡인다 (#63). 두 번 보내기는 ask 가 막는다.
        <button type="submit" disabled={questionToSend(question) === null}>
          질문하기
        </button>
      )}
    </form>
  );
};

interface ExamplesProps {
  examples: string[];
  running: boolean;
  onPick: (example: string) => void;
}

/** 누르면 바로 묻는 예시 질문 (FR-007). */
const Examples = ({ examples, running, onPick }: ExamplesProps) => (
  <div className={styles.examples}>
    {examples.map((example) => (
      <button key={example} type="button" disabled={running} onClick={() => onPick(example)}>
        {example}
      </button>
    ))}
  </div>
);

interface ProgressProps {
  events: QueryEvent[];
  pending: boolean;
}

const Progress = ({ events, pending }: ProgressProps) => (
  <>
    <h2>진행</h2>
    <QuerySteps events={events} running={pending} />
  </>
);

interface SqlSectionProps {
  event: SqlEvent;
}

const SqlSection = ({ event }: SqlSectionProps) => (
  <>
    <h2>{sqlHeading(event)}</h2>
    <QuerySql sql={event.sql} />
  </>
);

interface ResultSectionProps {
  event: DoneEvent;
}

const ResultSection = ({ event }: ResultSectionProps) => (
  <>
    <h2>결과</h2>
    <QueryResult columns={event.columns} rows={event.rows} truncated={event.truncated} />
  </>
);
