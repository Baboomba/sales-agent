import type { QueryEvent } from "./types";

/**
 * SSE 버퍼에서 완성된 이벤트만 꺼낸다. 끝나지 않은 블록은 rest 로 돌려줘 다음 조각과 이어 붙인다.
 * fetch 와 섞지 않은 순수 함수라 따로 테스트한다.
 */
export function parseSse(buffer: string): { events: QueryEvent[]; rest: string } {
  const blocks = buffer.replace(/\r\n/g, "\n").split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: QueryEvent[] = [];
  for (const block of blocks) {
    let type = "";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) type = line.slice(7);
      else if (line.startsWith("data: ")) data += line.slice(6);
    }
    if (type && data) events.push({ type, ...JSON.parse(data) } as QueryEvent);
  }
  return { events, rest };
}
