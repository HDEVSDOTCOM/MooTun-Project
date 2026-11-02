import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, type TransactionItem } from "../api";

const ITEM: TransactionItem = {
  id: 7, transaction_type: "expense", amount_baht: "50.00", category: "อาหารเก่า", description: "ข้าว",
  occurred_on: "2026-01-03", created_at: "2026-01-03T12:00:00+07:00",
};
const CATEGORIES = { expense: ["อาหาร", "เดินทาง", "อื่นๆ"], income: ["เงินเดือน", "รายรับอื่นๆ"] };

const state = vi.hoisted(() => ({
  item: null as unknown,
  itemError: null as unknown,
  send: vi.fn(),
  close: vi.fn(),
  requireAuth: vi.fn(),
}));

vi.mock("../session", () => ({
  useSession: () => ({ token: "tok", requireAuth: state.requireAuth }),
  useMe: (path: string) => (path === "/api/me/categories"
    ? { data: CATEGORIES, error: null, loading: false, retry: () => {} }
    : { data: state.item, error: state.itemError, loading: false, retry: () => {} }),
}));

vi.mock("../api", async (original) => ({
  ...(await original<typeof import("../api")>()),
  sendMe: (...args: unknown[]) => state.send(...args),
}));

vi.mock("../liff", () => ({ closeWindow: () => state.close() }));

const { EditSheet, bangkokToday } = await import("../components/EditSheet");

function renderSheet(fromChat = false) {
  const onClose = vi.fn();
  const onChanged = vi.fn();
  render(<EditSheet id={7} fromChat={fromChat} onClose={onClose} onChanged={onChanged} />);
  return { onClose, onChanged };
}

function options(): string[] {
  return Array.from((screen.getByLabelText("หมวด") as HTMLSelectElement).options).map((option) => option.value);
}

beforeEach(() => {
  state.item = ITEM;
  state.itemError = null;
  state.send = vi.fn(async () => ITEM);
  state.close = vi.fn();
  state.requireAuth = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("EditSheet", () => {
  it("fills every field from the transaction", () => {
    renderSheet();
    expect((screen.getByLabelText("จำนวนเงิน") as HTMLInputElement).value).toBe("50.00");
    expect((screen.getByLabelText("หมวด") as HTMLSelectElement).value).toBe("อาหารเก่า");
    expect((screen.getByLabelText("รายละเอียด") as HTMLInputElement).value).toBe("ข้าว");
    expect((screen.getByLabelText("วันที่") as HTMLInputElement).value).toBe("2026-01-03");
    expect(screen.getByRole("radio", { name: "รายจ่าย" }).getAttribute("aria-checked")).toBe("true");
  });

  it("swaps categories with the type and restores a legacy category on the way back", () => {
    renderSheet();
    expect(options()).toEqual(["อาหารเก่า", "อาหาร", "เดินทาง", "อื่นๆ"]);
    fireEvent.click(screen.getByRole("radio", { name: "รายรับ" }));
    expect(options()).toEqual(["เงินเดือน", "รายรับอื่นๆ"]);
    expect((screen.getByLabelText("หมวด") as HTMLSelectElement).value).toBe("รายรับอื่นๆ");
    fireEvent.click(screen.getByRole("radio", { name: "รายจ่าย" }));
    expect((screen.getByLabelText("หมวด") as HTMLSelectElement).value).toBe("อาหารเก่า");
  });

  it("saves the exact body and returns to the chat when opened from a card", async () => {
    vi.useFakeTimers();
    const { onClose, onChanged } = renderSheet(true);
    fireEvent.change(screen.getByLabelText("จำนวนเงิน"), { target: { value: " 75.5 " } });
    fireEvent.change(screen.getByLabelText("รายละเอียด"), { target: { value: "  " } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "บันทึก" }));
    });
    expect(state.send).toHaveBeenCalledWith("PATCH", "/api/me/transactions/7", "tok", {
      transaction_type: "expense", amount_baht: "75.5", category: "อาหารเก่า", description: null,
      occurred_on: "2026-01-03",
    });
    expect(screen.getByRole("status").textContent).toContain("บันทึกแล้ว");
    act(() => vi.advanceTimersByTime(800));
    expect(state.close).toHaveBeenCalledOnce();
    expect(onChanged).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not close LINE when opened from the list", async () => {
    vi.useFakeTimers();
    const { onClose } = renderSheet(false);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "บันทึก" }));
    });
    act(() => vi.advanceTimersByTime(800));
    expect(state.close).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("needs a second tap within 3 seconds to delete", async () => {
    vi.useFakeTimers();
    renderSheet();
    fireEvent.click(screen.getByRole("button", { name: "ลบรายการนี้" }));
    act(() => vi.advanceTimersByTime(3000));
    expect(screen.getByRole("button", { name: "ลบรายการนี้" })).toBeTruthy();
    expect(state.send).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "ลบรายการนี้" }));
    act(() => vi.advanceTimersByTime(500));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "แตะอีกครั้งเพื่อลบ" }));
    });
    expect(state.send).toHaveBeenCalledWith("DELETE", "/api/me/transactions/7", "tok", undefined);
    expect(screen.getByRole("status").textContent).toContain("ลบแล้ว");
  });

  it("ignores an accidental double tap on delete", () => {
    vi.useFakeTimers();
    renderSheet();
    fireEvent.click(screen.getByRole("button", { name: "ลบรายการนี้" }));
    act(() => vi.advanceTimersByTime(100));
    fireEvent.click(screen.getByRole("button", { name: "แตะอีกครั้งเพื่อลบ" }));
    expect(state.send).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "แตะอีกครั้งเพื่อลบ" })).toBeTruthy();
  });

  it("explains a transaction that no longer exists", () => {
    state.item = null;
    state.itemError = new ApiError(404, "NOT_FOUND");
    const { onClose } = renderSheet();
    expect(screen.getByText("รายการนี้ถูกลบไปแล้ว")).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "ปิด" }).at(-1) as HTMLElement);
    expect(onClose).toHaveBeenCalled();
  });

  it("switches to the gone state when a save finds the row deleted", async () => {
    state.send = vi.fn(async () => { throw new ApiError(404, "NOT_FOUND"); });
    renderSheet();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "บันทึก" }));
    });
    expect(screen.getByText("รายการนี้ถูกลบไปแล้ว")).toBeTruthy();
  });

  it("points at the field a 422 names and keeps the input", async () => {
    state.send = vi.fn(async () => { throw new ApiError(422, "INVALID_FIELD", "amount_baht"); });
    renderSheet();
    fireEvent.change(screen.getByLabelText("จำนวนเงิน"), { target: { value: "0" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "บันทึก" }));
    });
    expect(screen.getByRole("alert").textContent).toBe("ตรวจช่องนี้อีกครั้ง");
    expect(screen.getByLabelText("จำนวนเงิน").getAttribute("aria-invalid")).toBe("true");
    expect((screen.getByLabelText("จำนวนเงิน") as HTMLInputElement).value).toBe("0");
  });

  it("sends a 401 to the login flow", async () => {
    state.send = vi.fn(async () => { throw new ApiError(401, "UNAUTHORIZED"); });
    renderSheet();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "บันทึก" }));
    });
    expect(state.requireAuth).toHaveBeenCalledOnce();
  });

  it("uses the Bangkok calendar day for the latest allowed date", () => {
    expect(bangkokToday(new Date("2026-01-03T18:30:00Z"))).toBe("2026-01-04");
  });
});
