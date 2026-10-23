// 日時の表示と変換。日時はすべて日本時間(Asia/Tokyo)で扱う
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
