// 認証 API の呼び出し
import type { Me } from "../types/api";
import { api, statusOf } from "./client";

export async function login(loginId: string, password: string): Promise<Me> {
  const res = await api.post<Me>("/api/auth/login", { login_id: loginId, password });
  return res.data;
}

export async function logout(): Promise<void> {
  await api.post("/api/auth/logout");
}

// ログイン中の利用者。未ログイン(401)なら null
export async function fetchMe(): Promise<Me | null> {
  try {
    const res = await api.get<Me>("/api/me");
    return res.data;
  } catch (e) {
    if (statusOf(e) === 401) {
      return null;
    }
    throw e;
  }
}
