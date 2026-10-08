import { LoadFailed } from "@/components/LoadFailed";
import { SchemaTables } from "@/entities/schema/SchemaTables";

import { useTables } from "./hooks";

/** 어떤 테이블과 컬럼에 물어볼 수 있는지 불러와 보여 준다 (FR-006 · SCR-R014). */
export const TableList = () => {
  const { state, retry } = useTables();
  if (state.status === "failed") return <LoadFailed onRetry={retry} />;
  if (state.status === "loading") return null;
  return <SchemaTables tables={state.value} />;
};
