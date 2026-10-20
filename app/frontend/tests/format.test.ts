import { expect, test } from "vitest";
import { formatDateTime, formatShortDateTime, toJstIso } from "../src/format";

test("toJstIso treats datetime-local value as Tokyo time", () => {
  expect(toJstIso("2026-10-16T19:30")).toBe("2026-10-16T19:30:00+09:00");
});

test("formatDateTime shows Tokyo time", () => {
  expect(formatDateTime("2026-10-15T11:00:00Z")).toBe("2026/10/15 20:00");
  expect(formatShortDateTime("2026-10-15T20:00:00+09:00")).toBe("10/15 20:00");
});
