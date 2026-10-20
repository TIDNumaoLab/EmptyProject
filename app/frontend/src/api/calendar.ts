// 祝日・行事日カレンダー API
import type { CalendarDay } from "../types/api";
import { api } from "./client";

export async function listCalendar(year: number): Promise<CalendarDay[]> {
  const res = await api.get<CalendarDay[]>("/api/calendar", { params: { year } });
  return res.data;
}

export async function createCalendarDay(body: Omit<CalendarDay, "id">): Promise<CalendarDay> {
  const res = await api.post<CalendarDay>("/api/calendar", body);
  return res.data;
}

export async function deleteCalendarDay(id: number): Promise<void> {
  await api.delete(`/api/calendar/${id}`);
}
