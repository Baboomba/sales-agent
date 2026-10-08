/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // 제 폴더 밖은 @/ 로 가리킨다 (코드 아키텍처 6.5). tsconfig.json 의 paths 와 같아야 한다.
  resolve: { alias: { "@": decodeURIComponent(new URL("./src", import.meta.url).pathname) } },
  server: {
    // 개발에서만 /api 를 서버로 넘긴다. 운영은 서버가 화면을 같은 출처에서 내준다.
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
