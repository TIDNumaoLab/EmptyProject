import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import ConfirmDialog from "../src/components/ConfirmDialog";

test("shows message and calls handlers", async () => {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(<ConfirmDialog open message="この特売を削除しますか?" onConfirm={onConfirm} onCancel={onCancel} />);
  expect(screen.getByRole("dialog")).toHaveTextContent("この特売を削除しますか?");
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "いいえ" }));
  expect(onCancel).toHaveBeenCalledTimes(1);
  await user.click(screen.getByRole("button", { name: "はい" }));
  expect(onConfirm).toHaveBeenCalledTimes(1);
});

test("renders nothing when closed", () => {
  render(<ConfirmDialog open={false} message="x" onConfirm={() => {}} onCancel={() => {}} />);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
