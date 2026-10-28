// 惣菜の製造計画の API(陳列残数の入力)
import type { DisplayStockInput, DisplayStockResult } from "../types/api";
import { api } from "./client";

export async function putDisplayStock(body: DisplayStockInput): Promise<DisplayStockResult> {
  const res = await api.put<DisplayStockResult>("/api/production/display-stock", body);
  return res.data;
}
