"""환경변수 설정 (docs/design/query.md 5절). 수를 코드에 박지 않고 여기서 받는다."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:1.5b"
    generation_timeout_seconds: float = 15
    db_path: Path = field(default_factory=lambda: BACKEND_DIR / "data" / "sales.db")
    max_attempts: int = 3
    row_limit: int = 200
    query_timeout_seconds: float = 5
    static_dir: Path = field(default_factory=lambda: BACKEND_DIR / "static")

    @classmethod
    def from_env(cls) -> Settings:
        defaults = cls()
        return cls(
            ollama_base_url=_env("OLLAMA_BASE_URL", defaults.ollama_base_url),
            ollama_model=_env("OLLAMA_MODEL", defaults.ollama_model),
            generation_timeout_seconds=float(
                _env("GENERATION_TIMEOUT_SECONDS", str(defaults.generation_timeout_seconds))
            ),
            db_path=Path(_env("SALES_DB_PATH", str(defaults.db_path))),
            max_attempts=int(_env("MAX_ATTEMPTS", str(defaults.max_attempts))),
            row_limit=int(_env("ROW_LIMIT", str(defaults.row_limit))),
            query_timeout_seconds=float(
                _env("QUERY_TIMEOUT_SECONDS", str(defaults.query_timeout_seconds))
            ),
            static_dir=Path(_env("STATIC_DIR", str(defaults.static_dir))),
        )
