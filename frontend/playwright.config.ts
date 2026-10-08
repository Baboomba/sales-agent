import { defineConfig, devices } from "@playwright/test";

// 끝단 테스트 (docs/design/screen.md 6절). 가짜 모델 서버 · 실제 서버(시드 DB) · 화면을 띄우고
// 브라우저로 시나리오를 돈다. 언어 모델은 부르지 않는다 (NFR-005). 실행은 scripts/e2e.sh.
const FAKE_OLLAMA = 11500;
const SERVER = 8100;
const SCREEN = 5180;

export default defineConfig({
  testDir: "e2e",
  // 시나리오가 가짜 모델의 시도 수를 함께 쓴다 — 하나씩 돈다.
  workers: 1,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${SCREEN}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
  ],
  webServer: [
    {
      command: `node e2e/fake-ollama.mjs ${FAKE_OLLAMA}`,
      url: `http://127.0.0.1:${FAKE_OLLAMA}/__health`,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `uv run uvicorn --factory app.main:app_from_env --port ${SERVER}`,
      cwd: "../backend",
      url: `http://127.0.0.1:${SERVER}/api/health`,
      env: {
        OLLAMA_BASE_URL: `http://127.0.0.1:${FAKE_OLLAMA}`,
        OLLAMA_MODEL: "zzz-model",
      },
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${SCREEN} --strictPort`,
      url: `http://127.0.0.1:${SCREEN}`,
      env: { API_URL: `http://127.0.0.1:${SERVER}` },
      reuseExistingServer: !process.env.CI,
    },
  ],
});
