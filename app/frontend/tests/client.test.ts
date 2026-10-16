import { expect, test } from "vitest";
import { api, errorMessage } from "../src/api/client";

test("api sends csrf header and credentials", () => {
  expect(api.defaults.headers["X-Requested-With"]).toBe("smdx");
  expect(api.defaults.withCredentials).toBe(true);
});

test("errorMessage uses string detail", () => {
  const e = { isAxiosError: true, response: { status: 409, data: { detail: "承認済みの提案は修正できません" } } };
  expect(errorMessage(e)).toBe("承認済みの提案は修正できません");
});

test("errorMessage joins validation messages", () => {
  const e = { isAxiosError: true, response: { data: { detail: [{ msg: "A" }, { msg: "B" }] } } };
  expect(errorMessage(e)).toBe("A、B");
});

test("errorMessage for network failure", () => {
  expect(errorMessage({ isAxiosError: true })).toBe("通信に失敗しました。");
});
