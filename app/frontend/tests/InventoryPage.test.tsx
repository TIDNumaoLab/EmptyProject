import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import * as inventoryApi from "../src/api/inventory";
import InventoryPage from "../src/pages/InventoryPage";
import { DELI, VEG, renderPage, staff } from "./helpers";

vi.mock("../src/api/auth");
vi.mock("../src/api/inventory");

beforeEach(() => {
  vi.mocked(inventoryApi.getLatestInventory).mockResolvedValue([
    { product_code: "VEG-001", product_name: "キャベツ", quantity: 8, based_at: "2026-10-15T20:00:00+09:00" },
    { product_code: "VEG-002", product_name: "トマト", quantity: null, based_at: null },
  ]);
  vi.mocked(inventoryApi.putInventory).mockResolvedValue({ saved: 1 });
});

test("inventory shows previous quantity and saves only entered items", async () => {
  await renderPage(<InventoryPage />, staff(VEG, DELI), "在庫入力");
  expect(await screen.findByText("前回 8(10/15 20:00)")).toBeInTheDocument();
  expect(screen.getByText("前回 —")).toBeInTheDocument();
  // 惣菜(製造計画の部門)は在庫入力の対象外
  expect(screen.queryByRole("option", { name: "惣菜" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("基準日時"), { target: { value: "2026-10-16T19:30" } });
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("キャベツ の在庫数"), "12");
  await user.click(screen.getByRole("button", { name: "保存" }));
  expect(await screen.findByText("保存しました(1件)")).toBeInTheDocument();
  expect(inventoryApi.putInventory).toHaveBeenCalledWith({
    department_code: "VEG",
    based_at: "2026-10-16T19:30:00+09:00",
    items: [{ product_code: "VEG-001", quantity: 12 }],
  });
  expect(inventoryApi.getLatestInventory).toHaveBeenCalledTimes(2); // 保存後に前回の値を読み直す
});

test("rejects negative quantity on client", async () => {
  await renderPage(<InventoryPage />, staff(VEG), "在庫入力");
  await screen.findByText("前回 8(10/15 20:00)");
  fireEvent.change(screen.getByLabelText("キャベツ の在庫数"), { target: { value: "-1" } });
  await userEvent.setup().click(screen.getByRole("button", { name: "保存" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("在庫数は0以上の整数で入力してください");
  expect(inventoryApi.putInventory).not.toHaveBeenCalled();
});
