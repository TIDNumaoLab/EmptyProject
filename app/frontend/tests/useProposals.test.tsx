import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import * as proposalsApi from "../src/api/proposals";
import { useProposals } from "../src/hooks/useProposals";
import { listResponse, proposal, running } from "./proposalFixtures";

vi.mock("../src/api/proposals");

afterEach(() => {
  vi.useRealTimers();
});

test("useProposals polls running job then reloads", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.mocked(proposalsApi.listProposals)
    .mockResolvedValueOnce(listResponse([], running(0, 1)))
    .mockResolvedValueOnce(listResponse([proposal()]));
  vi.mocked(proposalsApi.getJob).mockResolvedValue({ id: 5, status: "succeeded", processed: 1, total: 1, error: null, notice: null });

  const { result } = renderHook(() => useProposals({ departmentCode: "VEG" }, { pollMs: 2000 }));
  await waitFor(() => expect(result.current.job?.status).toBe("running"));
  expect(result.current.data?.proposals).toEqual([]);
  expect(proposalsApi.listProposals).toHaveBeenCalledWith({ departmentCode: "VEG" });

  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  await waitFor(() => expect(result.current.data?.proposals).toHaveLength(1));
  expect(proposalsApi.getJob).toHaveBeenCalledWith(5);
  expect(result.current.job).toBeNull();
  expect(proposalsApi.listProposals).toHaveBeenCalledTimes(2);
});

test("failed job shows error and stops polling", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.mocked(proposalsApi.listProposals).mockResolvedValue(listResponse([proposal()], running()));
  vi.mocked(proposalsApi.getJob).mockResolvedValue({ id: 5, status: "failed", processed: 0, total: 6, error: "計算に失敗", notice: null });

  const { result } = renderHook(() => useProposals({ departmentCode: "VEG" }, { pollMs: 1000 }));
  await waitFor(() => expect(result.current.job?.status).toBe("running"));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1000);
  });
  await waitFor(() => expect(result.current.error).toBe("最新の予測の計算に失敗しました: 計算に失敗"));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });
  expect(proposalsApi.getJob).toHaveBeenCalledTimes(1);
  // 既存の提案は表示したまま
  expect(result.current.data?.proposals).toHaveLength(1);
});

test("recalculate starts polling the returned job", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.mocked(proposalsApi.listProposals).mockResolvedValue(listResponse([proposal()]));
  vi.mocked(proposalsApi.recalculate).mockResolvedValue(running(0, 1));
  vi.mocked(proposalsApi.getJob).mockResolvedValue({ id: 5, status: "succeeded", processed: 1, total: 1, error: null, notice: null });

  const { result } = renderHook(() => useProposals({ departmentCode: "VEG", targetDate: "2026-10-20" }));
  await waitFor(() => expect(result.current.loading).toBe(false));
  await act(async () => {
    await result.current.recalculate();
  });
  expect(proposalsApi.recalculate).toHaveBeenCalledWith("VEG", "2026-10-20");
  expect(result.current.job?.status).toBe("running");
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  await waitFor(() => expect(result.current.job).toBeNull());
});

test("job progress failure is retried at the next interval", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.mocked(proposalsApi.listProposals)
    .mockResolvedValueOnce(listResponse([], running(0, 1)))
    .mockResolvedValueOnce(listResponse([proposal()]));
  vi.mocked(proposalsApi.getJob)
    .mockRejectedValueOnce({})
    .mockResolvedValueOnce({ id: 5, status: "succeeded", processed: 1, total: 1, error: null, notice: null });

  const { result } = renderHook(() => useProposals({ departmentCode: "VEG" }, { pollMs: 1000 }));
  await waitFor(() => expect(result.current.job?.status).toBe("running"));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1000);
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1000);
  });
  await waitFor(() => expect(result.current.job).toBeNull());
  expect(proposalsApi.getJob).toHaveBeenCalledTimes(2);
  expect(result.current.data?.proposals).toHaveLength(1);
});

test("job progress 4xx stops polling and shows the error", async () => {
  // セッション切れ・ジョブが見つからない等は取り直しても直らない
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.mocked(proposalsApi.listProposals).mockResolvedValue(listResponse([proposal()], running(0, 1)));
  vi.mocked(proposalsApi.getJob).mockRejectedValue({ response: { status: 401, data: { detail: "ログインしてください" } } });

  const { result } = renderHook(() => useProposals({ departmentCode: "VEG" }, { pollMs: 1000 }));
  await waitFor(() => expect(result.current.job?.status).toBe("running"));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1000);
  });
  await waitFor(() => expect(result.current.error).toBe("最新の予測の進捗を確認できません: ログインしてください"));
  expect(result.current.job).toBeNull();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });
  expect(proposalsApi.getJob).toHaveBeenCalledTimes(1);
});

test("job progress stops after 5 consecutive network failures", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.mocked(proposalsApi.listProposals).mockResolvedValue(listResponse([proposal()], running(0, 1)));
  vi.mocked(proposalsApi.getJob).mockRejectedValue({});

  const { result } = renderHook(() => useProposals({ departmentCode: "VEG" }, { pollMs: 1000 }));
  await waitFor(() => expect(result.current.job?.status).toBe("running"));
  for (let i = 0; i < 4; i++) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
  }
  expect(result.current.error).toBeNull();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1000);
  });
  await waitFor(() => expect(result.current.error).toBe("最新の予測の進捗を確認できません: 通信に失敗しました。"));
  expect(result.current.job).toBeNull();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });
  expect(proposalsApi.getJob).toHaveBeenCalledTimes(5);
});
