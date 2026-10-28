// 承認済み発注リスト API
import type { ApprovedOrder } from "../types/api";
import { api } from "./client";

// 対象日を指定しなければ当日以降のすべて
export async function listApprovedOrders(departmentCode: string, targetDate?: string): Promise<ApprovedOrder[]> {
  const res = await api.get<ApprovedOrder[]>("/api/orders/approved", {
    params: { department_code: departmentCode, target_date: targetDate },
  });
  return res.data;
}
