import { fireEvent, render, screen } from "@testing-library/react";

import { type FakeReply, fakeServer, sse } from "@/api/__test__/fakeServer";
import { AskQuery } from "@/features/AskQuery";

const install = (routes: Record<string, FakeReply[]>) => {
  const server = fakeServer(routes);
  vi.stubGlobal("fetch", server.fetch);
  return server;
};

afterEach(() => {
  vi.unstubAllGlobals();
});

const SUCCESS = sse(
  ["generated", { attempt: 1, sql: "zzz sql" }],
  ["validated", { sql: "zzz sql LIMIT 201" }],
  ["done", { columns: ["zzz_region"], rows: [["zzz 서울"]], truncated: false }],
);

describe("AskQuery", () => {
  it("묻기 전에는 진행 · SQL · 결과 칸이 없다", async () => {
    install({ "/api/examples": [{ json: { questions: ["zzz 예시"] } }] });
    render(<AskQuery />);
    await screen.findByRole("button", { name: "zzz 예시" });

    expect(screen.queryByRole("heading", { name: "진행" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "실행한 SQL" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "결과" })).not.toBeInTheDocument();
  });

  it("예시 질문을 누르면 그 질문을 묻고, 진행 · 실행한 SQL · 결과를 보여 준다 — 위 테스트의 짝", async () => {
    const server = install({
      "/api/examples": [{ json: { questions: ["zzz 예시"] } }],
      "/api/queries": [{ sse: SUCCESS }],
    });
    render(<AskQuery />);

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));

    expect(await screen.findByRole("heading", { name: "결과" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "진행" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "실행한 SQL" })).toBeInTheDocument();
    expect(screen.getByText("zzz sql LIMIT 201")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "zzz 서울" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "질문" })).toHaveValue("zzz 예시");
    expect(server.requests.at(-1)).toEqual({
      path: "/api/queries",
      body: { question: "zzz 예시" },
    });
  });

  it("SQL 을 만들었지만 끝내 실패하면, 만든 SQL 은 보이고 결과 칸은 없다", async () => {
    install({
      "/api/examples": [{ json: { questions: ["zzz 예시"] } }],
      "/api/queries": [
        {
          sse: sse(
            ["generated", { attempt: 1, sql: "zzz 만든 sql" }],
            ["failed", { reason: "zzz 사유" }],
          ),
        },
      ],
    });
    render(<AskQuery />);

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("zzz 사유");
    expect(screen.getByRole("heading", { name: "만든 SQL" })).toBeInTheDocument();
    expect(screen.getByText("zzz 만든 sql")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "결과" })).not.toBeInTheDocument();
  });

  it("입력하고 질문하기를 누르면 그 질문을 보낸다 (FR-001)", async () => {
    const server = install({
      "/api/examples": [{ json: { questions: [] } }],
      "/api/queries": [{ sse: SUCCESS }],
    });
    render(<AskQuery />);

    fireEvent.change(screen.getByRole("textbox", { name: "질문" }), {
      target: { value: "zzz 직접 쓴 질문" },
    });
    fireEvent.click(screen.getByRole("button", { name: "질문하기" }));

    expect(await screen.findByRole("heading", { name: "결과" })).toBeInTheDocument();
    expect(server.requests.at(-1)).toEqual({
      path: "/api/queries",
      body: { question: "zzz 직접 쓴 질문" },
    });
  });

  it("응답이 늦으면 첫 단계가 오기 전에도 진행 칸과 진행 중 · 중지가 보인다 (#63)", async () => {
    install({
      "/api/examples": [{ json: { questions: ["zzz 예시"] } }],
      "/api/queries": [{ hang: true }],
    });
    render(<AskQuery />);

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));

    expect(await screen.findByRole("heading", { name: "진행" })).toBeInTheDocument();
    expect(screen.getByText("진행 중…")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "중지" }));
  });

  it("묻는 동안에도 질문하기 단추를 끄지 않는다 — 빠른 응답에 단추가 깜빡이지 않게 (#63)", async () => {
    install({
      "/api/examples": [{ json: { questions: ["zzz 예시"] } }],
      "/api/queries": [{ hang: true }],
    });
    render(<AskQuery />);

    fireEvent.click(await screen.findByRole("button", { name: "zzz 예시" }));

    expect(screen.getByRole("button", { name: "질문하기" })).toBeEnabled();
    fireEvent.click(await screen.findByRole("button", { name: "중지" }));
  });

  it("입력칸은 300자까지만 받는다 (QRY-R001)", async () => {
    install({ "/api/examples": [{ json: { questions: [] } }] });
    render(<AskQuery />);

    expect(screen.getByRole("textbox", { name: "질문" })).toHaveAttribute("maxlength", "300");
  });

  it("공백뿐이면 질문하기를 누를 수 없고, 글자가 있으면 누를 수 있다", async () => {
    install({ "/api/examples": [{ json: { questions: [] } }] });
    render(<AskQuery />);
    const input = screen.getByRole("textbox", { name: "질문" });
    const submit = screen.getByRole("button", { name: "질문하기" });

    fireEvent.change(input, { target: { value: "   " } });
    expect(submit).toBeDisabled();
    fireEvent.change(input, { target: { value: "zzz 질문" } });
    expect(submit).toBeEnabled();
  });
});
