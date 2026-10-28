// 惣菜の製造計画の API(陳列残数の入力)
import type { DisplayStockInput, Job } from "../types/api";
import { api } from "./client";

export async function putDisplayStock(body: DisplayStockInput): Promise<{ saved: number; job: Job }> {
  const res = await api.put<{ saved: number; job: Job }>("/api/production/display-stock", body);
  return res.data;
}
