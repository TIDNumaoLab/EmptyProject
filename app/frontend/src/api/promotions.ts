// 特売・チラシ API
import type { Promotion, PromotionInput } from "../types/api";
import { api } from "./client";

export async function listPromotions(
  params: { date_from?: string; date_to?: string; department_code?: string } = {},
): Promise<Promotion[]> {
  const res = await api.get<Promotion[]>("/api/promotions", { params });
  return res.data;
}

export async function createPromotion(body: PromotionInput): Promise<Promotion> {
  const res = await api.post<Promotion>("/api/promotions", body);
  return res.data;
}

export async function updatePromotion(id: number, body: Partial<PromotionInput>): Promise<Promotion> {
  const res = await api.patch<Promotion>(`/api/promotions/${id}`, body);
  return res.data;
}

export async function deletePromotion(id: number): Promise<void> {
  await api.delete(`/api/promotions/${id}`);
}
