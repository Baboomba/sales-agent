import { parseSse } from "./sse";

describe("parseSse", () => {
  it("완성된 블록만 이벤트로 꺼내고 나머지는 남긴다", () => {
    const buffer =
      'event: generated\ndata: {"attempt":1,"sql":"SELECT 1"}\n\n' + "event: validated\ndata: {";
    const { events, rest } = parseSse(buffer);
    expect(events).toEqual([{ type: "generated", attempt: 1, sql: "SELECT 1" }]);
    expect(rest).toBe("event: validated\ndata: {");
  });

  it("조각으로 나뉘어 와도 이어 붙이면 같은 이벤트가 된다", () => {
    const first = parseSse('event: failed\ndata: {"rea');
    expect(first.events).toEqual([]);
    const second = parseSse(first.rest + 'son":"모델 서버"}\n\n');
    expect(second.events).toEqual([{ type: "failed", reason: "모델 서버" }]);
  });

  it("CRLF 줄바꿈도 읽는다", () => {
    const { events } = parseSse(
      'event: done\r\ndata: {"columns":[],"rows":[],"truncated":false}\r\n\r\n',
    );
    expect(events).toEqual([{ type: "done", columns: [], rows: [], truncated: false }]);
  });
});
