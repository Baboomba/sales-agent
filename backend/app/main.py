"""조립 루트. 의존성 구현을 만들어 유스케이스에, 유스케이스를 API 에 끼우는 유일한 곳이다.

uv run uvicorn --factory app.main:app_from_env
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.query.api.router import create_router
from app.query.dependency.impl.ollama_client import ollama_complete
from app.query.dependency.impl.ollama_generator import OllamaSqlGenerator
from app.query.dependency.impl.sqlglot_analyzer import SqlglotAnalyzer
from app.query.dependency.impl.sqlite_sales_database import SqliteSalesDatabase
from app.query.dependency.sales_database import SalesDatabase
from app.query.dependency.sql_analyzer import SqlAnalyzer
from app.query.dependency.sql_generator import SqlGenerator
from app.query.model.failure import QueryLimits
from app.query.model.terms import TERMS
from app.query.rules.limits import check_limits
from app.query.usecase.lookup import Lookup
from app.query.usecase.query_flow import QueryFlow


def query_limits(settings: Settings) -> QueryLimits:
    """설정에서 질의 한도를 꺼낸다 (설계서 5.3)."""
    return QueryLimits(
        max_attempts=settings.max_attempts,
        row_limit=settings.row_limit,
        generation_timeout_seconds=settings.generation_timeout_seconds,
        query_timeout_seconds=settings.query_timeout_seconds,
    )


def create_app(
    settings: Settings,
    *,
    generator: SqlGenerator | None = None,
    analyzer: SqlAnalyzer | None = None,
    database: SalesDatabase | None = None,
) -> FastAPI:
    """의존성을 받지 않은 자리는 실제 구현으로 채운다. 테스트는 가짜를 넘긴다."""
    generator = generator or OllamaSqlGenerator(
        ollama_complete(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.generation_timeout_seconds,
        )
    )
    analyzer = analyzer or SqlglotAnalyzer()
    database = database or SqliteSalesDatabase(
        settings.db_path, timeout_seconds=settings.query_timeout_seconds
    )
    flow = QueryFlow(generator, analyzer, database, TERMS, query_limits(settings))
    lookup = Lookup(database, TERMS)

    app = FastAPI(title="sales-agent")
    app.include_router(create_router(flow, lookup, settings.ollama_model))
    # 빌드된 화면을 같은 출처에서 내준다. API 경로 뒤에 붙여야 /api 를 가리지 않는다.
    if settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="static")
    return app


def app_from_env() -> FastAPI:
    """uvicorn --factory 진입점. import 할 때 앱을 만들지 않아 테스트가 실제 DB 에 묶이지 않는다."""
    settings = Settings.from_env()
    # QRY-R016 지킬 수 없는 한도면 서버가 뜨지 않는다.
    reason = check_limits(query_limits(settings))
    if reason is not None:
        raise ValueError(reason)
    return create_app(settings)
