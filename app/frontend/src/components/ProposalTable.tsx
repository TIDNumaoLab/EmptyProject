// 提案の表(1行1商品)。空なら空状態の文言を出す(再計算中は計算中の文言)
import pageStyles from "../styles/page.module.css";
import type { AdjustReason, Proposal } from "../types/api";
import ProposalRow from "./ProposalRow";

interface Props {
  proposals: Proposal[];
  selected: Set<number>;
  skipped: Map<number, string>;
  approveLocked: boolean;
  // 再計算ジョブの実行中
  computing?: boolean;
  onSelect(id: number, checked: boolean): void;
  onSave(p: Proposal, quantity: number, reason: AdjustReason, note: string | undefined): Promise<void>;
  onApprove(p: Proposal): void;
  onCancel(p: Proposal): void;
  onAdopt(p: Proposal): void;
  onDirtyChange?(id: number, dirty: boolean): void;
}

const HEADERS = ["選択", "納品日", "商品", "提案数", "予測値", "天候", "祝日・特売", "前週同曜日", "在庫・発注残・持越見込", "状態", "警告", "差分", "操作"];

export default function ProposalTable({ proposals, selected, skipped, approveLocked, computing = false, onSelect, onSave, onApprove, onCancel, onAdopt, onDirtyChange }: Props) {
  if (proposals.length === 0) {
    return (
      <p className={pageStyles.muted}>
        {computing ? "最新の予測を計算中です。完了すると表示します。" : "この条件の提案はありません。"}
      </p>
    );
  }
  return (
    <table className={pageStyles.table}>
      <thead>
        <tr>
          {HEADERS.map((h) => (
            <th key={h}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {proposals.map((p) => (
          <ProposalRow
            key={p.id}
            proposal={p}
            selected={selected.has(p.id)}
            skippedReason={skipped.get(p.id) ?? null}
            approveLocked={approveLocked}
            onSelect={(checked) => onSelect(p.id, checked)}
            onSave={(q, r, n) => onSave(p, q, r, n)}
            onApprove={() => onApprove(p)}
            onCancel={() => onCancel(p)}
            onAdopt={() => onAdopt(p)}
            onDirtyChange={onDirtyChange ? (dirty) => onDirtyChange(p.id, dirty) : undefined}
          />
        ))}
      </tbody>
    </table>
  );
}
