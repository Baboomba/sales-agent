import { fireEvent, render, screen } from "@testing-library/react";

import { type FakeReply, fakeServer } from "@/api/__test__/fakeServer";
import { ModelStatus } from "@/features/ModelStatus";

const install = (routes: Record<string, FakeReply[]>) => {
  const server = fakeServer(routes);
  vi.stubGlobal("fetch", server.fetch);
  return server;
};

afterEach(() => {
  vi.unstubAllGlobals();
});

const HEALTH: FakeReply = { json: { status: "ok", model: "zzz-model" } };

describe("ModelStatus", () => {
  it("서버가 쓰는 모델 이름을 보인다", async () => {
    install({ "/api/health": [HEALTH] });
    render(<ModelStatus />);

    expect(await screen.findByText("모델 zzz-model")).toBeInTheDocument();
  });

  it("못 불러오면 안내와 다시 시도를 보이고, 다시 시도하면 다시 부른다 (SCR-R014)", async () => {
    // 본문이 정상 JSON 이어도 상태 코드가 실패면 실패다.
    install({
      "/api/health": [{ status: 503, text: '{"status":"ok","model":"zzz-model"}' }, HEALTH],
    });
    render(<ModelStatus />);

    expect(await screen.findByText("불러오지 못했습니다")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));

    expect(await screen.findByText("모델 zzz-model")).toBeInTheDocument();
  });
});
