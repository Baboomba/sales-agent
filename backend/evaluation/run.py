"""평가 세트를 실제 모델로 돌린다 (docs/eval/README.md).

    scripts/eval.sh qwen2.5-coder:0.5b qwen2.5-coder:1.5b

판정: 정답 SQL 의 열마다, 같은 값의 열이 Agent 결과에 하나 있어야 한다. 행 수도 같아야 한다.
Agent 가 열을 더 붙이는 것(예: 매장 이름에 매출을 곁들임)은 틀린 것으로 보지 않는다.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from app.config import Settings
from app.main import query_limits
from app.query.dependency.impl.ollama_client import ollama_complete
from app.query.dependency.impl.ollama_generator import OllamaSqlGenerator
from app.query.dependency.impl.sqlglot_analyzer import SqlglotAnalyzer
from app.query.dependency.impl.sqlite_sales_database import SqliteSalesDatabase
from app.query.model.question import Question
from app.query.model.run import Completed, Failed, Generated
from app.query.model.terms import TERMS
from app.query.usecase.query_flow import QueryFlow

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"


@dataclass
class Outcome:
    id: str
    type: str
    question: str
    correct: bool
    seconds: float
    attempts: int
    sql: str
    note: str


def normalize(value: object) -> object:
    if isinstance(value, float):
        return round(value, 2)
    return value


def columns_of(rows: list[tuple[object, ...]], ordered: bool) -> list[list[object]]:
    if not rows:
        return []
    width = len(rows[0])
    cols = [[normalize(row[i]) for row in rows] for i in range(width)]
    return cols if ordered else [sorted(c, key=repr) for c in cols]


def matches(gold: list[tuple[object, ...]], got: list[tuple[object, ...]], ordered: bool) -> bool:
    if len(gold) != len(got):
        return False
    got_cols = columns_of(got, ordered)
    return all(col in got_cols for col in columns_of(gold, ordered))


async def evaluate(model: str, settings: Settings) -> list[Outcome]:
    questions = yaml.safe_load((HERE / "questions.yaml").read_text(encoding="utf-8"))
    database = SqliteSalesDatabase(settings.db_path, timeout_seconds=settings.query_timeout_seconds)
    generator = OllamaSqlGenerator(
        ollama_complete(
            base_url=settings.ollama_base_url,
            model=model,
            generation_timeout_seconds=settings.generation_timeout_seconds,
        ),
        timeout_seconds=settings.generation_timeout_seconds,
    )
    flow = QueryFlow(generator, SqlglotAnalyzer(), database, TERMS, query_limits(settings))
    gold_conn = sqlite3.connect(f"file:{settings.db_path}?mode=ro", uri=True)

    outcomes = []
    for q in questions:
        gold = gold_conn.execute(q["sql"]).fetchall()
        started = time.perf_counter()
        steps = flow.start(Question(q["question"]))
        if isinstance(steps, str):
            raise ValueError(f"{q['id']} 질문이 입력 검증에 걸립니다: {steps}")
        events = [e async for e in steps]
        seconds = time.perf_counter() - started
        attempts = max((e.attempt for e in events if isinstance(e, Generated)), default=0)
        last = events[-1]
        sql = next((e.sql for e in reversed(events) if isinstance(e, Generated)), "")
        if isinstance(last, Completed):
            rows = list(last.result.rows)
            correct = matches(gold, rows, q["ordered"])
            note = "" if correct else f"결과 불일치 (정답 {len(gold)}행, 결과 {len(rows)}행)"
        else:
            correct = False
            note = last.reason if isinstance(last, Failed) else "끝나지 않음"
        outcomes.append(
            Outcome(q["id"], q["type"], q["question"], correct, seconds, attempts, sql, note)
        )
        mark = "✔" if correct else "✘"
        print(f"  {mark} {q['id']} {seconds:5.1f}s 시도 {attempts}  {q['question']}", flush=True)
    gold_conn.close()
    return outcomes


@dataclass
class Summary:
    model: str
    accuracy: float
    avg_seconds: float
    retry_rate: float
    failed: list[str]


def summarize(model: str, outcomes: list[Outcome]) -> Summary:
    total = len(outcomes)
    return Summary(
        model=model,
        accuracy=sum(o.correct for o in outcomes) / total,
        avg_seconds=sum(o.seconds for o in outcomes) / total,
        retry_rate=sum(o.attempts > 1 for o in outcomes) / total,
        failed=[o.id for o in outcomes if not o.correct],
    )


async def main(models: list[str]) -> None:
    settings = Settings.from_env()
    models = models or [settings.ollama_model]
    RESULTS_DIR.mkdir(exist_ok=True)
    summaries = []
    for model in models:
        print(f"\n▶ {model}")
        outcomes = await evaluate(model, settings)
        summary = summarize(model, outcomes)
        summaries.append(summary)
        detail = {"summary": asdict(summary), "outcomes": [asdict(o) for o in outcomes]}
        path = RESULTS_DIR / f"{model.replace(':', '_').replace('/', '_')}.json"
        path.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n| 모델 | 정답률 | 평균 시간 | 재생성률 | 틀린 문항 |")
    print("|---|---:|---:|---:|---|")
    for s in summaries:
        failed = ", ".join(s.failed) or "없음"
        print(
            f"| {s.model} | {s.accuracy:.0%} | {s.avg_seconds:.1f}s "
            f"| {s.retry_rate:.0%} | {failed} |"
        )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
