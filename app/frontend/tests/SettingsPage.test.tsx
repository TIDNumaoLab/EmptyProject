import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import * as settingsApi from "../src/api/settings";
import SettingsPage from "../src/pages/SettingsPage";
import { VEG, manager, renderPage, staff } from "./helpers";

vi.mock("../src/api/auth");
vi.mock("../src/api/settings");

const SETTINGS = {
  business_hours: { open: "10:00", close: "20:00" },
  deli_time_bands: [10, 11, 14, 17],
  deli_production_start: { "10": "09:00", "11": "10:00", "14": "13:00", "17": "16:00" },
  weather_stale_hours: 3,
  "safety_factor.VEG": 1.1,
  "safety_factor.FISH": 1.1,
  "safety_factor.DELI": 1.1,
  "order_cutoff.VEG": "20:00",
  "order_cutoff.FISH": "20:00",
  "delivery_time.VEG": "10:00",
  "delivery_time.FISH": "10:00",
};

beforeEach(() => {
  vi.mocked(settingsApi.getSettings).mockResolvedValue(SETTINGS);
  vi.mocked(settingsApi.putSettings).mockResolvedValue(SETTINGS);
});

test("lists settings and saves only changed items", async () => {
  await renderPage(<SettingsPage />, manager(), "設定");
  const user = userEvent.setup();
  const safety = await screen.findByLabelText("安全係数(青果)");
  expect(safety).toHaveValue(1.1);
  expect(screen.getByLabelText("発注締め時刻(鮮魚)")).toHaveValue("20:00");
  await user.clear(safety);
  await user.type(safety, "1.2");
  await user.click(screen.getByRole("button", { name: "保存" }));
  expect(settingsApi.putSettings).toHaveBeenCalledWith({ "safety_factor.VEG": 1.2 });
  expect(await screen.findByText("保存しました")).toBeInTheDocument();
  expect(screen.queryByText("時間帯別モデルの再学習が必要です")).not.toBeInTheDocument();
});

test("settings shows retraining notice after time band change", async () => {
  await renderPage(<SettingsPage />, manager(), "設定");
  const user = userEvent.setup();
  const bands = await screen.findByLabelText("時間帯の区切り");
  expect(bands).toHaveValue("10,11,14,17");
  await user.clear(bands);
  await user.type(bands, "10,12,15,17");
  await user.click(screen.getByRole("button", { name: "保存" }));
  expect(settingsApi.putSettings).toHaveBeenCalledWith({ deli_time_bands: [10, 12, 15, 17] });
  expect(await screen.findByText("時間帯別モデルの再学習が必要です")).toBeInTheDocument();
});

test("settings shows field error from 422", async () => {
  vi.mocked(settingsApi.putSettings).mockRejectedValue({
    response: { status: 422, data: { detail: [{ key: "safety_factor.VEG", msg: "0より大きい数値を指定してください" }] } },
  });
  await renderPage(<SettingsPage />, manager(), "設定");
  const user = userEvent.setup();
  const safety = await screen.findByLabelText("安全係数(青果)");
  await user.clear(safety);
  await user.type(safety, "0");
  await user.click(screen.getByRole("button", { name: "保存" }));
  const row = (await screen.findByText("0より大きい数値を指定してください")).closest("tr")!;
  expect(within(row).getByText("安全係数(青果)")).toBeInTheDocument();
  expect(screen.getByLabelText("安全係数(青果)")).toHaveValue(0); // 入力は保持
});

test("invalid time bands are rejected on client", async () => {
  await renderPage(<SettingsPage />, manager(), "設定");
  const user = userEvent.setup();
  const bands = await screen.findByLabelText("時間帯の区切り");
  await user.clear(bands);
  await user.type(bands, "10,a");
  await user.click(screen.getByRole("button", { name: "保存" }));
  expect(await screen.findByText("時間帯の区切りは開始時(整数)をカンマ区切りで入力してください")).toBeInTheDocument();
  expect(settingsApi.putSettings).not.toHaveBeenCalled();
});

test("staff sees values without inputs", async () => {
  await renderPage(<SettingsPage />, staff(VEG), "設定");
  expect(await screen.findByText("10:00〜20:00")).toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "保存" })).not.toBeInTheDocument();
});
