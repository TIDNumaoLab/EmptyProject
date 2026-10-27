import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import * as proposalsApi from "../src/api/proposals";
import * as settingsApi from "../src/api/settings";
import OrdersPage from "../src/pages/OrdersPage";
import { DELI, FISH, VEG, renderPage, staff } from "./helpers";
import { listResponse, proposal, running } from "./proposalFixtures";

vi.mock("../src/api/auth");
vi.mock("../src/api/proposals");
vi.mock("../src/api/settings");

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-16T15:10:00+09:00"));
  vi.mocked(settingsApi.getSettings).mockResolvedValue({ "order_cutoff.VEG": "20:00", "order_cutoff.FISH": "19:00" });
  vi.mocked(proposalsApi.listProposals).mockResolvedValue(listResponse([proposal()]));
});

afterEach(() => {
  vi.useRealTimers();
});

test("shows cutoff, freshness and proposals; only order departments selectable", async () => {
  await renderPage(<OrdersPage />, staff(VEG, FISH, DELI), "発注");
  expect(await screen.findByText("発注締め 20:00 まで")).toBeInTheDocument();
  expect(screen.getByText("予測作成 10/16 15:00、予報取得 15:00、在庫 14:30時点")).toBeInTheDocument();
  expect(screen.getByText("キャベツ")).toBeInTheDocument();
  const options = within(screen.getByLabelText("部門")).getAllByRole("option").map((o) => o.textContent);
  expect(options).toEqual(["青果", "鮮魚"]);
  expect(proposalsApi.listProposals).toHaveBeenCalledWith({ departmentCode: "VEG", targetDate: undefined, status: undefined });
});

test("shows empty state", async () => {
  vi.mocked(proposalsApi.listProposals).mockResolvedValue(listResponse([]));
  await renderPage(<OrdersPage />, staff(VEG), "発注");
  expect(await screen.findByText("この条件の提案はありません。")).toBeInTheDocument();
});

test("recalc button disabled while job running and shows progress", async () => {
  vi.mocked(proposalsApi.listProposals).mockResolvedValue(listResponse([proposal()], running(3, 6)));
  vi.mocked(proposalsApi.getJob).mockReturnValue(new Promise(() => {}));
  await renderPage(<OrdersPage />, staff(VEG), "発注");
  expect(await screen.findByText("最新の予測を計算中… (3/6)")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "再計算" })).toBeDisabled();
});

test("filters by target date and status", async () => {
  await renderPage(<OrdersPage />, staff(VEG), "発注");
  await screen.findByText("キャベツ");
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("対象日"), "2026-10-20");
  await user.selectOptions(screen.getByLabelText("状態"), "approved");
  await waitFor(() =>
    expect(proposalsApi.listProposals).toHaveBeenLastCalledWith({ departmentCode: "VEG", targetDate: "2026-10-20", status: "approved" }),
  );
});

test("saving an adjusted quantity sends quantity and reason", async () => {
  vi.mocked(proposalsApi.adjustProposal).mockResolvedValue(proposal({ proposed_qty: 18, is_adjusted: true }));
  await renderPage(<OrdersPage />, staff(VEG), "発注");
  const user = userEvent.setup();
  const input = await screen.findByLabelText("キャベツ の提案数");
  await user.clear(input);
  await user.type(input, "18");
  await user.selectOptions(screen.getByLabelText("キャベツ の修正理由"), "weather");
  await user.click(screen.getByRole("button", { name: "保存" }));
  expect(proposalsApi.adjustProposal).toHaveBeenCalledWith(1, { quantity: 18, reason: "weather" });
  await waitFor(() => expect(proposalsApi.listProposals).toHaveBeenCalledTimes(2));
});

test("api error keeps entered quantity", async () => {
  vi.mocked(proposalsApi.adjustProposal).mockRejectedValue({ response: { status: 409, data: { detail: "承認済みの提案は修正できません" } } });
  await renderPage(<OrdersPage />, staff(VEG), "発注");
  const user = userEvent.setup();
  const input = await screen.findByLabelText("キャベツ の提案数");
  await user.clear(input);
  await user.type(input, "18");
  await user.selectOptions(screen.getByLabelText("キャベツ の修正理由"), "other");
  await user.click(screen.getByRole("button", { name: "保存" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("承認済みの提案は修正できません");
  expect(screen.getByLabelText("キャベツ の提案数")).toHaveValue(18);
});

test("approving warned row shows confirm dialog with inventory message", async () => {
  vi.mocked(proposalsApi.listProposals).mockResolvedValue(listResponse([proposal({ warnings: ["NO_INVENTORY"] })]));
  vi.mocked(proposalsApi.approveProposal).mockResolvedValue(proposal({ status: "approved" }));
  await renderPage(<OrdersPage />, staff(VEG), "発注");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "承認" }));
  const dialog = screen.getByRole("dialog");
  expect(dialog).toHaveTextContent("在庫が取り込まれていません。このまま承認しますか?");
  await user.click(within(dialog).getByRole("button", { name: "はい" }));
  expect(proposalsApi.approveProposal).toHaveBeenCalledWith(1, true);
});

test("approving row without warnings needs no dialog", async () => {
  vi.mocked(proposalsApi.approveProposal).mockResolvedValue(proposal({ status: "approved" }));
  await renderPage(<OrdersPage />, staff(VEG), "発注");
  await userEvent.setup().click(await screen.findByRole("button", { name: "承認" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(proposalsApi.approveProposal).toHaveBeenCalledWith(1, false);
});

test("bulk approve reports skipped rows", async () => {
  vi.mocked(proposalsApi.listProposals).mockResolvedValue(
    listResponse([proposal(), proposal({ id: 2, product_code: "VEG-002", product_name: "トマト", warnings: ["NO_WEATHER"] })]),
  );
  vi.mocked(proposalsApi.approveBulk).mockResolvedValue({
    approved_ids: [1],
    skipped: [{ id: 2, reason: "警告があるため一括承認から除外しました" }],
  });
  await renderPage(<OrdersPage />, staff(VEG), "発注");
  const user = userEvent.setup();
  const bulk = await screen.findByRole("button", { name: "一括承認" });
  expect(bulk).toBeDisabled();
  await user.click(screen.getByLabelText("キャベツ を選択"));
  await user.click(screen.getByLabelText("トマト を選択"));
  await user.click(bulk);
  expect(proposalsApi.approveBulk).toHaveBeenCalledWith([1, 2]);
  const row = (await screen.findByText("警告があるため一括承認から除外しました")).closest("tr")!;
  expect(within(row).getByText("トマト")).toBeInTheDocument();
});

test("cancel and adopt call the api", async () => {
  vi.mocked(proposalsApi.listProposals).mockResolvedValue(
    listResponse([proposal({ status: "approved", recalculated_qty: 30 })]),
  );
  vi.mocked(proposalsApi.cancelApproval).mockResolvedValue(proposal());
  vi.mocked(proposalsApi.adoptRecalculated).mockResolvedValue(proposal());
  await renderPage(<OrdersPage />, staff(VEG), "発注");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "取消" }));
  await user.click(screen.getByRole("button", { name: "採用" }));
  expect(proposalsApi.cancelApproval).toHaveBeenCalledWith(1);
  expect(proposalsApi.adoptRecalculated).toHaveBeenCalledWith(1);
});
