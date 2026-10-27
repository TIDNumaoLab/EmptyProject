import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import * as ordersApi from "../src/api/orders";
import ApprovedOrdersPage from "../src/pages/ApprovedOrdersPage";
import { DELI, VEG, renderPage, staff } from "./helpers";

vi.mock("../src/api/auth");
vi.mock("../src/api/orders");

beforeEach(() => {
  vi.mocked(ordersApi.listApprovedOrders).mockResolvedValue([
    { product_code: "VEG-001", product_name: "キャベツ", target_date: "2026-10-17", proposed_qty: 24, order_unit: 6,
      status: "confirmed", approved_by_name: "担当 太郎", approved_at: "2026-10-16T15:00:00+09:00" },
    { product_code: "VEG-002", product_name: "トマト", target_date: "2026-10-17", proposed_qty: 10, order_unit: 1,
      status: "approved", approved_by_name: "担当 花子", approved_at: "2026-10-16T15:05:00+09:00" },
  ]);
});

test("approved list in product code order and print button calls window.print", async () => {
  const print = vi.spyOn(window, "print").mockImplementation(() => {});
  await renderPage(<ApprovedOrdersPage />, staff(VEG, DELI), "承認済み発注リスト");
  const rows = await screen.findAllByRole("row");
  expect(rows.slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent)).toEqual(["VEG-001", "VEG-002"]);
  const first = within(rows[1]);
  expect(first.getByText("キャベツ")).toBeInTheDocument();
  expect(first.getByText("24")).toBeInTheDocument();
  expect(first.getByText("6")).toBeInTheDocument();
  expect(first.getByText("担当 太郎")).toBeInTheDocument();
  expect(ordersApi.listApprovedOrders).toHaveBeenCalledWith("VEG", undefined);
  // 惣菜は対象外
  expect(screen.queryByRole("option", { name: "惣菜" })).not.toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole("button", { name: "印刷" }));
  expect(print).toHaveBeenCalled();
});

test("filters by target date and shows empty state", async () => {
  await renderPage(<ApprovedOrdersPage />, staff(VEG), "承認済み発注リスト");
  await screen.findByText("キャベツ");
  vi.mocked(ordersApi.listApprovedOrders).mockResolvedValue([]);
  await userEvent.setup().type(screen.getByLabelText("対象日"), "2026-10-18");
  await waitFor(() => expect(ordersApi.listApprovedOrders).toHaveBeenLastCalledWith("VEG", "2026-10-18"));
  expect(await screen.findByText("承認済みの発注はありません。")).toBeInTheDocument();
});
