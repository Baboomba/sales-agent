"""조립 루트. 어댑터를 만들어 그래프에 끼우는 유일한 곳이다 (docs/architecture.md 2절).

uv run uvicorn --factory app.main:app_from_env
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.query.adapters.ollama import OllamaSqlGenerator
from app.query.adapters.sqlite import SqliteSalesDatabase
from app.query.api import create_router
from app.query.graph import AgentSettings, SqlAgent
from app.query.ports import SalesDatabase, SqlGenerator


def create_app(
    settings: Settings,
    *,
    generator: SqlGenerator | None = None,
    database: SalesDatabase | None = None,
) -> FastAPI:
    generator = generator or OllamaSqlGenerator(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout_seconds=settings.generation_timeout_seconds,
    )
    database = database or SqliteSalesDatabase(
        settings.db_path, timeout_seconds=settings.query_timeout_seconds
    )
    agent = SqlAgent(
        generator,
        database,
        AgentSettings(max_attempts=settings.max_attempts, row_limit=settings.row_limit),
    )

    app = FastAPI(title="sales-agent")
    app.include_router(create_router(agent, database.schema(), settings.ollama_model))
    # 빌드된 화면을 같은 출처에서 내준다. API 라우트 뒤에 붙여야 /api 를 가리지 않는다.
    if settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="static")
    return app


def app_from_env() -> FastAPI:
    """uvicorn --factory 진입점. import 할 때 앱을 만들지 않아 테스트가 실제 DB 에 묶이지 않는다."""
    return create_app(Settings.from_env())
