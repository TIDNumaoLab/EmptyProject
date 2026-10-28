// 提案の画面の試験で使う応答の例
import type { Job, Proposal, ProposalList } from "../src/types/api";

export function proposal(over: Partial<Proposal> = {}): Proposal {
  return {
    id: 1,
    department_code: "VEG",
    product_code: "VEG-001",
    product_name: "キャベツ",
    target_date: "2026-10-17",
    time_band: null,
    proposed_qty: 24,
    original_qty: 24,
    recalculated_qty: null,
    is_adjusted: false,
    adjust_reason: null,
    adjust_note: null,
    status: "pending",
    deadline: "2026-10-16T20:00:00+09:00",
    approved_by: null,
    approved_by_name: null,
    approved_at: null,
    warnings: [],
    order_unit: 6,
    calculated_at: "2026-10-16T15:00:00+09:00",
    created_at: "2026-10-16T15:00:00+09:00",
    updated_at: "2026-10-16T15:00:00+09:00",
    predicted_qty: 20.04,
    model_version: "baseline",
    is_baseline: true,
    weather_code: 61,
    weather_label: "雨",
    temperature: 18.5,
    precipitation: 1.2,
    precipitation_probability: 70,
    is_holiday: false,
    is_event_day: false,
    holiday_name: null,
    is_promotion: true,
    sales_lag_7d: 20,
    inventory_qty: 8,
    inventory_based_at: "2026-10-16T14:30:00+09:00",
    backlog_qty: 0,
    carry_over_qty: 2.5,
    expected_sales_qty: 5.5,
    display_stock_qty: null,
    weather_fetched_at: "2026-10-16T15:00:00+09:00",
    ...over,
  };
}

export function listResponse(proposals: Proposal[], job: Job | null = null, over: Partial<ProposalList> = {}): ProposalList {
  return {
    proposals,
    freshness: {
      calculated_at: "2026-10-16T15:00:00+09:00",
      weather_fetched_at: "2026-10-16T15:00:00+09:00",
      inventory_based_at: "2026-10-16T14:30:00+09:00",
    },
    job,
    notice: null,
    ...over,
  };
}

export const running = (processed = 3, total = 6): Job => ({ id: 5, status: "running", processed, total, error: null, notice: null });
