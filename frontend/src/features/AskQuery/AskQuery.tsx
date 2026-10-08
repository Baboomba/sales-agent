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
  const { question, setQuestion, events, running, ask, stop } = useAskQuery();
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
        onChange={setQuestion}
        onAsk={() => void ask(question)}
        onStop={stop}
      />
      <Examples examples={examples} running={running} onPick={askExample} />
      {events.length > 0 && <Progress events={events} running={running} />}
      {sql && <SqlSection event={sql} />}
      {done && <ResultSection event={done} />}
    </div>
  );
};

interface QuestionFormProps {
  question: string;
  running: boolean;
  onChange: (question: string) => void;
  onAsk: () => void;
  onStop: () => void;
}

/** 질문 입력칸과 질문하기 · 중지 단추. */
const QuestionForm = ({ question, running, onChange, onAsk, onStop }: QuestionFormProps) => {
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
      {running ? (
        <button type="button" onClick={onStop}>
          중지
        </button>
      ) : (
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
  running: boolean;
}

const Progress = ({ events, running }: ProgressProps) => (
  <>
    <h2>진행</h2>
    <QuerySteps events={events} running={running} />
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
