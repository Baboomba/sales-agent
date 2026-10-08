import { getSchema } from "@/api/query";
import { useLoad } from "@/common/useLoad";

/** 물어볼 수 있는 표 목록을 불러온다. 못 불러오면 실패를 알리고 다시 시도할 수 있다 (SCR-R014). */
export const useTables = () => useLoad(getSchema);
