// カレンダー(/calendar、店長のみ): 月表示で祝日・行事日を表示し、行事日を登録・削除する
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { createCalendarDay, deleteCalendarDay, listCalendar } from "../api/calendar";
import { errorMessage } from "../api/client";
import ConfirmDialog from "../components/ConfirmDialog";
import ErrorBanner from "../components/ErrorBanner";
import { jstToday } from "../format";
import styles from "../styles/page.module.css";
import type { CalendarDay } from "../types/api";
import { monthGrid } from "./calendarGrid";

const WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"];

export default function CalendarPage() {
  const today = jstToday();
  const [year, setYear] = useState(Number(today.slice(0, 4)));
  const [month, setMonth] = useState(Number(today.slice(5, 7)));
  const [days, setDays] = useState<CalendarDay[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [newDate, setNewDate] = useState("");
  const [newName, setNewName] = useState("");
  const [deleting, setDeleting] = useState<CalendarDay | null>(null);

  const load = useCallback(async (y: number) => {
    try {
      setDays(await listCalendar(y));
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);

  useEffect(() => {
    void load(year);
  }, [year, load]);

  function move(delta: number) {
    const m = month + delta;
    if (m < 1) {
      setYear(year - 1);
      setMonth(12);
    } else if (m > 12) {
      setYear(year + 1);
      setMonth(1);
    } else {
      setMonth(m);
    }
  }

  async function onRegister(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!newDate || !newName.trim()) {
      setError("日付と名称を入力してください");
      return;
    }
    try {
      await createCalendarDay({ date: newDate, kind: "event", name: newName.trim() });
      setNewDate("");
      setNewName("");
      await load(year);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function onDelete() {
    if (!deleting) return;
    const target = deleting;
    setDeleting(null);
    try {
      await deleteCalendarDay(target.id);
      await load(year);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const byDate = new Map<string, CalendarDay[]>();
  for (const d of days) {
    byDate.set(d.date, [...(byDate.get(d.date) ?? []), d]);
  }

  return (
    <section>
      <h1>カレンダー</h1>
      <ErrorBanner message={error} />
      <div className={styles.toolbar}>
        <button type="button" className={styles.secondary} onClick={() => move(-1)}>
          前月
        </button>
        <strong>
          {year}年{month}月
        </strong>
        <button type="button" className={styles.secondary} onClick={() => move(1)}>
          翌月
        </button>
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            {WEEKDAYS.map((w) => (
              <th key={w}>{w}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {monthGrid(year, month).map((week, i) => (
            <tr key={i}>
              {week.map((date, j) => (
                <td key={j} style={{ verticalAlign: "top", height: 64, width: "14%" }}>
                  {date && (
                    <>
                      <div>{Number(date.slice(8, 10))}</div>
                      {(byDate.get(date) ?? []).map((d) => (
                        <div key={d.id} style={{ color: d.kind === "holiday" ? "#b3261e" : "#1f3a4d", fontSize: "0.85rem" }}>
                          {d.name}
                          {d.kind === "event" && (
                            <button
                              type="button"
                              aria-label={`${d.name} を削除`}
                              onClick={() => setDeleting(d)}
                              style={{ marginLeft: 4, fontSize: "0.75rem" }}
                            >
                              削除
                            </button>
                          )}
                        </div>
                      ))}
                    </>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <form className={`${styles.toolbar} ${styles.section}`} onSubmit={onRegister}>
        <label className={styles.field}>
          日付
          <input type="date" value={newDate} onChange={(e) => setNewDate(e.target.value)} />
        </label>
        <label className={styles.field}>
          名称
          <input value={newName} maxLength={64} onChange={(e) => setNewName(e.target.value)} />
        </label>
        <button type="submit" className={styles.primary}>
          行事日を登録
        </button>
        <span className={styles.muted}>祝日は公開データから取り込みます(管理コマンド import_holidays)。</span>
      </form>

      <ConfirmDialog
        open={deleting !== null}
        message={deleting ? `行事日「${deleting.name}」(${deleting.date})を削除しますか?` : ""}
        onConfirm={onDelete}
        onCancel={() => setDeleting(null)}
      />
    </section>
  );
}
