// ログイン中の利用者を画面全体で共有する
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import * as authApi from "../api/auth";
import { api, statusOf } from "../api/client";
import type { Me } from "../types/api";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login(loginId: string, password: string): Promise<Me>;
  logout(): Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

// 401 でも利用者を空にしない要求(ログイン中かどうかの確認と、ログインの失敗)
const AUTH_URLS = ["/api/me", "/api/auth/login"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    authApi
      .fetchMe()
      .then((m) => active && setMe(m))
      .catch(() => active && setMe(null))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  // セッション切れ(401)なら利用者を空にする。ログイン必須の画面の枠がログイン画面へ戻す
  useEffect(() => {
    const id = api.interceptors.response.use(undefined, (e) => {
      if (statusOf(e) === 401 && !AUTH_URLS.includes(e?.config?.url)) {
        setMe(null);
      }
      return Promise.reject(e);
    });
    return () => api.interceptors.response.eject(id);
  }, []);

  const login = useCallback(async (loginId: string, password: string) => {
    const m = await authApi.login(loginId, password);
    setMe(m);
    return m;
  }, []);

  // API の呼び出しに失敗しても、利用者を空にしてログイン画面へ戻せるようにする(例外は外に出さない)
  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // 失敗しても Cookie は最後の操作から SESSION_MAX_AGE_HOURS で切れる
    } finally {
      setMe(null);
    }
  }, []);

  const value = useMemo(() => ({ me, loading, login, logout }), [me, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth は AuthProvider の中で使う");
  }
  return ctx;
}
