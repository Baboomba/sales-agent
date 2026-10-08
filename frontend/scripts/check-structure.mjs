// 화면 코드의 모양을 본다 — 린트가 못 막는 규칙 (docs/convention/enforcement.md).
// 묶음 폴더의 이름 · 파일 · 하위 폴더 (코드 아키텍처 6.2 · 6.5), 스타일 파일의 색 값 (코드 컨벤션 3절),
// 경고를 끄는 주석 (코드 컨벤션 1.1). 어긴 곳을 모두 적고 실패한다.
//
//   node scripts/check-structure.mjs

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const SRC = new URL("../src/", import.meta.url).pathname;
const PASCAL = /^[A-Z][A-Za-z0-9]*$/;
const LOWER = /^[a-z][a-z0-9-]*$/;
const SUBDIRS = new Set(["components", "__test__"]);
const HEX = /#[0-9a-fA-F]{3,8}\b/;
const SUPPRESSION = /eslint-disable|@ts-ignore|@ts-expect-error|@ts-nocheck/;

const dirs = (path) => readdirSync(path).filter((name) => statSync(join(path, name)).isDirectory());
const files = (path) => readdirSync(path).filter((name) => statSync(join(path, name)).isFile());
const walk = (path) =>
  readdirSync(path).flatMap((name) => {
    const full = join(path, name);
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
const rel = (path) => relative(SRC, path);

/** 묶음 하나 — 이름은 파스칼, <이름>.tsx 와 index.ts, 정해진 파일과 하위 폴더만 (6.2 · 6.5). */
const checkGroup = (path, name, { stateful }) => {
  const problems = [];
  if (!PASCAL.test(name)) problems.push(`${rel(path)} 묶음 폴더 이름은 파스칼이다`);
  const allowed = new Set([
    `${name}.tsx`,
    `${name}.module.css`,
    `${name}.test.tsx`,
    "index.ts",
    ...(stateful ? ["hooks.ts", "service.ts"] : []),
  ]);
  const own = files(path);
  for (const required of [`${name}.tsx`, "index.ts"]) {
    if (!own.includes(required)) problems.push(`${rel(path)} ${required} 가 없다`);
  }
  for (const file of own.filter((file) => !allowed.has(file))) {
    const why = ["hooks.ts", "service.ts"].includes(file)
      ? "components · entities 는 hooks.ts · service.ts 를 두지 않는다"
      : "묶음에 둘 수 없는 파일이다";
    problems.push(`${rel(join(path, file))} ${why}`);
  }
  for (const dir of dirs(path).filter((dir) => !SUBDIRS.has(dir))) {
    problems.push(`${rel(join(path, dir))} 묶음 안의 폴더는 components/ 와 __test__/ 뿐이다`);
  }
  return problems;
};

const groupsIn = (layer, options) =>
  dirs(join(SRC, layer)).flatMap((name) => checkGroup(join(SRC, layer, name), name, options));

const entityGroups = () =>
  dirs(join(SRC, "entities")).flatMap((domain) => [
    ...(LOWER.test(domain) ? [] : [`entities/${domain} 엔티티 묶음 이름은 소문자다`]),
    ...dirs(join(SRC, "entities", domain)).flatMap((name) =>
      checkGroup(join(SRC, "entities", domain, name), name, { stateful: false }),
    ),
  ]);

const lines = (path) => readFileSync(path, "utf8").split("\n");

const hexColors = () =>
  walk(SRC)
    .filter((path) => path.endsWith(".module.css"))
    .flatMap((path) =>
      lines(path).flatMap((line, i) =>
        HEX.test(line) ? [`${rel(path)}:${i + 1} 색은 index.css 의 변수로 쓴다`] : [],
      ),
    );

const suppressions = () =>
  walk(SRC)
    .filter((path) => /\.(ts|tsx)$/.test(path))
    .flatMap((path) =>
      lines(path).flatMap((line, i) =>
        SUPPRESSION.test(line) ? [`${rel(path)}:${i + 1} 경고를 끄는 주석 — 설정에서 이유와 함께 끈다`] : [],
      ),
    );

const problems = [
  ...groupsIn("components", { stateful: false }),
  ...entityGroups(),
  ...groupsIn("features", { stateful: true }),
  ...groupsIn("pages", { stateful: true }),
  ...hexColors(),
  ...suppressions(),
];

for (const problem of problems) console.log(problem);
if (problems.length > 0) {
  console.log(`\n구조 검사 실패 — ${problems.length}곳`);
  process.exit(1);
}
