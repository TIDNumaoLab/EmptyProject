// 月表示のカレンダーの升目(月曜始まり)。月外の日は null
export function monthGrid(year: number, month: number): (string | null)[][] {
  const pad = (n: number) => String(n).padStart(2, "0");
  // 曜日の計算だけに使うので UTC で日付を作る(端末のタイムゾーンの影響を受けない)
  const first = new Date(Date.UTC(year, month - 1, 1));
  const days = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const offset = (first.getUTCDay() + 6) % 7; // 月曜=0
  const cells: (string | null)[] = Array(offset).fill(null);
  for (let d = 1; d <= days; d++) {
    cells.push(`${year}-${pad(month)}-${pad(d)}`);
  }
  while (cells.length % 7 !== 0) {
    cells.push(null);
  }
  const weeks: (string | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) {
    weeks.push(cells.slice(i, i + 7));
  }
  return weeks;
}
