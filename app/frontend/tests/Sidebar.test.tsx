import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { expect, test, vi } from "vitest";
import Sidebar from "../src/components/Sidebar";
import type { Me } from "../src/types/api";

const vegStaff: Me = {
  user_id: 1,
  name: "青果 太郎",
  role: "staff",
  departments: [{ code: "VEG", name: "青果", business_type: "order" }],
  accessible_departments: [{ code: "VEG", name: "青果", business_type: "order" }],
};

test("shows user name, departments and highlights current page", () => {
  render(
    <MemoryRouter initialEntries={["/orders"]}>
      <Sidebar me={vegStaff} onLogout={() => {}} />
    </MemoryRouter>,
  );
  expect(screen.getByText("青果 太郎")).toBeInTheDocument();
  expect(screen.getByText("青果")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "発注" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: "承認済み発注リスト" })).not.toHaveAttribute("aria-current");
  expect(screen.queryByRole("link", { name: "設定" })).not.toBeInTheDocument();
});

test("logout button calls handler", async () => {
  const onLogout = vi.fn();
  render(
    <MemoryRouter>
      <Sidebar me={vegStaff} onLogout={onLogout} />
    </MemoryRouter>,
  );
  await userEvent.setup().click(screen.getByRole("button", { name: "ログアウト" }));
  expect(onLogout).toHaveBeenCalled();
});
