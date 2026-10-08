import { fireEvent, render, screen, within } from "@testing-library/react";

import { type FakeReply, fakeServer, sse } from "@/api/__test__/fakeServer";
import { AskQuery } from "@/features/AskQuery";

const install = (routes: Record<string, FakeReply[]>) => {
  const server = fakeServer(routes);
  vi.stubGlobal("fetch", server.fetch);
  return server;
};

const renderAsk = () =>
  render(<AskQuery mobileTabs={null} mobileHidden={{ result: false, log: false }} />);

afterEach(() => {
  vi.unstubAllGlobals();
});

const EXAMPLES: FakeReply = { json: { questions: ["zzz 예시", "zzz 다른 예시"] } };

const SUCCESS = sse(
  ["generated", { attempt: 1, sql: "zzz sql" }],
  ["validated", { sql: "zzz sql LIMIT 201" }],
  ["done", { columns: ["zzz_region"], rows: [["zzz 서울"]], truncated: false }],
);

const resultCard = () => screen.getByRole("region", { name: "결과" });

describe("AskQuery", () => {
  it("묻기 전에는 결과 카드에 안내 문구가, 단계 칸에는 셋 다 대기가 보인다", async () => {
    install({ "/api/examples": [EXAMPLES] });
    renderAsk();
    await screen.findByRole("button", { name: "zzz 예시" });

    expect(resultCard()).toHaveTextContent("질문하거나 예시 질문을 눌러 보세요.");
    const cards = within(screen.getByRole("list", { name: "진행 단계" })).getAllByRole("listitem");
    expect(cards.map((card) => card.dataset.status)).toEqual(["wait", "wait", "wait"]);
  });

  it("예시 질문을 누르면 질문칸에 넣어 바로 묻고, 고른 예시를 강조한다 (SCR-R006)", async () => {
    const server = install({ "/api/examples": [EXAMPLES], "/api/queries": [{ sse: SUCCESS }] });
    renderAsk();

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));

    expect(await within(resultCard()).findByRole("cell", { name: "zzz 서울" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "질문" })).toHaveValue("zzz 예시");
    expect(screen.getByRole("button", { name: "zzz 예시" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "zzz 다른 예시" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(server.requests.at(-1)).toEqual({
      path: "/api/queries",
      body: { question: "zzz 예시" },
    });
  });

  it("검증을 통과했으면 SQL 탭이 「실행한 SQL」이고 검증된 SQL 을 보인다 (SCR-R009)", async () => {
    install({ "/api/examples": [EXAMPLES], "/api/queries": [{ sse: SUCCESS }] });
    renderAsk();

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));
    await within(resultCard()).findByRole("cell", { name: "zzz 서울" });
    fireEvent.click(screen.getByRole("tab", { name: "실행한 SQL" }));

    expect(within(resultCard()).getByText("zzz sql LIMIT 201")).toBeInTheDocument();
  });

  it("검증 전에 실패하면 결과 카드에 사유를 알리고, 처리 기록 끝에도 남기며, 「만든 SQL」은 남는다 — 위의 짝 (SCR-R009 · SCR-R010)", async () => {
    install({
      "/api/examples": [EXAMPLES],
      "/api/queries": [
        {
          sse: sse(
            ["generated", { attempt: 1, sql: "zzz 만든 sql" }],
            ["failed", { reason: "zzz 사유" }],
          ),
        },
      ],
    });
    renderAsk();

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));

    expect(await within(resultCard()).findByRole("alert")).toHaveTextContent("zzz 사유");
    const log = screen.getByRole("list", { name: "처리 기록" });
    expect(within(log).getAllByRole("listitem").at(-1)).toHaveTextContent("zzz 사유");
    fireEvent.click(screen.getByRole("tab", { name: "만든 SQL" }));
    expect(within(resultCard()).getByText("zzz 만든 sql")).toBeInTheDocument();
    expect(within(resultCard()).getByRole("alert")).toHaveTextContent("zzz 사유");
  });

  it("입력하고 질문하기를 누르면 그 질문을 보낸다 (FR-001)", async () => {
    const server = install({
      "/api/examples": [{ json: { questions: [] } }],
      "/api/queries": [{ sse: SUCCESS }],
    });
    renderAsk();

    fireEvent.change(screen.getByRole("textbox", { name: "질문" }), {
      target: { value: "zzz 직접 쓴 질문" },
    });
    fireEvent.click(screen.getByRole("button", { name: "질문하기" }));

    expect(await within(resultCard()).findByRole("cell", { name: "zzz 서울" })).toBeInTheDocument();
    expect(server.requests.at(-1)).toEqual({
      path: "/api/queries",
      body: { question: "zzz 직접 쓴 질문" },
    });
  });

  it("응답이 늦으면 첫 단계가 오기 전에도 진행 중과 중지가 보인다 (SCR-R002)", async () => {
    install({ "/api/examples": [EXAMPLES], "/api/queries": [{ hang: true }] });
    renderAsk();

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));

    const stop = await screen.findByRole("button", { name: "중지" });
    expect(screen.getByText("진행 중…")).toBeInTheDocument();
    fireEvent.click(stop);
  });

  it("늦은 응답에는 결과 카드에 흐르는 막대 · 지금 단계 · 표 모양 뼈대가 보이고, 끝나면 사라진다 (SCR-R002)", async () => {
    install({
      "/api/examples": [EXAMPLES],
      "/api/queries": [{ sseThenHang: sse(["generated", { attempt: 1, sql: "zzz sql" }]) }],
    });
    renderAsk();

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));

    const status = await within(resultCard()).findByRole("status");
    expect(status).toHaveTextContent("SQL 을 검증하는 중");
    expect(resultCard()).toHaveAttribute("aria-busy", "true");
    expect(within(resultCard()).getByTestId("skeleton")).toBeInTheDocument();
    expect(within(resultCard()).getByTestId("progress-bar")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "중지" }));
    await screen.findByRole("button", { name: "질문하기" });
    expect(resultCard()).toHaveAttribute("aria-busy", "false");
    expect(within(resultCard()).queryByTestId("skeleton")).not.toBeInTheDocument();
    expect(within(resultCard()).queryByTestId("progress-bar")).not.toBeInTheDocument();
  });

  it("빠른 응답에는 뼈대가 한 번도 보이지 않는다 — 위의 짝 (SCR-R002)", async () => {
    install({ "/api/examples": [EXAMPLES], "/api/queries": [{ sse: SUCCESS }] });
    renderAsk();
    let seen = false;
    const observer = new MutationObserver(() => {
      if (screen.queryByTestId("skeleton")) seen = true;
    });
    observer.observe(document.body, { childList: true, subtree: true });

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));
    await within(resultCard()).findByRole("cell", { name: "zzz 서울" });
    observer.disconnect();

    expect(seen).toBe(false);
    expect(resultCard()).toHaveAttribute("aria-busy", "false");
  });

  it("늦은 응답을 중지하면 묻기 전 모습으로 돌아간다 (SCR-R002)", async () => {
    install({ "/api/examples": [EXAMPLES], "/api/queries": [{ hang: true }] });
    renderAsk();

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));
    fireEvent.click(await screen.findByRole("button", { name: "중지" }));

    expect(await screen.findByRole("button", { name: "질문하기" })).toBeInTheDocument();
    expect(resultCard()).toHaveTextContent("질문하거나 예시 질문을 눌러 보세요.");
  });

  it("묻는 동안 질문하기 단추를 끄지 않고, 예시를 또 눌러도 한 번만 보낸다 (SCR-R004)", async () => {
    const server = install({ "/api/examples": [EXAMPLES], "/api/queries": [{ hang: true }] });
    renderAsk();

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));
    fireEvent.click(screen.getByRole("button", { name: "zzz 다른 예시" }));

    expect(screen.getByRole("button", { name: "질문하기" })).toBeEnabled();
    expect(screen.getByRole("textbox", { name: "질문" })).toHaveValue("zzz 예시");
    expect(server.requests.filter((r) => r.path === "/api/queries")).toHaveLength(1);
    fireEvent.click(await screen.findByRole("button", { name: "중지" }));
  });

  it("질문칸은 300자까지만 받는다 (SCR-R005)", () => {
    install({ "/api/examples": [{ json: { questions: [] } }] });
    renderAsk();

    expect(screen.getByRole("textbox", { name: "질문" })).toHaveAttribute("maxlength", "300");
  });

  it("공백뿐이면 질문하기를 누를 수 없고, 글자가 있으면 누를 수 있다 (SCR-R005)", () => {
    install({ "/api/examples": [{ json: { questions: [] } }] });
    renderAsk();
    const input = screen.getByRole("textbox", { name: "질문" });
    const submit = screen.getByRole("button", { name: "질문하기" });

    fireEvent.change(input, { target: { value: "   " } });
    expect(submit).toBeDisabled();
    fireEvent.change(input, { target: { value: "zzz 질문" } });
    expect(submit).toBeEnabled();
  });

  it("예시 질문을 못 불러오면 안내와 다시 시도를 보이고, 다시 시도하면 다시 부른다 (SCR-R014)", async () => {
    // 본문이 정상 JSON 이어도 상태 코드가 실패면 실패다.
    install({
      "/api/examples": [{ status: 500, text: '{"questions":["zzz 예시"]}' }, EXAMPLES],
    });
    renderAsk();

    expect(await screen.findByText("불러오지 못했습니다")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));

    expect(await screen.findByRole("button", { name: "zzz 예시" })).toBeInTheDocument();
    expect(screen.queryByText("불러오지 못했습니다")).not.toBeInTheDocument();
  });
});
