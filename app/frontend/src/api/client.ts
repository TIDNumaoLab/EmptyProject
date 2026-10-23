// Axios の共通設定。Cookie(セッション)を送り、CSRF 対策の独自ヘッダを全要求に付ける
import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL,
  withCredentials: true,
  headers: { "X-Requested-With": "smdx" },
});

interface ErrorLike {
  isAxiosError?: boolean;
  response?: { status?: number; data?: { detail?: unknown } };
}

// API のエラーから画面に出す文言を作る
export function errorMessage(e: unknown): string {
  const err = e as ErrorLike;
  if (!err?.response) {
    return "通信に失敗しました。";
  }
  const detail = err.response.data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((d: { msg?: string }) => d.msg ?? "").filter(Boolean).join("、");
  }
  return "エラーが発生しました。";
}

export function statusOf(e: unknown): number | undefined {
  return (e as ErrorLike)?.response?.status;
}
