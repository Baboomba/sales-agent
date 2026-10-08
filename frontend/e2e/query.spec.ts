import { expect, test, type Page } from "@playwright/test";

import { QUESTIONS } from "./scripts.mjs";

// 끝단 시나리오 (docs/design/screen.md 6절). 화면 · 서버 · 시드 DB 는 실제로 돌고, 모델만 가짜다.

const FAKE_OLLAMA = "http://127.0.0.1:11500";

test.beforeEach(async ({ page }) => {
  await fetch(`${FAKE_OLLAMA}/__reset`, { method: "POST" });
  await page.goto("/");
});

const ask = async (page: Page, question: string) => {
  await page.getByRole("textbox", { name: "질문" }).fill(question);
  await page.getByRole("button", { name: "질문하기" }).click();
};

const resultCard = (page: Page) => page.getByRole("region", { name: "결과" });
const processLog = (page: Page) => page.getByRole("list", { name: "처리 기록" });
const stageCards = (page: Page) => page.getByRole("list", { name: "진행 단계" });

test("E2E-01 예시 질문을 누르면 생성 · 검증 · 실행을 거쳐 결과 표와 막대를 보인다 (SCR-R006 · R007 · R012 · R016)", async ({
  page,
}) => {
  await page.getByRole("button", { name: QUESTIONS.topStores }).click();

  await expect(resultCard(page).getByRole("row")).toHaveCount(4);
  await expect(resultCard(page).getByTestId("bar")).toHaveCount(3);
  await expect(stageCards(page)).toContainText("완료 · 3행");
  await expect(processLog(page).getByRole("listitem")).toHaveCount(3);
  await expect(page.getByRole("button", { name: QUESTIONS.topStores })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("tab", { name: "실행한 SQL" }).click();
  await expect(resultCard(page)).toContainText("LIMIT 3");
});

test("E2E-02 공백뿐이면 질문하기를 누를 수 없고, 직접 쓴 질문은 보낸다 (SCR-R005)", async ({
  page,
}) => {
  const input = page.getByRole("textbox", { name: "질문" });
  await input.fill("   ");
  await expect(page.getByRole("button", { name: "질문하기" })).toBeDisabled();

  await ask(page, QUESTIONS.regenerate);
  await expect(resultCard(page).getByRole("row")).toHaveCount(4);
});

test("E2E-03 쓰기 SQL 은 검증에서 거부되고, 사유를 붙여 다시 만들어 성공한다 (QRY-R003 · R006 · SCR-R008)", async ({
  page,
}) => {
  await ask(page, QUESTIONS.regenerate);

  await expect(resultCard(page).getByRole("cell", { name: "배달" })).toBeVisible();
  const entries = processLog(page).getByRole("listitem");
  await expect(entries).toHaveCount(5);
  await expect(entries.nth(1)).toContainText("검증 실패");
  await expect(stageCards(page)).toContainText("시도 2 · 1번 다시 만듦");
});

test("E2E-04 끝내 실패하면 결과 카드와 처리 기록 끝에 사유를 남기고 만든 SQL 을 보인다 (QRY-R007 · SCR-R009 · R010)", async ({
  page,
}) => {
  await ask(page, QUESTIONS.giveUp);

  const alert = resultCard(page).getByRole("alert");
  await expect(alert).toBeVisible();
  const reason = (await alert.textContent()) ?? "";
  await expect(processLog(page).getByRole("listitem").last()).toContainText(reason.slice(0, 20));
  await page.getByRole("tab", { name: "만든 SQL" }).click();
  await expect(resultCard(page)).toContainText("UPDATE orders");
});

test("E2E-05 모델 서버 장애면 다시 만들지 않고 바로 실패를 알린다 (QRY-R013)", async ({ page }) => {
  await ask(page, QUESTIONS.outage);

  await expect(resultCard(page).getByRole("alert")).toContainText("zzz-model");
  await expect(processLog(page).getByRole("listitem")).toHaveCount(1);
});

test("E2E-06 늦은 응답에는 진행 표시가 보이고, 답이 오면 사라진다 (SCR-R002)", async ({ page }) => {
  await ask(page, QUESTIONS.slow);

  await expect(resultCard(page).getByTestId("skeleton")).toBeVisible();
  await expect(resultCard(page).getByRole("status")).toHaveText("SQL 을 만드는 중");
  await expect(page.getByRole("button", { name: "중지" })).toBeVisible();

  await expect(resultCard(page).getByRole("cell", { name: "배달" })).toBeVisible();
  await expect(resultCard(page).getByTestId("skeleton")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "질문하기" })).toBeVisible();
});

test("E2E-07 단계를 받은 뒤 중지해도 묻기 전 모습으로 돌아간다 (SCR-R002)", async ({ page }) => {
  await ask(page, QUESTIONS.hang);
  await expect(processLog(page)).toContainText("검증 실패");
  await page.getByRole("button", { name: "중지" }).click();

  await expect(resultCard(page)).toContainText("질문하거나 예시 질문을 눌러 보세요.");
  await expect(page.getByText("질문하면 처리 기록이 여기에 쌓입니다.")).toBeVisible();
  await expect(page.getByRole("button", { name: "질문하기" })).toBeVisible();
});

test("E2E-08 묻는 동안 칸의 위치 · 크기와 질문하기 단추 모양이 바뀌지 않는다 (SCR-R001 · R004)", async ({
  page,
}) => {
  await page.evaluate(() => {
    const rects = new Set<string>();
    const panels = [
      "aside[aria-label='테이블과 컬럼']",
      "section[aria-label='결과']",
      "aside[aria-label='처리 기록']",
      "ol[aria-label='진행 단계']",
      "form button",
    ];
    const record = () => {
      const shot = panels.map((selector) => {
        const box = document.querySelector(selector)?.getBoundingClientRect();
        return box ? [box.x, box.y, box.width, box.height].map(Math.round).join(",") : "-";
      });
      const button = document.querySelector("form button");
      const look = button ? getComputedStyle(button).opacity : "-";
      rects.add(`${shot.join("|")}|${look}`);
      document.body.dataset.layouts = String(rects.size);
    };
    new MutationObserver(record).observe(document.body, { childList: true, subtree: true });
    record();
  });

  await ask(page, QUESTIONS.topStores);
  await expect(resultCard(page).getByRole("row")).toHaveCount(4);

  // 묻기 전부터 끝까지 본 칸 배치 · 단추 모양의 가짓수 — 하나여야 한다.
  await expect(page.locator("body")).toHaveAttribute("data-layouts", "1");
});

test("E2E-09 테이블과 컬럼을 못 불러오면 안내와 다시 시도가 있고, 다시 시도하면 불러온다 (SCR-R013 · R014)", async ({
  page,
}) => {
  // 다시 시도를 누르기 전까지는 모두 실패시킨다 — 개발 모드의 React 는 불러오기를 두 번 부른다.
  let failing = true;
  await page.route("**/api/schema", async (route) => {
    await (failing ? route.fulfill({ status: 500, body: "zzz" }) : route.continue());
  });
  await page.reload();

  const data = page.getByRole("complementary", { name: "테이블과 컬럼" });
  await expect(data).toContainText("불러오지 못했습니다");
  failing = false;
  await data.getByRole("button", { name: "다시 시도" }).click();
  await expect(data).toContainText("stores");
  await expect(data.locator("details[open]")).toHaveCount(1);
});

test("E2E-10 좁은 화면에서는 탭으로 고른 칸 하나만 보이고 옆으로 밀리지 않는다 (SCR-R015)", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(page.getByRole("tab", { name: "결과" })).toHaveAttribute("aria-selected", "true");
  await expect(resultCard(page)).toBeVisible();
  await expect(page.getByRole("complementary", { name: "처리 기록" })).toBeHidden();

  await page.getByRole("tab", { name: "처리 기록" }).click();
  await expect(page.getByRole("complementary", { name: "처리 기록" })).toBeVisible();
  await expect(resultCard(page)).toBeHidden();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBe(0);
});

test("E2E-11 행 상한을 넘는 결과는 앞부분만 보이고 잘렸다고 알린다 (QRY-R005 · SCR-R011)", async ({
  page,
}) => {
  await ask(page, QUESTIONS.truncated);

  await expect(resultCard(page)).toContainText("앞부분만 보여 줍니다");
  await expect(resultCard(page).getByRole("row")).toHaveCount(201);
});

test("E2E-12 숫자 열의 머리글은 값과 오른쪽 끝이 같고, 막대는 줄마다 같은 자리에서 시작한다 (SCR-R011 · R012)", async ({
  page,
}) => {
  await ask(page, QUESTIONS.topStores);
  await expect(resultCard(page).getByTestId("bar")).toHaveCount(3);

  const measured = await page.evaluate(() => {
    const textRight = (element: Element) => {
      const range = document.createRange();
      range.selectNodeContents(element);
      return Math.round(range.getBoundingClientRect().right);
    };
    const card = document.querySelector("section[aria-label='결과']");
    const header = card?.querySelector("th:last-child");
    const values = [...(card?.querySelectorAll("tbody td:last-child") ?? [])].map(textRight);
    const bars = [...(card?.querySelectorAll("[data-testid='bar']") ?? [])].map((bar) =>
      Math.round(bar.getBoundingClientRect().left),
    );
    return { header: header ? textRight(header) : null, values, bars };
  });

  expect(new Set(measured.values)).toEqual(new Set([measured.header]));
  expect(new Set(measured.bars).size).toBe(1);
});
