import { useState } from "react";

import { AskQuery } from "@/features/AskQuery";
import { ModelStatus } from "@/features/ModelStatus";
import { TableList } from "@/features/TableList";

import styles from "./Query.module.css";

/** 휴대폰에서 고른 탭 (SCR-R015). PC 에서는 셋 다 보인다. */
type MobileTab = "result" | "log" | "data";

const MOBILE_TABS: { tab: MobileTab; label: string }[] = [
  { tab: "result", label: "결과" },
  { tab: "log", label: "처리 기록" },
  { tab: "data", label: "테이블과 컬럼" },
];

/** 질의 화면. 폭 1280 까지의 틀에 테이블과 컬럼 · 질문하기 · 처리 기록을 놓는다 (screen.md 2절). */
export const Query = () => {
  // 휴대폰에서 고른 탭. 처음은 결과다 (SCR-R015).
  const [tab, setTab] = useState<MobileTab>("result");
  return (
    <div className={styles.page}>
      <header className={styles.top}>
        <div className={styles.brand}>
          <span className={styles.logo} aria-hidden="true">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />
            </svg>
          </span>
          <h1>
            매출 질의 Agent<span>2025년 가상 매출 데이터</span>
          </h1>
        </div>
        <ModelStatus />
      </header>

      <aside className={styles.data} aria-label="테이블과 컬럼" data-mobile-hidden={tab !== "data"}>
        <h2>테이블과 컬럼</h2>
        <TableList />
      </aside>

      <AskQuery
        mobileTabs={<MobileTabs tab={tab} onTab={setTab} />}
        mobileHidden={{ result: tab !== "result", log: tab !== "log" }}
      />
    </div>
  );
};

interface MobileTabsProps {
  tab: MobileTab;
  onTab: (tab: MobileTab) => void;
}

/** 휴대폰에서만 보이는 탭. 질문하기의 단계 칸 아래에 놓인다. */
const MobileTabs = ({ tab, onTab }: MobileTabsProps) => (
  <div className={styles.mobileTabs} role="tablist" aria-label="보기">
    {MOBILE_TABS.map((item) => (
      <button
        key={item.tab}
        type="button"
        role="tab"
        aria-selected={item.tab === tab}
        onClick={() => onTab(item.tab)}
      >
        {item.label}
      </button>
    ))}
  </div>
);
