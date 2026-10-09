# shellcheck shell=bash
# scripts/ 가 함께 쓰는 것 — 출력 모양과 모델 서버 띄우기. source 로 읽는다.

model="${OLLAMA_MODEL:-qwen2.5-coder:1.5b}"
ollama_url="${OLLAMA_BASE_URL:-http://localhost:11434}"
ollama_container="sales-agent-ollama"

step() { printf '\n\033[1m▶ %s\033[0m\n' "$1"; }
ok() { printf '  \033[32m✔\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m⚠\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m✘\033[0m %s\n' "$1" >&2; exit 1; }
has() { command -v "$1" >/dev/null 2>&1; }
model_server_up() { curl -sf -m 3 "$ollama_url/api/tags" >/dev/null; }
model_ready() { curl -sf -m 3 "$ollama_url/api/tags" | grep -q "\"name\":\"$model\""; }

# 모델 서버를 띄운다 — 떠 있으면 그것을, 없으면 이 컴퓨터의 Ollama 를, 그것도 없으면 도커로.
ensure_model_server() {
  if model_server_up; then
    ok "이미 떠 있습니다 ($ollama_url)"
  elif has ollama; then
    (ollama serve >/dev/null 2>&1 &)
    for _ in $(seq 1 15); do model_server_up && break; sleep 1; done
    model_server_up || fail "ollama serve 가 뜨지 않습니다 — 터미널에서 ollama serve 를 직접 실행해 보세요"
    ok "이 컴퓨터의 Ollama 를 띄웠습니다 (GPU 를 씁니다)"
  elif has docker && docker info >/dev/null 2>&1; then
    if docker container inspect "$ollama_container" >/dev/null 2>&1; then
      docker start "$ollama_container" >/dev/null
    else
      docker run -d --name "$ollama_container" -p 11434:11434 \
        -v sales-agent_ollama:/root/.ollama ollama/ollama:latest >/dev/null
    fi
    for _ in $(seq 1 30); do model_server_up && break; sleep 1; done
    model_server_up || fail "도커의 모델 서버가 뜨지 않습니다 — docker logs $ollama_container"
    ok "도커로 띄웠습니다 (컨테이너 $ollama_container, GPU 없이 CPU)"
  else
    fail "모델 서버를 띄울 수 없습니다 — Ollama(https://ollama.com)를 설치하거나 도커를 켜세요"
  fi
}
