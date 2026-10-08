"""조립 루트가 설정을 실제 구현에 넘기는지. 가짜로는 보이지 않아 실제 연결 · 파일에 닿는다.

언어 모델은 부르지 않는다 — 응답하지 않는 로컬 서버를 모델 서버 자리에 둔다 (NFR-005).
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.config import Settings
from app.main import app_from_env, create_app
from app.query.model.question import Column, Table
from app.query.model.sql import GeneratedSql
from app.query.rules.retry import after_unexpected_error
from tests.query.fake import ScriptedAnalyzer, ScriptedDatabase, ScriptedGenerator
from tests.query.support import passing_shape, read_sse

pytestmark = pytest.mark.integration

ENDLESS = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT COUNT(*) FROM n"
# 표를 참조하지 않고 판정을 통과하는 SQL 구성.
PASSING = passing_shape(cte_names=("n",))


async def ask(
    settings: Settings,
    *,
    generator: ScriptedGenerator | None = None,
    analyzer: ScriptedAnalyzer | None = None,
    database: ScriptedDatabase | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """비워 둔 의존성은 조립 루트가 실제 구현으로 채운다."""
    app = create_app(settings, generator=generator, analyzer=analyzer, database=database)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/queries", json={"question": "zzz 질문"})
    return read_sse(response.text)


async def test_ollama_address_and_generation_timeout_reach_the_generator(tmp_path: Path) -> None:
    """설정의 주소 · 생성 제한 시간이 Ollama 연결에 닿는다 (설계서 5.3).

    응답하지 않는 서버에 0.2초로 닿으면 시간 초과로 끝나고, 사유에 그 제한 시간이 있다
    (QRY-R013). 주소가 안 닿으면 연결 실패, 제한 시간이 안 닿으면 끝나지 않는다.
    """

    async def silent(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await asyncio.Event().wait()

    server = await asyncio.start_server(silent, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    settings = Settings(
        ollama_base_url=f"http://127.0.0.1:{port}",
        generation_timeout_seconds=0.2,
        # 실행 제한 시간은 아래 상한(10초)보다 길게 둔다 — 두 제한 시간을 바꿔 끼운 구현을 가른다.
        query_timeout_seconds=30,
        max_attempts=1,
        static_dir=tmp_path / "absent",
    )
    try:
        events = await asyncio.wait_for(
            ask(settings, analyzer=ScriptedAnalyzer([]), database=ScriptedDatabase((), [])),
            timeout=10,
        )
    finally:
        server.close()
    assert len(events) == 1
    name, data = events[0]
    assert name == "failed"
    assert "0.2" in data["reason"]


async def test_query_timeout_reaches_the_database(tmp_path: Path) -> None:
    """설정의 실행 제한 시간이 매출 DB 에 닿는다 (설계서 5.3).

    끝나지 않는 재귀 질의가 0.2초에 끊겨 실행 시간 초과로 끝나고, 사유에 더 가벼운 질의로
    바꾸라는 안내가 있다 (QRY-R009). 제한 시간이 안 닿으면 DB 가 예외를 던져 다른 실패가 된다.
    """
    db_path = tmp_path / "zzz.db"
    sqlite3.connect(db_path).close()
    settings = Settings(
        db_path=db_path,
        query_timeout_seconds=0.2,
        # 생성 제한 시간은 아래 상한(2초)보다 길게 둔다 — 두 제한 시간을 바꿔 끼운 구현을 가른다.
        generation_timeout_seconds=3,
        max_attempts=1,
        static_dir=tmp_path / "absent",
    )
    events = await asyncio.wait_for(
        ask(
            settings,
            generator=ScriptedGenerator([GeneratedSql(ENDLESS)]),
            analyzer=ScriptedAnalyzer([PASSING]),
        ),
        timeout=2,
    )
    name, data = events[-1]
    assert name == "failed"
    assert "가벼운" in data["reason"]


DB_TABLES = (Table("zzz_sales", (Column("zzz_c", "REAL"),)),)


def use_env(
    monkeypatch: pytest.MonkeyPatch, *, db_path: Path, generation_timeout: str, static_dir: Path
) -> None:
    """서버가 읽는 환경변수를 모두 정한다 — 테스트를 돌리는 셸의 값이 새어 들지 않게."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://zzz-host:1")
    monkeypatch.setenv("OLLAMA_MODEL", "zzz-model")
    monkeypatch.setenv("GENERATION_TIMEOUT_SECONDS", generation_timeout)
    monkeypatch.setenv("SALES_DB_PATH", str(db_path))
    monkeypatch.setenv("MAX_ATTEMPTS", "3")
    monkeypatch.setenv("ROW_LIMIT", "200")
    monkeypatch.setenv("QUERY_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("STATIC_DIR", str(static_dir))


def empty_db(tmp_path: Path) -> Path:
    path = tmp_path / "zzz.db"
    sqlite3.connect(path).close()
    return path


# --- 뜨지 않아야 할 때 (QRY-R016 · 설계서 5.3) ------------------------------


def test_app_from_env_starts_with_limits_within_a_minute(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """기본 한도 3 × (15 + 5) = 60초면 뜬다 — 아래 두 거부의 짝."""
    use_env(
        monkeypatch,
        db_path=empty_db(tmp_path),
        generation_timeout="15",
        static_dir=tmp_path / "absent",
    )
    assert isinstance(app_from_env(), FastAPI)


def test_qry_r016_app_from_env_refuses_limits_over_a_minute(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """QRY-R016 생성 제한 시간 30초면 최악 3 × (30 + 5) = 105초라 서버가 뜨지 않는다."""
    use_env(
        monkeypatch,
        db_path=empty_db(tmp_path),
        generation_timeout="30",
        static_dir=tmp_path / "absent",
    )
    with pytest.raises(ValueError, match="105"):
        app_from_env()


def test_app_from_env_refuses_a_missing_db_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SALES_DB_PATH 의 파일이 없으면 서버가 뜨지 않는다 (설계서 5.3)."""
    use_env(
        monkeypatch,
        db_path=tmp_path / "zzz-absent.db",
        generation_timeout="15",
        static_dir=tmp_path / "absent",
    )
    with pytest.raises(FileNotFoundError, match=r"zzz-absent\.db"):
        app_from_env()


async def test_real_generator_is_wired_to_the_ollama_address(tmp_path: Path) -> None:
    """생성기를 넘기지 않으면 설정의 주소로 Ollama 에 닿는 생성기를 조립한다.

    닿지 않는 주소면 모델 서버 장애(연결 실패)로 끝난다 (QRY-R013). 연결을 빠뜨리면 생성기가
    예외를 던져 「예상하지 못한 오류」로 끝나므로 둘을 가른다. 언어 모델은 부르지 않는다.
    """
    settings = Settings(
        ollama_base_url="http://127.0.0.1:9",
        generation_timeout_seconds=2,
        static_dir=tmp_path / "absent",
    )
    app = create_app(
        settings,
        analyzer=ScriptedAnalyzer([]),
        database=ScriptedDatabase(DB_TABLES, []),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/queries", json={"question": "zzz 질문"})
    events = read_sse(response.text)
    assert len(events) == 1
    name, data = events[0]
    assert name == "failed"
    assert data["reason"] != after_unexpected_error().reason
