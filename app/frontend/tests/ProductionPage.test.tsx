import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import * as productionApi from "../src/api/production";
import * as productsApi from "../src/api/products";
import * as proposalsApi from "../src/api/proposals";
import * as settingsApi from "../src/api/settings";
import ProductionPage from "../src/pages/ProductionPage";
import type { Product, Proposal } from "../src/types/api";
import { DELI, VEG, renderPage, staff } from "./helpers";
import { listResponse, proposal, running } from "./proposalFixtures";

vi.mock("../src/api/auth");
vi.mock("../src/api/proposals");
vi.mock("../src/api/settings");
vi.mock("../src/api/products");
vi.mock("../src/api/production");

function deli(over: Partial<Proposal> = {}): Proposal {
  return proposal({
    department_code: "DELI", product_code: "DELI-001", product_name: "唐揚げ", target_date: "2026-10-16", time_band: 11,
    deadline: "2026-10-16T10:00:00+09:00", order_unit: 1, proposed_qty: 7, original_qty: 7, inventory_qty: null,
    inventory_based_at: null, backlog_qty: null, carry_over_qty: null, expected_sales_qty: null, display_stock_qty: 3,
    ...over,
  });
}

const KARAAGE: Product = {
  product_code: "DELI-001", name: "唐揚げ", department_code: "DELI", department_name: "惣菜", order_unit: 1,
  lead_time_days: 0, can_carry_over: false, cost_price: null, selling_price: null, is_active: true,
};

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-16T08:00:00+09:00"));
  vi.mocked(settingsApi.getSettings).mockResolvedValue({
    business_hours: { open: "10:00", close: "20:00" }, deli_time_bands: [10, 11, 14, 17],
  });
  vi.mocked(productsApi.listProducts).mockResolvedValue([KARAAGE]);
  vi.mocked(proposalsApi.listProposals).mockResolvedValue(
    listResponse([deli(), deli({ id: 2, time_band: 17, deadline: "2026-10-16T16:00:00+09:00", display_stock_qty: 0 })]),
  );
});

afterEach(() => {
  vi.useRealTimers();
});

test("production table shows band and production start columns", async () => {
  await renderPage(<ProductionPage />, staff(VEG, DELI), "製造計画");
  expect(await screen.findByText("11:00〜14:00")).toBeInTheDocument();
  // 最後の時間帯は閉店時刻まで
  expect(screen.getByText("17:00〜20:00")).toBeInTheDocument();
  const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
  expect(headers).toContain("時間帯");
  expect(headers).toContain("製造開始");
  expect(headers).toContain("陳列残数");
  expect(headers).not.toContain("在庫・発注残・持越見込");
  expect(headers).not.toContain("納品日");
  const row = screen.getByText("11:00〜14:00").closest("tr")!;
  expect(within(row).getByText("10:00")).toBeInTheDocument();
  expect(within(row).getByText("3")).toBeInTheDocument();
  // 惣菜の部門だけ選べる。発注締めは出さない
  const options = within(screen.getByLabelText("部門")).getAllByRole("option").map((o) => o.textContent);
  expect(options).toEqual(["惣菜"]);
  expect(screen.queryByText(/発注締め/)).not.toBeInTheDocument();
  expect(proposalsApi.listProposals).toHaveBeenCalledWith({ departmentCode: "DELI", targetDate: undefined, status: undefined });
  expect(productsApi.listProducts).toHaveBeenCalledWith("DELI");
});

test("shows notice from list response", async () => {
  vi.mocked(proposalsApi.listProposals).mockResolvedValue(
    listResponse([deli()], null, { notice: "時間帯の設定が変わったため再学習が必要です" }),
  );
  await renderPage(<ProductionPage />, staff(DELI), "製造計画");
  expect(await screen.findByText("時間帯の設定が変わったため再学習が必要です")).toBeInTheDocument();
});

test("approve sends the shown quantity", async () => {
  vi.mocked(proposalsApi.approveProposal).mockResolvedValue(deli({ status: "approved" }));
  await renderPage(<ProductionPage />, staff(DELI), "製造計画");
  const row = (await screen.findByText("11:00〜14:00")).closest("tr")!;
  await userEvent.setup().click(within(row).getByRole("button", { name: "承認" }));
  expect(proposalsApi.approveProposal).toHaveBeenCalledWith(1, 7, false);
});

test("saving display stock shows the plan of the day and tracks the recalculation", async () => {
  vi.setSystemTime(new Date("2026-10-16T12:00:00+09:00"));
  vi.mocked(productionApi.putDisplayStock).mockResolvedValue({ saved: 1, job: running(0, 2) });
  vi.mocked(proposalsApi.getJob).mockReturnValue(new Promise(() => {}));
  await renderPage(<ProductionPage />, staff(DELI), "製造計画");
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("唐揚げ の陳列残数"), "3");
  await user.click(screen.getByRole("button", { name: "陳列残数を保存" }));
  expect(productionApi.putDisplayStock).toHaveBeenCalledWith(expect.objectContaining({ target_date: "2026-10-16" }));
  // 陳列残数は当日の計画に効くので、当日の一覧に切り替える
  await waitFor(() =>
    expect(proposalsApi.listProposals).toHaveBeenLastCalledWith({ departmentCode: "DELI", targetDate: "2026-10-16", status: undefined }),
  );
  expect(screen.getByLabelText("対象日")).toHaveValue("2026-10-16");
});

test("tracks the returned job when the plan of the day is already shown", async () => {
  vi.setSystemTime(new Date("2026-10-16T12:00:00+09:00"));
  vi.mocked(productionApi.putDisplayStock).mockResolvedValue({ saved: 1, job: running(0, 2) });
  vi.mocked(proposalsApi.getJob).mockReturnValue(new Promise(() => {}));
  await renderPage(<ProductionPage />, staff(DELI), "製造計画");
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("対象日"), "2026-10-16");
  await user.type(await screen.findByLabelText("唐揚げ の陳列残数"), "3");
  await user.click(screen.getByRole("button", { name: "陳列残数を保存" }));
  expect(await screen.findByText("最新の予測を計算中… (0/2)")).toBeInTheDocument();
});
