import { fireEvent, render, screen } from "@testing-library/react";

import { type FakeReply, fakeServer, sse } from "@/api/__test__/fakeServer";
import { Query } from "@/pages/Query";

const install = (queries: FakeReply[]) => {
  const server = fakeServer({
    "/api/health": [{ json: { status: "ok", model: "zzz-model" } }],
    "/api/schema": [{ json: { tables: [] } }],
    "/api/examples": [{ json: { questions: ["zzz 예시"] } }],
    "/api/queries": queries,
  });
  vi.stubGlobal("fetch", server.fetch);
};

afterEach(() => {
  vi.unstubAllGlobals();
});

const PANELS = [
  ["complementary", "표와 열"],
  ["region", "결과"],
  ["complementary", "처리 기록"],
] as const;

/** 칸이 모두 그 자리에 있는지. 크기 자체는 CSS 가 고정하고 브라우저에서 잰다. */
const expectPanels = () => {
  for (const [role, name] of PANELS) expect(screen.getByRole(role, { name })).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "진행 단계" })).toBeInTheDocument();
};

describe("Query", () => {
  it("묻기 전 · 완료 · 실패에서 칸이 늘 같은 자리에 있다 (SCR-R001)", async () => {
    install([
      { sse: sse(["done", { columns: ["zzz_a"], rows: [["zzz 값"]], truncated: false }]) },
      { sse: sse(["failed", { reason: "zzz 사유" }]) },
    ]);
    render(<Query />);
    expectPanels();

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));
    await screen.findByRole("cell", { name: "zzz 값" });
    expectPanels();

    fireEvent.click(screen.getByRole("button", { name: "zzz 예시" }));
    await screen.findByRole("alert");
    expectPanels();
  });

  it("묻는 중에도 칸이 그 자리에 있다 (SCR-R001)", async () => {
    install([{ hang: true }]);
    render(<Query />);

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));
    expectPanels();
    const stop = await screen.findByRole("button", { name: "중지" });
    expectPanels();
    fireEvent.click(stop);
    expectPanels();
  });

  // 숨김은 data-mobile-hidden 으로 본다. jsdom 은 미디어 쿼리를 적용하지 않으므로, 실제로 숨는지는 브라우저에서 잰다.
  it("휴대폰 탭은 처음에 결과를 고르고, 고른 탭의 칸만 보이게 한다 (SCR-R015)", async () => {
    install([]);
    render(<Query />);
    await screen.findByText("모델 zzz-model");
    const hidden = () =>
      PANELS.map(([role, name]) => screen.getByRole(role, { name }).dataset.mobileHidden);

    expect(screen.getByRole("tab", { name: "결과" })).toHaveAttribute("aria-selected", "true");
    expect(hidden()).toEqual(["true", "false", "true"]);

    fireEvent.click(screen.getByRole("tab", { name: "처리 기록" }));
    expect(hidden()).toEqual(["true", "true", "false"]);

    fireEvent.click(screen.getByRole("tab", { name: "표와 열" }));
    expect(hidden()).toEqual(["false", "true", "true"]);
    expect(screen.getByRole("tab", { name: "표와 열" })).toHaveAttribute("aria-selected", "true");
  });
});
