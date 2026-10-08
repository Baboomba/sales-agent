// 서버가 설계서의 이름으로 내는 값 (docs/design/query.md 2.2). 응답 타입과 엔티티가 함께 쓴다.

/** 거부됨 이벤트의 실패 단계. */
export type Stage = "generate" | "validate" | "execute";
