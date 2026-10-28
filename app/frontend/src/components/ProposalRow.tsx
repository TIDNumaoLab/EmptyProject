// 提案の表の1行(1商品)。未承認は提案数を入力でき、数量を変えたら修正理由を選んで保存する
import { useEffect, useState } from "react";
import { formatMonthDay, STATUS_LABELS } from "../format";
import pageStyles from "../styles/page.module.css";
import type { AdjustReason, Proposal } from "../types/api";
import AdjustReasonSelect from "./AdjustReasonSelect";
import DiffBadge from "./DiffBadge";
import styles from "./Proposals.module.css";
import WarningBadge from "./WarningBadge";

interface Props {
  proposal: Proposal;
  selected: boolean;
  // 一括承認で除外された理由
  skippedReason: string | null;
  // 再計算中は承認できない(表示中の数量がまもなく置き換わるため)
  approveLocked?: boolean;
  onSelect(checked: boolean): void;
  onSave(quantity: number, reason: AdjustReason, note: string | undefined): Promise<void>;
  onApprove(): void;
  onCancel(): void;
  onAdopt(): void;
}

function num(v: number | null, digits?: number): string {
  if (v === null) return "—";
  return digits === undefined ? String(v) : v.toFixed(digits);
}

function weatherText(p: Proposal): string {
  if (p.weather_label === null) return "—";
  const parts = [p.weather_label];
  if (p.temperature !== null) parts.push(`${p.temperature}℃`);
  if (p.precipitation_probability !== null) parts.push(`${p.precipitation_probability}%`);
  return parts.join(" ");
}

export default function ProposalRow({ proposal: p, selected, skippedReason, approveLocked = false, onSelect, onSave, onApprove, onCancel, onAdopt }: Props) {
  const [qty, setQty] = useState(String(p.proposed_qty));
  const [reason, setReason] = useState<AdjustReason | "">("");
  const [note, setNote] = useState("");
  // 保存などで提案が更新されたら入力欄を新しい値に戻す
  useEffect(() => {
    setQty(String(p.proposed_qty));
    setReason("");
    setNote("");
  }, [p.proposed_qty, p.updated_at]);

  const pending = p.status === "pending";
  const beforeDeadline = Date.now() < new Date(p.deadline).getTime();
  const dirty = qty !== String(p.proposed_qty);
  const valid = /^\d+$/.test(qty.trim());
  const name = p.product_name;

  return (
    <tr className={p.warnings.length > 0 ? styles.warned : undefined}>
      <td>
        <input
          type="checkbox"
          aria-label={`${name} を選択`}
          checked={selected}
          disabled={!pending}
          onChange={(e) => onSelect(e.target.checked)}
        />
      </td>
      <td>{formatMonthDay(p.target_date)}</td>
      <td>
        {name}
        <div className={pageStyles.muted}>入数 {p.order_unit}</div>
      </td>
      <td>
        {pending ? (
          <>
            <input
              type="number"
              min={0}
              step={1}
              className={styles.qty}
              aria-label={`${name} の提案数`}
              value={qty}
              onChange={(e) => setQty(e.target.value)}
            />
            {dirty && (
              <div>
                <AdjustReasonSelect label={`${name} の修正理由`} value={reason} onChange={setReason} />
                <input aria-label={`${name} の修正理由の補足`} placeholder="補足(任意)" maxLength={128} value={note}
                  onChange={(e) => setNote(e.target.value)} />
              </div>
            )}
          </>
        ) : (
          p.proposed_qty
        )}
        {p.is_adjusted && <div className={pageStyles.muted}>修正前 {p.original_qty}</div>}
      </td>
      <td className={pageStyles.num}>
        {num(p.predicted_qty, 1)}
        {p.is_baseline && <div className={styles.badge}>ベースライン予測</div>}
      </td>
      <td>{weatherText(p)}</td>
      <td>
        {p.is_holiday && <span className={styles.badge}>{p.holiday_name ?? "祝日"}</span>}
        {p.is_event_day && <span className={styles.badge}>行事日</span>}
        {p.is_promotion && <span className={styles.badge}>特売</span>}
      </td>
      <td className={pageStyles.num}>{num(p.sales_lag_7d)}</td>
      <td>{`在庫 ${num(p.inventory_qty)} / 発注残 ${num(p.backlog_qty)} / 持越 ${num(p.carry_over_qty)}`}</td>
      <td>
        {STATUS_LABELS[p.status]}
        {p.approved_by_name && <div className={pageStyles.muted}>{p.approved_by_name}</div>}
      </td>
      <td>
        {p.warnings.map((w) => (
          <WarningBadge key={w} code={w} />
        ))}
        {skippedReason && <div className={styles.skipped}>{skippedReason}</div>}
      </td>
      <td>
        <DiffBadge
          proposed={p.proposed_qty}
          recalculated={p.recalculated_qty}
          canAdopt={pending || (p.status === "approved" && beforeDeadline)}
          onAdopt={onAdopt}
        />
      </td>
      <td>
        <div className={styles.actions}>
          {pending && dirty && (
            <button
              type="button"
              className={pageStyles.secondary}
              disabled={!valid || reason === ""}
              onClick={() => void onSave(Number(qty.trim()), reason as AdjustReason, note.trim() || undefined)}
            >
              保存
            </button>
          )}
          {pending && !dirty && (
            <button type="button" className={pageStyles.secondary} onClick={onApprove} disabled={approveLocked}>
              承認
            </button>
          )}
          {p.status === "approved" && beforeDeadline && (
            <button type="button" className={pageStyles.secondary} onClick={onCancel}>
              取消
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}
