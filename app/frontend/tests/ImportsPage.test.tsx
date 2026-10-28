import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import * as importsApi from "../src/api/imports";
import ImportsPage from "../src/pages/ImportsPage";
import type { ImportLog } from "../src/types/api";
import { FISH, VEG, manager, renderPage, staff } from "./helpers";

vi.mock("../src/api/auth");
vi.mock("../src/api/imports");

const log: ImportLog = {
  id: 5,
  kind: "waste",
  department_code: "VEG",
  file_name: "waste.csv",
  imported_count: 1,
  skipped_count: 1,
  errors: [{ row: 3, reason: "未登録の商品コードです: XXX" }],
  imported_by_name: "担当 太郎",
  finished_at: "2026-10-16T19:40:00+09:00",
};

beforeEach(() => {
  vi.mocked(importsApi.listImports).mockResolvedValue([]);
});

function kindOptions() {
  return within(screen.getByLabelText("種類")).getAllByRole("option").map((o) => o.textContent);
}

test("staff cannot choose products kind but manager can", async () => {
  await renderPage(<ImportsPage />, staff(VEG), "データ取込");
  expect(kindOptions()).toEqual(["POS売上", "在庫", "廃棄"]);
});

test("shows file format hint", async () => {
  // Excel で保存し直すと形式が変わりやすいため、画面に形式を書いておく(PR #2 の補足)
  await renderPage(<ImportsPage />, staff(VEG), "データ取込");
  expect(screen.getByText(/文字コードは UTF-8、日付は YYYY-MM-DD/)).toBeInTheDocument();
});

test("manager sees products kind", async () => {
  await renderPage(<ImportsPage />, manager(), "データ取込");
  expect(kindOptions()).toEqual(["商品マスタ", "POS売上", "在庫", "廃棄"]);
});

test("shows imported/skipped counts and error rows after upload", async () => {
  vi.mocked(importsApi.uploadImport).mockResolvedValue(log);
  await renderPage(<ImportsPage />, staff(VEG, FISH), "データ取込");
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("種類"), "waste");
  await user.selectOptions(screen.getByLabelText("部門"), "VEG");
  const file = new File(["waste_date,product_code,quantity\n"], "waste.csv", { type: "text/csv" });
  await user.upload(screen.getByLabelText("CSVファイル"), file);
  await user.click(screen.getByRole("button", { name: "取り込む" }));
  expect(await screen.findByText("取込 1件、スキップ 1件")).toBeInTheDocument();
  expect(screen.getByText("3行目: 未登録の商品コードです: XXX")).toBeInTheDocument();
  expect(importsApi.uploadImport).toHaveBeenCalledWith("waste", file, "VEG");
  expect(importsApi.listImports).toHaveBeenCalledTimes(2); // 表示時と取込後
});

test("keeps selected file when upload fails", async () => {
  vi.mocked(importsApi.uploadImport).mockRejectedValue({
    isAxiosError: true,
    response: { status: 422, data: { detail: "必須列がありません: quantity" } },
  });
  await renderPage(<ImportsPage />, staff(VEG), "データ取込");
  const user = userEvent.setup();
  const file = new File(["x"], "pos.csv", { type: "text/csv" });
  await user.upload(screen.getByLabelText("CSVファイル"), file);
  await user.click(screen.getByRole("button", { name: "取り込む" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("必須列がありません: quantity");
  expect((screen.getByLabelText("CSVファイル") as HTMLInputElement).files?.[0]).toBe(file);
});

test("shows history rows", async () => {
  vi.mocked(importsApi.listImports).mockResolvedValue([log]);
  await renderPage(<ImportsPage />, staff(VEG), "データ取込");
  const row = (await screen.findByText("waste.csv")).closest("tr")!;
  expect(within(row).getByText("10/16 19:40")).toBeInTheDocument();
  expect(within(row).getByText("廃棄")).toBeInTheDocument();
});
