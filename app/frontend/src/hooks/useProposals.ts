// 提案一覧の取得と再計算ジョブの進捗の確認(詳細設計書「きっかけ」)。
// 一覧APIは既存の提案をすぐ返し、再計算中ならジョブも返す。ジョブが終わるまで一定間隔で進捗を取り、終わったら一覧を取り直す。
// holdUpdates が true を返す間(保存していない入力がある間)は取り直さず、hasUpdate を立てて applyUpdate を待つ
import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage, statusOf } from "../api/client";
import { getJob, listProposals, recalculate as startRecalc } from "../api/proposals";
import type { Job, ProposalList, ProposalStatus } from "../types/api";

export interface ProposalParams {
  departmentCode: string;
  targetDate?: string;
  status?: ProposalStatus;
}

// 進捗の取得が通信の失敗・5xx で続けてこの回数失敗したら確認をやめる
const MAX_POLL_FAILURES = 5;

export function useProposals(params: ProposalParams, opts: { pollMs?: number; holdUpdates?: () => boolean } = {}) {
  const pollMs = opts.pollMs ?? 2000;
  // 最新の判定を使うため、描画ごとに入れ替わる関数を ref に置く
  const holdUpdates = useRef(opts.holdUpdates);
  holdUpdates.current = opts.holdUpdates;
  const { departmentCode, targetDate, status } = params;
  const [data, setData] = useState<ProposalList | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // 再計算が終わったが、保存していない入力があるため一覧を差し替えていない
  const [hasUpdate, setHasUpdate] = useState(false);
  // 条件を変えた後に古い要求の結果で上書きしないための番号
  const seq = useRef(0);
  // 進捗の取得が続けて失敗した回数
  const pollFailures = useRef(0);

  const reload = useCallback(async () => {
    if (!departmentCode) return;
    const mine = ++seq.current;
    setLoading(true);
    try {
      const res = await listProposals({ departmentCode, targetDate, status });
      if (mine !== seq.current) return;
      setData(res);
      setJob(res.job);
      setHasUpdate(false);
      setError(null);
    } catch (e) {
      if (mine === seq.current) setError(errorMessage(e));
    } finally {
      if (mine === seq.current) setLoading(false);
    }
  }, [departmentCode, targetDate, status]);

  useEffect(() => {
    // 条件が変わったら、前の条件の「新しい計算結果があります」は消す(取得に失敗しても残さない)
    setHasUpdate(false);
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
        pollFailures.current = 0;
        if (next.status === "running") {
          setJob(next);
        } else if (next.status === "succeeded") {
          setJob(null);
          if (holdUpdates.current?.()) {
            setHasUpdate(true);
          } else {
            await reload();
          }
        } else {
          setJob(next);
          setError(`最新の予測の計算に失敗しました: ${next.error ?? ""}`);
        }
      } catch (e) {
        if (stopped) return;
        const status = statusOf(e);
        // 4xx(セッション切れ・ジョブが見つからない等)は取り直しても直らない。通信の失敗・5xx は回数を限って取り直す
        const permanent = status !== undefined && status >= 400 && status < 500;
        pollFailures.current += 1;
        if (permanent || pollFailures.current >= MAX_POLL_FAILURES) {
          pollFailures.current = 0;
          setJob(null);
          setError(`最新の予測の進捗を確認できません: ${errorMessage(e)}`);
        } else {
          setJob({ ...job });
        }
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

  return { data, error, setError, loading, job, reload, recalculate, hasUpdate, applyUpdate: reload };
}
