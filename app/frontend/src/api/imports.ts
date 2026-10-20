// データ取込 API
import type { ImportKind, ImportLog } from "../types/api";
import { api } from "./client";

export async function uploadImport(kind: ImportKind, file: File, departmentCode?: string): Promise<ImportLog> {
  const form = new FormData();
  form.append("file", file);
  if (kind !== "products" && departmentCode) {
    form.append("department_code", departmentCode);
  }
  const res = await api.post<ImportLog>(`/api/imports/${kind}`, form);
  return res.data;
}

export async function listImports(params: { kind?: ImportKind; department_code?: string } = {}): Promise<ImportLog[]> {
  const res = await api.get<ImportLog[]>("/api/imports", { params });
  return res.data;
}
