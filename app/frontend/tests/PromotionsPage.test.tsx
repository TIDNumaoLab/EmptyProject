import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import * as productsApi from "../src/api/products";
import * as promotionsApi from "../src/api/promotions";
import PromotionsPage from "../src/pages/PromotionsPage";
import type { Product, Promotion } from "../src/types/api";
import { VEG, renderPage, staff } from "./helpers";

vi.mock("../src/api/auth");
vi.mock("../src/api/promotions");
vi.mock("../src/api/products");

const product = (code: string, name: string, dept: string): Product => ({
  product_code: code, name, department_code: dept, order_unit: 1, lead_time_days: 1,
  can_carry_over: true, cost_price: null, selling_price: null, is_active: true,
});
const promo: Promotion = {
  id: 7, product_code: "VEG-001", product_name: "キャベツ", department_code: "VEG",
  start_date: "2026-10-20", end_date: "2026-10-22", description: "チラシ", created_by_name: "担当 太郎",
};

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-16T12:00:00+09:00"));
  vi.mocked(productsApi.listProducts).mockResolvedValue([product("VEG-001", "キャベツ", "VEG"), product("FISH-001", "生鮭切身", "FISH")]);
  vi.mocked(promotionsApi.listPromotions).mockResolvedValue([promo]);
});

afterEach(() => {
  vi.useRealTimers();
});

test("lists promotions for default period and offers only own department products", async () => {
  await renderPage(<PromotionsPage />, staff(VEG), "特売・チラシ");
  // 一覧の取得は描画の後に始まるため、呼び出しを待ってから確かめる
  await waitFor(() =>
    expect(promotionsApi.listPromotions).toHaveBeenCalledWith({ date_from: "2026-10-16", date_to: "2026-11-15" }),
  );
  const row = (await screen.findByText("チラシ")).closest("tr")!;
  expect(within(row).getByText("10/20〜10/22")).toBeInTheDocument();
  const options = within(screen.getByLabelText("商品")).getAllByRole("option").map((o) => o.textContent);
  expect(options).toEqual(["キャベツ"]);
});

test("promotion form rejects end before start on client", async () => {
  await renderPage(<PromotionsPage />, staff(VEG), "特売・チラシ");
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("開始日"), "2026-10-22");
  await user.type(screen.getByLabelText("終了日"), "2026-10-20");
  await user.type(screen.getByLabelText("内容"), "週末セール");
  await user.click(screen.getByRole("button", { name: "登録" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("終了日は開始日以降にしてください");
  expect(promotionsApi.createPromotion).not.toHaveBeenCalled();
});

test("create promotion", async () => {
  vi.mocked(promotionsApi.createPromotion).mockResolvedValue({ ...promo, id: 8 });
  await renderPage(<PromotionsPage />, staff(VEG), "特売・チラシ");
  const user = userEvent.setup();
  await screen.findByRole("option", { name: "キャベツ" });
  await user.type(screen.getByLabelText("開始日"), "2026-10-24");
  await user.type(screen.getByLabelText("終了日"), "2026-10-25");
  await user.type(screen.getByLabelText("内容"), "週末セール");
  await user.click(screen.getByRole("button", { name: "登録" }));
  expect(promotionsApi.createPromotion).toHaveBeenCalledWith({
    product_code: "VEG-001", start_date: "2026-10-24", end_date: "2026-10-25", description: "週末セール",
  });
  expect(promotionsApi.listPromotions).toHaveBeenCalledTimes(2);
});

test("edit fills the form and saves with update", async () => {
  vi.mocked(promotionsApi.updatePromotion).mockResolvedValue({ ...promo, description: "変更" });
  await renderPage(<PromotionsPage />, staff(VEG), "特売・チラシ");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "編集" }));
  expect(screen.getByLabelText("内容")).toHaveValue("チラシ");
  await user.clear(screen.getByLabelText("内容"));
  await user.type(screen.getByLabelText("内容"), "変更");
  await user.click(screen.getByRole("button", { name: "更新" }));
  expect(promotionsApi.updatePromotion).toHaveBeenCalledWith(7, {
    product_code: "VEG-001", start_date: "2026-10-20", end_date: "2026-10-22", description: "変更",
  });
});

test("delete promotion asks confirmation", async () => {
  vi.mocked(promotionsApi.deletePromotion).mockResolvedValue();
  await renderPage(<PromotionsPage />, staff(VEG), "特売・チラシ");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "削除" }));
  const dialog = screen.getByRole("dialog");
  expect(dialog).toHaveTextContent("この特売を削除しますか?");
  await user.click(within(dialog).getByRole("button", { name: "いいえ" }));
  expect(promotionsApi.deletePromotion).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "削除" }));
  await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "はい" }));
  expect(promotionsApi.deletePromotion).toHaveBeenCalledWith(7);
});
