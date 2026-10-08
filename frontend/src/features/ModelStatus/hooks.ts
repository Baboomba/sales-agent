import { getModelName } from "@/api/query";
import { useLoad } from "@/common/useLoad";

/** 서버가 쓰는 모델 이름을 불러온다. 못 불러오면 실패를 알리고 다시 시도할 수 있다 (SCR-R014). */
export const useModelName = () => useLoad(getModelName);
