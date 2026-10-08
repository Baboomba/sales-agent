import js from "@eslint/js";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

// 규칙과 막는 장치의 표는 docs/convention/enforcement.md 에 있다. 경고로 두지 않는다 —
// 린트는 --max-warnings 0 · --no-inline-config 로 돈다(경고 · 끄는 주석도 실패).

// 계층 경계 (docs/convention/code-architecture.md 6.6).
const UP = { group: ["../*"], message: "제 폴더 밖은 @/ 로 가리킨다 (코드 아키텍처 6.5)." };
const INSIDE = {
  group: ["@/components/*/*", "@/entities/*/*/*", "@/features/*/*", "@/pages/*/*"],
  message: "묶음은 index.ts 로만 가져다 쓴다 (코드 아키텍처 6.6).",
};
// 서버 호출은 api/ 의 무엇이든이다. 응답 타입(api/types/)만 엔티티가 쓴다. 목록으로 박으면
// api/<도메인>.ts 를 더할 때 경계가 조용히 풀린다.
const SERVER = ["@/api/*", "!@/api/types", "!@/api/types/*"];

/** 계층마다 가져다 쓰지 못하는 것. 아래는 위를 모른다 (코드 아키텍처 6.1). */
const restrict = (...rules) => ({
  "no-restricted-imports": [
    "error",
    {
      patterns: [UP, INSIDE, ...rules.map(([group, message]) => ({ group, message }))],
    },
  ],
});

const FEATURE_IMPORTS = [["@/pages/*"], "기능은 화면을 모른다."];
const SERVICE_IMPORTS = [
  ["react", "react/*", "react-dom", "react-dom/*", ...SERVER],
  "service.ts 는 React 도 서버 호출도 모른다 — 아무것도 띄우지 않고 테스트된다 (코드 아키텍처 6.2).",
];

// 문법으로 막는 것. ESLint 는 이 규칙의 목록을 덮어쓰므로, 파일 종류마다 조각을 모아 건다.
const ARROW_ONLY = "함수는 화살표 함수로 쓴다 (코드 컨벤션 3절).";
const BASE = [
  { selector: "FunctionDeclaration", message: ARROW_ONLY },
  { selector: "FunctionExpression", message: ARROW_ONLY },
  {
    selector: "ExportDefaultDeclaration",
    message: "이름 있는 내보내기만 쓴다 (코드 컨벤션 3절).",
  },
  {
    selector: "JSXAttribute[name.name='style']",
    message:
      "인라인 스타일을 쓰지 않는다. CSS Modules 와 index.css 의 변수를 쓴다 (코드 컨벤션 3절).",
  },
];
// 기능의 .tsx 에는 훅 정의 · 순수 함수를 두지 않는다 — hooks.ts · service.ts 로 (코드 아키텍처 6.2).
const FEATURE_VIEW = [
  {
    selector:
      ":matches(Program, ExportNamedDeclaration) > VariableDeclaration > VariableDeclarator[id.name=/^use[A-Z]/]",
    message: "훅 정의는 hooks.ts 에 둔다 (코드 아키텍처 6.2).",
  },
  {
    selector:
      ":matches(Program, ExportNamedDeclaration) > VariableDeclaration > VariableDeclarator[id.name=/^[a-z]/] > ArrowFunctionExpression",
    message: "순수 함수는 service.ts 에 둔다. .tsx 에는 컴포넌트만 둔다 (코드 아키텍처 6.2).",
  },
];
// 테스트의 흐름에 if · 반복을 넣지 않는다 — 여러 경우는 it.each 나 테스트를 나눠 쓴다 (테스트 규칙 5절).
// 테스트 안에 정의한 함수(콜백 등)의 속은 보지 않는다.
const TEST_FLOW = [
  "IfStatement",
  "ForStatement",
  "ForOfStatement",
  "ForInStatement",
  "WhileStatement",
  "DoWhileStatement",
].map((statement) => ({
  selector: `CallExpression[callee.name=/^(it|test)$/] > :function > BlockStatement > ${statement}`,
  message: "테스트의 흐름에 if · 반복을 넣지 않는다 (테스트 규칙 5절).",
}));
// 스타일은 테스트하지 않는다 — 브라우저에서 잰다 (테스트 규칙 7.2).
const NO_STYLE =
  "스타일(클래스 · style · 정렬 속성)은 테스트하지 않는다. 브라우저에서 잰다 (테스트 규칙 7.2).";
const TEST_STYLE = [
  {
    selector: "MemberExpression[property.name=/^(className|classList|style)$/]",
    message: NO_STYLE,
  },
  { selector: "CallExpression[callee.name='getComputedStyle']", message: NO_STYLE },
  {
    selector: "CallExpression[callee.property.name=/^(toHaveStyle|toHaveClass)$/]",
    message: NO_STYLE,
  },
];
const syntax = (...groups) => ({ "no-restricted-syntax": ["error", ...groups.flat()] });

const TESTS = ["src/**/*.test.{ts,tsx}", "src/**/__test__/**"];

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
      // props 타입은 interface 로 둔다 (코드 컨벤션 3절).
      "@typescript-eslint/consistent-type-definitions": ["error", "interface"],
      // as 단언은 바깥 JSON 의 경계(api/)에서만 (코드 컨벤션 3절). as const 는 단언이 아니라 된다.
      "@typescript-eslint/consistent-type-assertions": ["error", { assertionStyle: "never" }],
      ...syntax(BASE),
      ...restrict(),
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "서버는 api/ 에서만 부른다 (코드 아키텍처 6.3)." },
      ],
    },
  },
  {
    // 판별 유니온은 switch 로 끝까지 다룬다 (코드 컨벤션 3절) — 타입 정보가 있어야 본다.
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: { parserOptions: { projectService: true } },
    rules: { "@typescript-eslint/switch-exhaustiveness-check": "error" },
  },
  {
    // 도구 설정 파일과 CSS Modules 타입 선언만 기본 내보내기를 쓴다 (코드 컨벤션 3절).
    files: ["vite.config.ts", "src/**/*.d.ts"],
    rules: syntax(BASE.filter((item) => item.selector !== "ExportDefaultDeclaration")),
  },
  {
    files: ["src/api/**"],
    rules: {
      "no-restricted-globals": "off",
      "@typescript-eslint/consistent-type-assertions": "off",
    },
  },
  {
    files: ["src/features/**"],
    rules: restrict(FEATURE_IMPORTS),
  },
  {
    files: ["src/features/**/*.tsx"],
    ignores: TESTS,
    rules: syntax(BASE, FEATURE_VIEW),
  },
  {
    files: ["src/**/service.ts"],
    rules: restrict(FEATURE_IMPORTS, SERVICE_IMPORTS),
  },
  {
    files: ["src/entities/**"],
    rules: restrict([
      ["@/pages/*", "@/features/*", ...SERVER],
      "엔티티는 화면 · 기능 · 서버 호출을 모른다. 응답 타입(@/api/types/*)만 쓴다.",
    ]),
  },
  {
    files: ["src/components/**"],
    rules: restrict([
      ["@/pages/*", "@/features/*", "@/entities/*", "@/api/*", "@/context/*", "@/common/values"],
      "부품은 도메인을 모른다.",
    ]),
  },
  {
    // 테스트는 묶음 속을 들여다본다 (코드 아키텍처 6.6). 목은 쓰지 않는다 — 가짜는 한 자리에 (테스트 규칙 7.1).
    files: TESTS,
    rules: {
      "no-restricted-imports": ["error", { patterns: [UP] }],
      ...syntax(BASE, TEST_FLOW, TEST_STYLE),
      "no-restricted-properties": [
        "error",
        ...["mock", "fn", "spyOn", "doMock"].map((property) => ({
          object: "vi",
          property,
          message:
            "목을 쓰지 않는다. 가짜는 src/api/__test__/fakeServer.ts 한 자리에 둔다 (테스트 규칙 7.1).",
        })),
      ],
    },
  },
);
