// 提案一覧の取得と再計算ジョブの進捗の確認(詳細設計書「きっかけ」)。
// 一覧APIは既存の提案をすぐ返し、再計算中ならジョブも返す。ジョブが終わるまで一定間隔で進捗を取り、終わったら一覧を取り直す
import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/client";
import { getJob, listProposals, recalculate as startRecalc } from "../api/proposals";
import type { Job, ProposalList, ProposalStatus } from "../types/api";

export interface ProposalParams {
  departmentCode: string;
  targetDate?: string;
  status?: ProposalStatus;
}

export function useProposals(params: ProposalParams, opts: { pollMs?: number } = {}) {
  const pollMs = opts.pollMs ?? 2000;
  const { departmentCode, targetDate, status } = params;
  const [data, setData] = useState<ProposalList | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // 条件を変えた後に古い要求の結果で上書きしないための番号
  const seq = useRef(0);

  const reload = useCallback(async () => {
    if (!departmentCode) return;
    const mine = ++seq.current;
    setLoading(true);
    try {
      const res = await listProposals({ departmentCode, targetDate, status });
      if (mine !== seq.current) return;
      setData(res);
      setJob(res.job);
      setError(null);
    } catch (e) {
      if (mine === seq.current) setError(errorMessage(e));
    } finally {
      if (mine === seq.current) setLoading(false);
    }
  }, [departmentCode, targetDate, status]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // 実行中のジョブがある間は進捗を取りに行く
  useEffect(() => {
    if (!job || job.status !== "running") return;
    let stopped = false;
    const timer = setTimeout(async () => {
      try {
        const next = await getJob(job.id);
        if (stopped) return;
        if (next.status === "running") {
          setJob(next);
        } else if (next.status === "succeeded") {
          setJob(null);
          await reload();
        } else {
          setJob(next);
          setError(`最新の予測の計算に失敗しました: ${next.error ?? ""}`);
        }
      } catch (e) {
        if (!stopped) setError(errorMessage(e));
      }
    }, pollMs);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [job, pollMs, reload]);

  const recalculate = useCallback(async () => {
    try {
      setJob(await startRecalc(departmentCode, targetDate));
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [departmentCode, targetDate]);

  return { data, error, setError, loading, job, reload, recalculate };
}
