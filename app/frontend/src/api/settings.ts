// 設定 API(取得は全員、更新は店長のみ)
import type { Settings } from "../types/api";
import { api } from "./client";

export async function getSettings(): Promise<Settings> {
  const res = await api.get<{ settings: Settings }>("/api/settings");
  return res.data.settings;
}

// 変更する項目だけを送る。値が不正なら 422(detail: [{key, msg}])
export async function putSettings(changes: Settings): Promise<Settings> {
  const res = await api.put<{ settings: Settings }>("/api/settings", { settings: changes });
  return res.data.settings;
}
