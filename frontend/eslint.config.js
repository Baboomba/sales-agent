import js from "@eslint/js";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

// 계층 경계 (docs/convention/code-architecture.md 6.6). 경고로 두지 않는다.
const UP = { group: ["../*"], message: "제 폴더 밖은 @/ 로 가리킨다 (코드 아키텍처 6.5)." };
const INSIDE = {
  group: ["@/components/*/*", "@/entities/*/*/*", "@/features/*/*", "@/pages/*/*"],
  message: "묶음은 index.ts 로만 가져다 쓴다 (코드 아키텍처 6.6).",
};
// 서버 호출은 api/ 의 무엇이든이다. 응답 타입(api/types/)만 엔티티가 쓴다. 목록으로 박으면
// api/<도메인>.ts 를 더할 때 경계가 조용히 풀린다.
const SERVER = ["@/api/*", "!@/api/types", "!@/api/types/*"];

/** 계층마다 가져다 쓰지 못하는 것. 아래는 위를 모른다 (코드 아키텍처 6.1). */
const restrict = (forbidden, message) => ({
  "no-restricted-imports": [
    "error",
    { patterns: [UP, INSIDE, ...(forbidden.length ? [{ group: forbidden, message }] : [])] },
  ],
});

// 함수는 화살표 함수로만 쓴다 (코드 컨벤션 3절).
const ARROW_ONLY = "함수는 화살표 함수로 쓴다 (코드 컨벤션 3절).";

export default tseslint.config(
  { ignores: ["dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.strict, jsxA11y.flatConfigs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/no-explicit-any": "error",
      "no-restricted-syntax": [
        "error",
        { selector: "FunctionDeclaration", message: ARROW_ONLY },
        { selector: "FunctionExpression", message: ARROW_ONLY },
      ],
      ...restrict([], ""),
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "서버는 api/ 에서만 부른다 (코드 아키텍처 6.3)." },
      ],
    },
  },
  {
    files: ["src/api/**"],
    rules: { "no-restricted-globals": "off" },
  },
  {
    files: ["src/features/**"],
    rules: restrict(["@/pages/*"], "기능은 화면을 모른다."),
  },
  {
    files: ["src/entities/**"],
    rules: restrict(
      ["@/pages/*", "@/features/*", ...SERVER],
      "엔티티는 화면 · 기능 · 서버 호출을 모른다. 응답 타입(@/api/types/*)만 쓴다.",
    ),
  },
  {
    files: ["src/components/**"],
    rules: restrict(
      ["@/pages/*", "@/features/*", "@/entities/*", "@/api/*", "@/context/*", "@/common/values"],
      "부품은 도메인을 모른다.",
    ),
  },
  {
    // 테스트는 묶음 속을 들여다본다 (코드 아키텍처 6.6).
    files: ["src/**/*.test.{ts,tsx}", "src/**/__test__/**"],
    rules: { "no-restricted-imports": ["error", { patterns: [UP] }] },
  },
);
