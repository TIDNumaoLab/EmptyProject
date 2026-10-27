// 日時の表示と変換。日時はすべて日本時間(Asia/Tokyo)で扱う
import type { AdjustReason, Freshness, Job, ProposalStatus, WarningCode } from "./types/api";
const TZ = "Asia/Tokyo";

function parts(d: Date): Record<string, string> {
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  return Object.fromEntries(fmt.formatToParts(d).map((p) => [p.type, p.value]));
}

// 例: 2026/10/15 20:00
export function formatDateTime(iso: string): string {
  const p = parts(new Date(iso));
  return `${p.year}/${p.month}/${p.day} ${p.hour}:${p.minute}`;
}

// 例: 10/15 20:00
export function formatShortDateTime(iso: string): string {
  const p = parts(new Date(iso));
  return `${p.month}/${p.day} ${p.hour}:${p.minute}`;
}

// datetime-local の入力値(日本時間の壁時計)を +09:00 つきの ISO 8601 にする
export function toJstIso(localValue: string): string {
  return `${localValue}:00+09:00`;
}

// 現在の日本時間を datetime-local の入力値の形(YYYY-MM-DDTHH:MM)で返す
export function jstNowInput(now: Date = new Date()): string {
  const p = parts(now);
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

// 現在の日本時間の日付(YYYY-MM-DD)。days で日数をずらす
export function jstToday(days = 0, now: Date = new Date()): string {
  const p = parts(new Date(now.getTime() + days * 86400000));
  return `${p.year}-${p.month}-${p.day}`;
}

// 例: 20:00
export function formatTime(iso: string): string {
  const p = parts(new Date(iso));
  return `${p.hour}:${p.minute}`;
}

// 例: 10/17(日付 YYYY-MM-DD の月日)
export function formatMonthDay(date: string): string {
  const [, m, d] = date.split("-");
  return `${m}/${d}`;
}

// 鮮度の表示(詳細設計書「鮮度の表示」)。値の無い項目は「—」
export function formatFreshness(f: Freshness): string {
  const calc = f.calculated_at ? formatShortDateTime(f.calculated_at) : "—";
  const weather = f.weather_fetched_at ? formatTime(f.weather_fetched_at) : "—";
  const inventory = f.inventory_based_at ? `${formatTime(f.inventory_based_at)}時点` : "—";
  return `予測作成 ${calc}、予報取得 ${weather}、在庫 ${inventory}`;
}

export function formatRunning(job: Job): string {
  return `最新の予測を計算中… (${job.processed}/${job.total})`;
}

// 再計算値との差分。例: 再計算: 45(+3)
export function formatDiff(proposed: number, recalculated: number): string {
  const d = recalculated - proposed;
  const sign = d > 0 ? `+${d}` : d < 0 ? `${d}` : "±0";
  return `再計算: ${recalculated}(${sign})`;
}

export const WARNING_LABELS: Record<WarningCode, string> = {
  NO_INVENTORY: "在庫未取込",
  NO_HISTORY: "販売実績なし",
  NO_WEATHER: "気象データなし(ベースライン予測)",
  STALE_POS: "POS未更新",
};

export const REASON_LABELS: Record<AdjustReason, string> = {
  weather: "天候判断",
  promotion: "特売・売場都合",
  inventory: "在庫差異",
  other: "その他",
};

export const STATUS_LABELS: Record<ProposalStatus, string> = {
  pending: "未承認",
  approved: "承認済み",
  confirmed: "確定",
  expired: "期限切れ",
};

// 警告付きの提案を個別に承認するときの確認文言
export function confirmMessage(warnings: WarningCode[]): string {
  if (warnings.includes("NO_INVENTORY")) {
    return "在庫が取り込まれていません。このまま承認しますか?";
  }
  return `警告があります(${warnings.map((w) => WARNING_LABELS[w]).join("、")})。このまま承認しますか?`;
}
