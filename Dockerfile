# 산출물은 이미지 하나다. 화면을 빌드해 서버 이미지에 담고, 서버가 같은 출처에서 내준다.

# --- 화면 빌드 ------------------------------------------------------------
FROM node:24-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 서버 -----------------------------------------------------------------
FROM python:3.13-slim AS app
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app

# 의존성 층을 소스와 나눠 둔다. 소스만 바뀌면 이 층을 다시 받지 않는다.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev

COPY backend/app ./app
COPY backend/scripts ./scripts
# DB 파일은 저장소에 없다. 고정 시드로 같은 파일을 만든다 (docs/design/data.md).
RUN python scripts/seed.py
COPY --from=web /web/dist ./static

RUN useradd --create-home --uid 10001 agent && chown -R agent /app
USER agent

ENV OLLAMA_BASE_URL=http://ollama:11434
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["uvicorn", "--factory", "app.main:app_from_env", "--host", "0.0.0.0", "--port", "8000"]
