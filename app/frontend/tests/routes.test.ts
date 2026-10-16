import { expect, test } from "vitest";
import { NAV_ITEMS, homePath, visibleNav } from "../src/auth/routes";
import type { DepartmentRef, Me } from "../src/types/api";

const veg: DepartmentRef = { code: "VEG", name: "青果", business_type: "order" };
const deli: DepartmentRef = { code: "DELI", name: "惣菜", business_type: "production" };
const me = (role: Me["role"], departments: DepartmentRef[]): Me => ({
  user_id: 1,
  name: "a",
  role,
  departments,
  accessible_departments: departments,
});

test("nav has the 9 screens except login", () => {
  expect(NAV_ITEMS.map((n) => n.path)).toEqual([
    "/orders",
    "/production",
    "/orders/approved",
    "/imports",
    "/inventory",
    "/promotions",
    "/calendar",
    "/settings",
    "/review",
  ]);
});

test("homePath by department", () => {
  expect(homePath(me("staff", [deli]))).toBe("/production");
  expect(homePath(me("staff", [veg, deli]))).toBe("/orders");
  expect(homePath(me("manager", []))).toBe("/orders");
});

test("staff cannot see calendar and settings", () => {
  const paths = visibleNav(me("staff", [veg])).map((n) => n.path);
  expect(paths).not.toContain("/calendar");
  expect(paths).not.toContain("/settings");
  expect(paths).toContain("/orders/approved");
});

test("manager sees all screens", () => {
  expect(visibleNav(me("manager", []))).toHaveLength(NAV_ITEMS.length);
});
