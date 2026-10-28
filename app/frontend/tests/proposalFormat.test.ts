import { expect, test } from "vitest";
import { confirmMessage, formatDiff, formatFreshness, formatRunning, formatTime } from "../src/format";

test("formatFreshness", () => {
  expect(
    formatFreshness({
      calculated_at: "2026-10-16T19:42:00+09:00",
      weather_fetched_at: "2026-10-16T19:40:00+09:00",
      inventory_based_at: "2026-10-16T19:30:00+09:00",
    }),
  ).toBe("予測作成 10/16 19:42、予報取得 19:40、在庫 19:30時点");
  expect(formatFreshness({ calculated_at: null, weather_fetched_at: null, inventory_based_at: null })).toBe(
    "予測作成 —、予報取得 —、在庫 —",
  );
});

test("formatRunning", () => {
  expect(formatRunning({ id: 1, status: "running", processed: 3, total: 6, error: null, notice: null })).toBe(
    "最新の予測を計算中… (3/6)",
  );
});

test("formatDiff", () => {
  expect(formatDiff(42, 45)).toBe("再計算: 45(+3)");
  expect(formatDiff(42, 40)).toBe("再計算: 40(-2)");
  expect(formatDiff(42, 42)).toBe("再計算: 42(±0)");
});

test("formatTime shows Tokyo hour and minute", () => {
  expect(formatTime("2026-10-16T11:00:00Z")).toBe("20:00");
});

test("confirmMessage", () => {
  expect(confirmMessage(["NO_INVENTORY", "STALE_POS"])).toBe("在庫が取り込まれていません。このまま承認しますか?");
  expect(confirmMessage(["NO_WEATHER", "STALE_POS"])).toBe(
    "警告があります(気象データなし(ベースライン予測)、POS未更新)。このまま承認しますか?",
  );
});
