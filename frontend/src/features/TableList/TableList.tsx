import { SchemaTables } from "@/entities/schema/SchemaTables";

import { useTables } from "./hooks";

/** 어떤 표와 열에 물어볼 수 있는지 불러와 보여 준다 (FR-006). */
export const TableList = () => <SchemaTables tables={useTables()} />;
