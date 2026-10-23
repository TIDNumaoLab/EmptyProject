// 商品一覧 API
import type { Product } from "../types/api";
import { api } from "./client";

export async function listProducts(departmentCode?: string): Promise<Product[]> {
  const res = await api.get<Product[]>("/api/products", {
    params: departmentCode ? { department_code: departmentCode } : {},
  });
  return res.data;
}
