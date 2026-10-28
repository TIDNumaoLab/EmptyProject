import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import * as productionApi from "../src/api/production";
import DisplayStockForm from "../src/components/DisplayStockForm";
import { running } from "./proposalFixtures";

vi.mock("../src/api/production");

const PRODUCTS = [
  { product_code: "DELI-001", name: "唐揚げ" },
  { product_code: "DELI-002", name: "コロッケ" },
];

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-16T12:00:00+09:00"));
  vi.mocked(productionApi.putDisplayStock).mockResolvedValue({ saved: 1, job: running(0, 2) });
});

afterEach(() => {
  vi.useRealTimers();
});

test("display stock form sends entered_at as now and only filled products", async () => {
  const onSaved = vi.fn();
  render(<DisplayStockForm departmentCode="DELI" products={PRODUCTS} onSaved={onSaved} />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("唐揚げ の陳列残数"), "3");
  await user.click(screen.getByRole("button", { name: "陳列残数を保存" }));
  expect(productionApi.putDisplayStock).toHaveBeenCalledWith({
    department_code: "DELI",
    target_date: "2026-10-16",
    entered_at: "2026-10-16T12:00:00+09:00",
    items: [{ product_code: "DELI-001", quantity: 3 }],
  });
  expect(onSaved).toHaveBeenCalledWith(running(0, 2), "2026-10-16");
  expect(await screen.findByText("陳列残数を保存しました(12:00 時点)")).toBeInTheDocument();
  expect(screen.getByLabelText("唐揚げ の陳列残数")).toHaveValue(null);
});

test("save is disabled until a quantity is entered", async () => {
  render(<DisplayStockForm departmentCode="DELI" products={PRODUCTS} onSaved={vi.fn()} />);
  expect(screen.getByRole("button", { name: "陳列残数を保存" })).toBeDisabled();
});

test("invalid quantity is not sent", async () => {
  render(<DisplayStockForm departmentCode="DELI" products={PRODUCTS} onSaved={vi.fn()} />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("コロッケ の陳列残数"), "1.5");
  await user.click(screen.getByRole("button", { name: "陳列残数を保存" }));
  expect(screen.getByText("陳列残数は0以上の整数で入力してください")).toBeInTheDocument();
  expect(productionApi.putDisplayStock).not.toHaveBeenCalled();
});

test("shows API error and keeps the input", async () => {
  vi.mocked(productionApi.putDisplayStock).mockRejectedValue(new Error("通信に失敗しました"));
  render(<DisplayStockForm departmentCode="DELI" products={PRODUCTS} onSaved={vi.fn()} />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("唐揚げ の陳列残数"), "3");
  await user.click(screen.getByRole("button", { name: "陳列残数を保存" }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(screen.getByLabelText("唐揚げ の陳列残数")).toHaveValue(3);
});
