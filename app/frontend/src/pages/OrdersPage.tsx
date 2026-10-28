// 発注(/orders): 生鮮の発注提案の確認・修正・承認(詳細設計書「発注(/orders)」)
import { useEffect, useState } from "react";
import { errorMessage, statusOf } from "../api/client";
import {
  adjustProposal,
  adoptRecalculated,
  approveBulk,
  approveProposal,
  cancelApproval,
  type AdjustInput,
} from "../api/proposals";
import { getSettings } from "../api/settings";
import { useAuth } from "../auth/AuthContext";
import BulkApproveButton from "../components/BulkApproveButton";
import ConfirmDialog from "../components/ConfirmDialog";
import DepartmentSelect, { selectableDepartments } from "../components/DepartmentSelect";
import ErrorBanner from "../components/ErrorBanner";
import FreshnessBar from "../components/FreshnessBar";
import ProposalTable from "../components/ProposalTable";
import proposalStyles from "../components/Proposals.module.css";
import { confirmMessage, STATUS_LABELS } from "../format";
import { useProposals } from "../hooks/useProposals";
import styles from "../styles/page.module.css";
import type { Proposal, ProposalStatus, Settings } from "../types/api";

export default function OrdersPage() {
  const { me } = useAuth();
  const [department, setDepartment] = useState(
    selectableDepartments(me?.accessible_departments ?? [], "order")[0]?.code ?? "",
  );
  const [targetDate, setTargetDate] = useState("");
  const [status, setStatus] = useState<ProposalStatus | "">("");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [skipped, setSkipped] = useState<Map<number, string>>(new Map());
  const [confirming, setConfirming] = useState<Proposal | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, error, job, reload, recalculate } = useProposals({
    departmentCode: department,
    targetDate: targetDate || undefined,
    status: status || undefined,
  });

  useEffect(() => {
    getSettings()
      .then(setSettings)
      .catch((e) => setActionError(errorMessage(e)));
  }, []);

  // 条件を変えたら選択と一括承認の結果を消す
  useEffect(() => {
    setSelected(new Set());
    setSkipped(new Map());
  }, [department, targetDate, status]);

  async function run(fn: () => Promise<unknown>) {
    setActionError(null);
    try {
      await fn();
      await reload();
    } catch (e) {
      setActionError(errorMessage(e));
      // 状態や数量が変わっていた(409): 新しい内容を見せるため一覧を取り直す
      if (statusOf(e) === 409) await reload();
    }
  }

  async function save(p: Proposal, quantity: number, reason: AdjustInput["reason"], note: string | undefined) {
    const body: AdjustInput = note ? { quantity, reason, reason_note: note } : { quantity, reason };
    await run(() => adjustProposal(p.id, body));
  }

  function approve(p: Proposal) {
    if (p.warnings.length > 0) {
      setConfirming(p);
    } else {
      void run(() => approveProposal(p.id, p.proposed_qty, false));
    }
  }

  async function bulk() {
    await run(async () => {
      const shown = data?.proposals ?? [];
      const items = shown.filter((p) => selected.has(p.id)).map((p) => ({ id: p.id, expected_qty: p.proposed_qty }));
      const res = await approveBulk(items);
      setSkipped(new Map(res.skipped.map((s) => [s.id, s.reason])));
      setSelected(new Set());
    });
  }

  const recalculating = job?.status === "running";
  const cutoff = settings?.[`order_cutoff.${department}`];

  return (
    <section>
      <h1>発注</h1>
      <ErrorBanner message={actionError ?? error} />
      {typeof cutoff === "string" && <p className={proposalStyles.cutoff}>発注締め {cutoff} まで</p>}
      <div className={styles.toolbar}>
        <DepartmentSelect value={department} onChange={setDepartment} businessType="order" />
        <label className={styles.field}>
          対象日
          <input type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
        </label>
        <label className={styles.field}>
          状態
          <select value={status} onChange={(e) => setStatus(e.target.value as ProposalStatus | "")}>
            <option value="">すべて</option>
            {(Object.keys(STATUS_LABELS) as ProposalStatus[]).map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </select>
        </label>
        <BulkApproveButton count={selected.size} disabled={recalculating} onClick={() => void bulk()} />
      </div>
      <FreshnessBar freshness={data?.freshness ?? null} job={job} onRecalculate={() => void recalculate()} />
      {data?.notice && <div className={styles.notice}>{data.notice}</div>}
      {data && (
        <ProposalTable
          proposals={data.proposals}
          selected={selected}
          skipped={skipped}
          approveLocked={recalculating}
          onSelect={(id, checked) => {
            const next = new Set(selected);
            if (checked) next.add(id);
            else next.delete(id);
            setSelected(next);
          }}
          onSave={save}
          onApprove={approve}
          onCancel={(p) => void run(() => cancelApproval(p.id))}
          onAdopt={(p) => void run(() => adoptRecalculated(p.id))}
        />
      )}
      <ConfirmDialog
        open={confirming !== null}
        message={confirming ? confirmMessage(confirming.warnings) : ""}
        onCancel={() => setConfirming(null)}
        onConfirm={() => {
          const p = confirming;
          setConfirming(null);
          if (p) void run(() => approveProposal(p.id, p.proposed_qty, true));
        }}
      />
    </section>
  );
}
