"""조립 루트. 설정이 유스케이스 · API 에 닿는지, 뜨지 않아야 할 때 뜨지 않는지 본다.

흐름 · 판정 · 응답 모양은 각 층의 테스트가 본다. 여기서는 끼운 것만 본다.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import httpx

from app.config import Settings
from app.main import create_app, query_limits
from app.query.model.failure import QueryLimits
from app.query.model.question import Column, Table
from app.query.model.run import QueryResult
from app.query.model.sql import GeneratedSql
from tests.query.fake import ScriptedAnalyzer, ScriptedDatabase, ScriptedGenerator
from tests.query.support import passing_shape, read_sse

DB_TABLES = (Table("zzz_sales", (Column("zzz_c", "REAL"),)),)
PASSING = passing_shape("zzz_sales")


def client_for(
    settings: Settings,
    generator: ScriptedGenerator,
    analyzer: ScriptedAnalyzer,
    database: ScriptedDatabase,
) -> httpx.AsyncClient:
    app = create_app(settings, generator=generator, analyzer=analyzer, database=database)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


# --- 설정이 닿는 곳 ---------------------------------------------------------


def test_query_limits_come_from_settings() -> None:
    """질의 한도는 설정의 값이다 (설계서 5.3). 값을 모두 다르게 둬 뒤바뀐 구현을 가른다."""
    settings = Settings(
        max_attempts=4, row_limit=9, generation_timeout_seconds=7.5, query_timeout_seconds=2.5
    )
    assert query_limits(settings) == QueryLimits(
        max_attempts=4, row_limit=9, generation_timeout_seconds=7.5, query_timeout_seconds=2.5
    )


async def test_health_reports_the_model_name_from_settings(tmp_path: Path) -> None:
    """헬스 체크의 모델 이름은 설정의 모델 이름이다 (설계서 2.4)."""
    settings = Settings(ollama_model="zzz-model", static_dir=tmp_path / "absent")
    database = ScriptedDatabase(DB_TABLES, [])
    async with client_for(
        settings, ScriptedGenerator([]), ScriptedAnalyzer([]), database
    ) as client:
        response = await client.get("/api/health")
    assert response.json() == {"status": "ok", "model": "zzz-model"}


async def test_flow_uses_the_row_limit_from_settings(tmp_path: Path) -> None:
    """질의 흐름은 설정의 행 상한을 쓴다 — 상한 7 이면 매출 DB 가 8 행을 가져온다 (QRY-R005)."""
    settings = Settings(row_limit=7, static_dir=tmp_path / "absent")
    database = ScriptedDatabase(DB_TABLES, [QueryResult(("zzz_c",), ())])
    generator = ScriptedGenerator([GeneratedSql("zzz sql 1")])
    async with client_for(settings, generator, ScriptedAnalyzer([PASSING]), database) as client:
        await client.post("/api/queries", json={"question": "zzz 질문"})
    assert database.executed == [("zzz sql 1", 8)]


async def test_flow_uses_the_max_attempts_from_settings(tmp_path: Path) -> None:
    """질의 흐름은 설정의 생성 최대 횟수를 쓴다 — 2 면 두 번 실패하고 끝난다 (QRY-R007)."""
    settings = Settings(max_attempts=2, static_dir=tmp_path / "absent")
    generator = ScriptedGenerator(
        [GeneratedSql("zzz sql 1"), GeneratedSql("zzz sql 2"), GeneratedSql("zzz sql 3")]
    )
    writing = replace(PASSING, is_query=False)
    analyzer = ScriptedAnalyzer([writing, writing, writing])
    database = ScriptedDatabase(DB_TABLES, [])
    async with client_for(settings, generator, analyzer, database) as client:
        response = await client.post("/api/queries", json={"question": "zzz 질문"})
    assert len(generator.calls) == 2
    assert read_sse(response.text)[-1][0] == "failed"


# --- 화면 (설계서 5.3 STATIC_DIR) -------------------------------------------


async def test_built_screen_is_served_beside_the_api(tmp_path: Path) -> None:
    """STATIC_DIR 가 있으면 화면을 같은 출처에서 내주고, API 는 가려지지 않는다."""
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<p>zzz 화면</p>", encoding="utf-8")
    settings = Settings(ollama_model="zzz-model", static_dir=static_dir)
    database = ScriptedDatabase(DB_TABLES, [])
    async with client_for(
        settings, ScriptedGenerator([]), ScriptedAnalyzer([]), database
    ) as client:
        screen = await client.get("/")
        health = await client.get("/api/health")
    assert (screen.status_code, screen.text) == (200, "<p>zzz 화면</p>")
    assert health.json() == {"status": "ok", "model": "zzz-model"}


async def test_only_the_api_is_served_without_the_screen(tmp_path: Path) -> None:
    """STATIC_DIR 가 없으면 API 만 뜬다 — 위 테스트의 짝."""
    settings = Settings(static_dir=tmp_path / "absent")
    database = ScriptedDatabase(DB_TABLES, [])
    async with client_for(
        settings, ScriptedGenerator([]), ScriptedAnalyzer([]), database
    ) as client:
        screen = await client.get("/")
        health = await client.get("/api/health")
    assert screen.status_code == 404
    assert health.status_code == 200


async def test_schema_comes_from_the_wired_lookup(tmp_path: Path) -> None:
    """보조 조회도 같은 매출 DB 로 조립한다 (설계서 2.4).

    `/api/schema` 가 그 DB 의 표를 돌려준다.
    """
    settings = Settings(static_dir=tmp_path / "absent")
    database = ScriptedDatabase(DB_TABLES, [])
    async with client_for(
        settings, ScriptedGenerator([]), ScriptedAnalyzer([]), database
    ) as client:
        response = await client.get("/api/schema")
    assert response.json() == {
        "tables": [
            {
                "name": "zzz_sales",
                "description": "",
                "columns": [{"name": "zzz_c", "type": "REAL", "description": ""}],
            }
        ]
    }
