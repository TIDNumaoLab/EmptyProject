// 提案(発注提案)の API
import type { AdjustReason, BulkApproveResult, Job, Proposal, ProposalList, ProposalStatus } from "../types/api";
import { api } from "./client";

export interface ProposalQuery {
  departmentCode: string;
  // 未指定は各商品の最も早い納品日
  targetDate?: string;
  status?: ProposalStatus;
}

export async function listProposals(q: ProposalQuery): Promise<ProposalList> {
  const res = await api.get<ProposalList>("/api/proposals", {
    params: { department_code: q.departmentCode, target_date: q.targetDate, status: q.status },
  });
  return res.data;
}

export async function getJob(id: number): Promise<Job> {
  const res = await api.get<Job>(`/api/proposals/jobs/${id}`);
  return res.data;
}

export async function recalculate(departmentCode: string, targetDate?: string): Promise<Job> {
  const res = await api.post<{ job: Job }>("/api/proposals/recalculate", {
    department_code: departmentCode,
    target_date: targetDate,
  });
  return res.data.job;
}

export interface AdjustInput {
  quantity: number;
  reason: AdjustReason;
  reason_note?: string;
}

export async function adjustProposal(id: number, body: AdjustInput): Promise<Proposal> {
  const res = await api.patch<Proposal>(`/api/proposals/${id}`, body);
  return res.data;
}

// expectedQty は画面に表示している提案数。裏の再計算で変わっていれば 409 になる
export async function approveProposal(id: number, expectedQty: number, confirmWarnings: boolean): Promise<Proposal> {
  const res = await api.post<Proposal>(`/api/proposals/${id}/approve`, {
    expected_qty: expectedQty,
    confirm_warnings: confirmWarnings,
  });
  return res.data;
}

export interface BulkApproveItem {
  id: number;
  expected_qty: number;
}

export async function approveBulk(items: BulkApproveItem[]): Promise<BulkApproveResult> {
  const res = await api.post<BulkApproveResult>("/api/proposals/approve-bulk", { items });
  return res.data;
}

export async function cancelApproval(id: number): Promise<Proposal> {
  const res = await api.post<Proposal>(`/api/proposals/${id}/cancel-approval`);
  return res.data;
}

export async function adoptRecalculated(id: number): Promise<Proposal> {
  const res = await api.post<Proposal>(`/api/proposals/${id}/adopt-recalculated`);
  return res.data;
}
