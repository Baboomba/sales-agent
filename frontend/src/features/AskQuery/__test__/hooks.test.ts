import { act, renderHook, waitFor } from "@testing-library/react";

import { type FakeReply, fakeServer, sse } from "@/api/__test__/fakeServer";
import { useAskQuery, useExamples } from "@/features/AskQuery/hooks";

const install = (routes: Record<string, FakeReply[]>) => {
  const server = fakeServer(routes);
  vi.stubGlobal("fetch", server.fetch);
  return server;
};

afterEach(() => {
  vi.unstubAllGlobals();
});

const GENERATED = { attempt: 1, sql: "zzz sql 1" };
const FAILED = { reason: "zzz 사유" };

describe("useAskQuery", () => {
  it("앞뒤 공백을 뗀 질문을 보내고, 받은 단계를 차례로 담는다. 끝나면 진행 중이 풀린다", async () => {
    const server = install({
      "/api/queries": [{ sse: sse(["generated", GENERATED], ["failed", FAILED]) }],
    });
    const { result } = renderHook(() => useAskQuery());

    await act(() => result.current.ask("  zzz 질문  "));

    expect(server.requests).toEqual([{ path: "/api/queries", body: { question: "zzz 질문" } }]);
    expect(result.current.events).toEqual([
      { type: "generated", ...GENERATED },
      { type: "failed", ...FAILED },
    ]);
    expect(result.current.running).toBe(false);
  });

  it("새로 물으면 앞 질문의 단계를 비우고 새 단계만 담는다", async () => {
    install({
      "/api/queries": [
        { sse: sse(["failed", { reason: "zzz 첫 사유" }]) },
        { sse: sse(["failed", { reason: "zzz 둘째 사유" }]) },
      ],
    });
    const { result } = renderHook(() => useAskQuery());

    await act(() => result.current.ask("zzz 첫 질문"));
    await act(() => result.current.ask("zzz 둘째 질문"));

    expect(result.current.events).toEqual([{ type: "failed", reason: "zzz 둘째 사유" }]);
  });

  it("새로 물어도 첫 단계가 올 때까지는 앞 단계를 두고, 늦으면 그때 지우고 진행 중을 알린다 (#63)", async () => {
    install({
      "/api/queries": [{ sse: sse(["failed", { reason: "zzz 앞 사유" }]) }, { hang: true }],
    });
    const { result } = renderHook(() => useAskQuery());
    await act(() => result.current.ask("zzz 첫 질문"));

    let asking: Promise<void> = Promise.resolve();
    act(() => {
      asking = result.current.ask("zzz 둘째 질문");
    });

    expect(result.current.events).toEqual([{ type: "failed", reason: "zzz 앞 사유" }]);
    expect(result.current.pending).toBe(false);
    await waitFor(() => expect(result.current.pending).toBe(true));
    expect(result.current.events).toEqual([]);

    act(() => result.current.stop());
    await act(() => asking);
    expect(result.current.pending).toBe(false);
  });

  it("진행 중에 다시 물으면 보내지 않는다", async () => {
    const server = install({ "/api/queries": [{ hang: true }, { sse: sse(["failed", FAILED]) }] });
    const { result } = renderHook(() => useAskQuery());

    let first: Promise<void> = Promise.resolve();
    act(() => {
      first = result.current.ask("zzz 첫 질문");
    });
    await waitFor(() => expect(result.current.running).toBe(true));
    await act(() => result.current.ask("zzz 둘째 질문"));

    expect(server.requests).toHaveLength(1);
    act(() => result.current.stop());
    await act(() => first);
  });

  it("공백뿐인 질문은 보내지 않는다", async () => {
    const server = install({ "/api/queries": [{ sse: sse(["failed", FAILED]) }] });
    const { result } = renderHook(() => useAskQuery());

    await act(() => result.current.ask("   "));

    expect(server.requests).toEqual([]);
    expect(result.current.events).toEqual([]);
  });

  it("연결이 끊기면 실패를 덧붙여 알린다", async () => {
    install({ "/api/queries": [{ disconnect: true }] });
    const { result } = renderHook(() => useAskQuery());

    await act(() => result.current.ask("zzz 질문"));

    expect(result.current.events).toHaveLength(1);
    const [event] = result.current.events;
    expect(event?.type).toBe("failed");
    expect(event?.type === "failed" && event.reason.trim()).not.toBe("");
    expect(result.current.running).toBe(false);
  });

  it("단계를 받다가 끊기면 받은 단계 뒤에 실패를 덧붙인다", async () => {
    install({ "/api/queries": [{ sseThenDisconnect: sse(["generated", GENERATED]) }] });
    const { result } = renderHook(() => useAskQuery());

    await act(() => result.current.ask("zzz 질문"));

    expect(result.current.events).toHaveLength(2);
    expect(result.current.events[0]).toEqual({ type: "generated", ...GENERATED });
    expect(result.current.events[1]?.type).toBe("failed");
  });

  it("중지하면 실패로 알리지 않는다 — 위 두 테스트의 짝", async () => {
    install({ "/api/queries": [{ hang: true }] });
    const { result } = renderHook(() => useAskQuery());

    let asking: Promise<void> = Promise.resolve();
    act(() => {
      asking = result.current.ask("zzz 질문");
    });
    await waitFor(() => expect(result.current.running).toBe(true));
    act(() => result.current.stop());
    await act(() => asking);

    expect(result.current.events).toEqual([]);
    expect(result.current.running).toBe(false);
  });

  it("서버가 질문을 받지 않으면 상태 코드와 본문을 담은 실패를 알린다", async () => {
    install({ "/api/queries": [{ status: 422, text: "zzz 본문" }] });
    const { result } = renderHook(() => useAskQuery());

    await act(() => result.current.ask("zzz 질문"));

    const [event] = result.current.events;
    expect(event?.type).toBe("failed");
    const reason = event?.type === "failed" ? event.reason : "";
    expect(reason).toContain("422");
    expect(reason).toContain("zzz 본문");
  });
});

describe("useExamples", () => {
  it("예시 질문을 서버가 준 순서대로 불러온다", async () => {
    install({ "/api/examples": [{ json: { questions: ["zzz 둘째", "zzz 첫"] } }] });
    const { result } = renderHook(() => useExamples());

    await waitFor(() => expect(result.current).toEqual(["zzz 둘째", "zzz 첫"]));
  });
});
