import { AskQuery } from "@/features/AskQuery";
import { TableList } from "@/features/TableList";

import styles from "./Query.module.css";

/** 질의 화면. 질문하기와 데이터 목록을 배치한다. */
export const Query = () => (
  <div className={styles.page}>
    <header className={styles.header}>
      <h1>매출 질의 Agent</h1>
      <p>
        2025년 가상 매출 데이터에 자연어로 물어보세요. 로컬 모델이 SQL 을 만들고, 규칙이 검증한 뒤
        실행합니다.
      </p>
    </header>

    <main className={styles.main}>
      <section>
        <AskQuery />
      </section>

      <aside className={styles.aside}>
        <h2>데이터</h2>
        <TableList />
      </aside>
    </main>
  </div>
);
