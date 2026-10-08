import { useEffect, useState } from "react";

import { getSchema } from "@/api/query";
import type { SchemaTable } from "@/api/types/query";

/** 물어볼 수 있는 표 목록을 불러온다. 못 불러오면 빈 목록이다. */
export const useTables = (): SchemaTable[] => {
  const [tables, setTables] = useState<SchemaTable[]>([]);
  useEffect(() => {
    getSchema()
      .then(setTables)
      .catch(() => setTables([]));
  }, []);
  return tables;
};
