import { act, render, screen, waitFor } from "@testing-library/react";
import { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import * as authApi from "../src/api/auth";
import { api } from "../src/api/client";
import { AuthProvider, useAuth } from "../src/auth/AuthContext";
import { VEG, staff } from "./helpers";

vi.mock("../src/api/auth");

const realAdapter = api.defaults.adapter;

// 要求をすべて status で失敗させる
function failWith(status: number): AxiosAdapter {
  return async (config: InternalAxiosRequestConfig) => {
    throw new AxiosError("失敗", "ERR_BAD_RESPONSE", config, null, {
      status, statusText: "", data: { detail: "ログインしてください" }, headers: {}, config,
    });
  };
}

let logoutRef: () => Promise<void> = async () => {};

function Who() {
  const { me, loading, logout } = useAuth();
  logoutRef = logout;
  if (loading) return null;
  return <p>{me ? me.name : "未ログイン"}</p>;
}

beforeEach(() => {
  vi.mocked(authApi.fetchMe).mockResolvedValue(staff(VEG));
});

afterEach(() => {
  api.defaults.adapter = realAdapter;
});

test("session expiry (401) logs the user out", async () => {
  // ログイン中の画面で API が 401 を返したら、ログイン画面へ戻すため利用者を空にする(PR #1 指摘8)
  render(<AuthProvider><Who /></AuthProvider>);
  await screen.findByText("担当 太郎");
  api.defaults.adapter = failWith(401);
  await act(async () => {
    await api.get("/api/products").catch(() => undefined);
  });
  expect(await screen.findByText("未ログイン")).toBeInTheDocument();
});

test("401 from login or other statuses keep the user", async () => {
  render(<AuthProvider><Who /></AuthProvider>);
  await screen.findByText("担当 太郎");
  api.defaults.adapter = failWith(401);
  await act(async () => {
    await api.post("/api/auth/login", {}).catch(() => undefined);
  });
  api.defaults.adapter = failWith(500);
  await act(async () => {
    await api.get("/api/products").catch(() => undefined);
  });
  expect(screen.getByText("担当 太郎")).toBeInTheDocument();
});

test("logout clears the user even when the API fails", async () => {
  // ログアウトの API が失敗しても、ログイン画面へ戻れるよう例外を外に出さない(PR #1 指摘8)
  vi.mocked(authApi.logout).mockRejectedValue(new Error("通信に失敗"));
  render(<AuthProvider><Who /></AuthProvider>);
  await screen.findByText("担当 太郎");
  await act(async () => {
    await expect(logoutRef()).resolves.toBeUndefined();
  });
  await waitFor(() => expect(screen.getByText("未ログイン")).toBeInTheDocument());
});
