import { fireEvent, render, screen } from "@testing-library/react";

import { type FakeReply, fakeServer } from "@/api/__test__/fakeServer";
import { TableList } from "@/features/TableList";

const install = (routes: Record<string, FakeReply[]>) => {
  const server = fakeServer(routes);
  vi.stubGlobal("fetch", server.fetch);
  return server;
};

afterEach(() => {
  vi.unstubAllGlobals();
});

const SCHEMA: FakeReply = {
  json: { tables: [{ name: "zzz_table", description: "zzz 설명", columns: [] }] },
};

describe("TableList", () => {
  it("표와 열을 불러와 보인다", async () => {
    install({ "/api/schema": [SCHEMA] });
    render(<TableList />);

    expect(await screen.findByText("zzz_table")).toBeInTheDocument();
  });

  it("못 불러오면 안내와 다시 시도를 보이고, 다시 시도하면 다시 부른다 (SCR-R014)", async () => {
    const server = install({ "/api/schema": [{ disconnect: true }, SCHEMA] });
    render(<TableList />);

    expect(await screen.findByText("불러오지 못했습니다")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));

    expect(await screen.findByText("zzz_table")).toBeInTheDocument();
    expect(server.requests.map((r) => r.path)).toEqual(["/api/schema", "/api/schema"]);
  });

  it("본문이 정상이어도 상태 코드가 실패면 안내를 보인다 (SCR-R014)", async () => {
    install({ "/api/schema": [{ status: 500, text: '{"tables":[]}' }] });
    render(<TableList />);

    expect(await screen.findByText("불러오지 못했습니다")).toBeInTheDocument();
  });
});
