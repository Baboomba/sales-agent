"""설정 — 환경변수를 읽는다 (설계서 5.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings

# 구현의 상수와 무관한 기준 — 이 파일은 backend/tests/ 에 있다.
BACKEND = Path(__file__).resolve().parent.parent


def test_settings_are_read_from_their_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """설정마다 설계서 5.3 의 이름으로 읽는다. 값을 모두 다르게 둬 이름이 뒤바뀐 구현을 가른다."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://zzz-host:1")
    monkeypatch.setenv("OLLAMA_MODEL", "zzz-model")
    monkeypatch.setenv("GENERATION_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("SALES_DB_PATH", "/zzz/sales.db")
    monkeypatch.setenv("MAX_ATTEMPTS", "4")
    monkeypatch.setenv("ROW_LIMIT", "9")
    monkeypatch.setenv("QUERY_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("STATIC_DIR", "/zzz/static")
    assert Settings.from_env() == Settings(
        ollama_base_url="http://zzz-host:1",
        ollama_model="zzz-model",
        generation_timeout_seconds=7.5,
        db_path=Path("/zzz/sales.db"),
        max_attempts=4,
        row_limit=9,
        query_timeout_seconds=2.5,
        static_dir=Path("/zzz/static"),
    )


def test_defaults_are_the_design_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """환경변수가 없으면 설계서 5.3 의 기본값이다. 경로는 backend 아래다."""
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("GENERATION_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("SALES_DB_PATH", raising=False)
    monkeypatch.delenv("MAX_ATTEMPTS", raising=False)
    monkeypatch.delenv("ROW_LIMIT", raising=False)
    monkeypatch.delenv("QUERY_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("STATIC_DIR", raising=False)
    assert Settings.from_env() == Settings(
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5-coder:1.5b",
        generation_timeout_seconds=15,
        db_path=BACKEND / "data" / "sales.db",
        max_attempts=3,
        row_limit=200,
        query_timeout_seconds=5,
        static_dir=BACKEND / "static",
    )
