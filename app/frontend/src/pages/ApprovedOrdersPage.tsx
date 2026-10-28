// 承認済み発注リスト(/orders/approved): 承認済み・確定の提案を商品コード順に並べ、印刷する
// (既存の発注システム・PDAへ入力しやすいよう、印刷時は A4縦でサイドバーと操作部品を隠す)
import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { listApprovedOrders } from "../api/orders";
import { useAuth } from "../auth/AuthContext";
import DepartmentSelect, { selectableDepartments } from "../components/DepartmentSelect";
import ErrorBanner from "../components/ErrorBanner";
import { formatMonthDay } from "../format";
import styles from "../styles/page.module.css";
import type { ApprovedOrder } from "../types/api";

export default function ApprovedOrdersPage() {
  const { me } = useAuth();
  const [department, setDepartment] = useState(
    selectableDepartments(me?.accessible_departments ?? [], "order")[0]?.code ?? "",
  );
  const [targetDate, setTargetDate] = useState("");
  const [rows, setRows] = useState<ApprovedOrder[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!department) return;
    let stale = false;
    listApprovedOrders(department, targetDate || undefined)
      .then((r) => {
        if (!stale) {
          setRows(r);
          setError(null);
        }
      })
      .catch((e) => {
        if (!stale) setError(errorMessage(e));
      });
    return () => {
      stale = true;
    };
  }, [department, targetDate]);

  return (
    <section>
      <h1>承認済み発注リスト</h1>
      <ErrorBanner message={error} />
      <div className={`${styles.toolbar} no-print`}>
        <DepartmentSelect value={department} onChange={setDepartment} businessType="order" />
        <label className={styles.field}>
          対象日
          <input type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
        </label>
        <button type="button" className={styles.primary} onClick={() => window.print()}>
          印刷
        </button>
      </div>
      {rows && rows.length === 0 && <p className={styles.muted}>承認済みの発注はありません。</p>}
      {rows && rows.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>商品コード</th>
              <th>商品名</th>
              <th>納品日</th>
              <th>発注数</th>
              <th>発注単位</th>
              <th>承認者</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r.product_code}-${r.target_date}`}>
                <td>{r.product_code}</td>
                <td>{r.product_name}</td>
                <td>{formatMonthDay(r.target_date)}</td>
                <td className={styles.num}>{r.proposed_qty}</td>
                <td className={styles.num}>{r.order_unit}</td>
                <td>{r.approved_by_name ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
