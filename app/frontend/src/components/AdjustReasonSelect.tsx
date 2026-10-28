// 修正理由の選択(数量を変えたら必須)
import { REASON_LABELS } from "../format";
import type { AdjustReason } from "../types/api";

interface Props {
  label: string;
  value: AdjustReason | "";
  onChange(value: AdjustReason | ""): void;
}

export default function AdjustReasonSelect({ label, value, onChange }: Props) {
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value as AdjustReason | "")}>
      <option value="">修正理由を選択</option>
      {(Object.keys(REASON_LABELS) as AdjustReason[]).map((r) => (
        <option key={r} value={r}>
          {REASON_LABELS[r]}
        </option>
      ))}
    </select>
  );
}
