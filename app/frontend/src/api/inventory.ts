// 在庫入力 API
import type { InventoryInput, InventoryLatest } from "../types/api";
import { api } from "./client";

export async function getLatestInventory(departmentCode: string): Promise<InventoryLatest[]> {
  const res = await api.get<InventoryLatest[]>("/api/inventory", { params: { department_code: departmentCode } });
  return res.data;
}

export async function putInventory(body: InventoryInput): Promise<{ saved: number }> {
  const res = await api.put<{ saved: number }>("/api/inventory", body);
  return res.data;
}
