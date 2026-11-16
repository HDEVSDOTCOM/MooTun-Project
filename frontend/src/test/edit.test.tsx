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
  chat: vi.fn(),
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

vi.mock("../liff", () => ({
  closeWindow: () => state.close(),
  sendToChat: (text: string) => state.chat(text),
}));

const { EditSheet, bangkokToday, rememberedEdit } = await import("../components/EditSheet");

function hidden(value: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => value });
}

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
  state.chat = vi.fn(async () => {});
  state.requireAuth = vi.fn();
});

afterEach(() => {
  cleanup();
  // Close any sheet a test left open so the next one starts clean.
  rememberedEdit.forget();
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
    await act(async () => vi.advanceTimersByTime(800));
    expect(state.chat).toHaveBeenCalledWith("แก้รายการ #7 แล้ว");
    expect(state.chat.mock.invocationCallOrder[0]).toBeLessThan(state.close.mock.invocationCallOrder[0]);
    expect(state.close).toHaveBeenCalledOnce();
    expect(onChanged).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("still returns to the chat when the chat message cannot be sent", async () => {
    vi.useFakeTimers();
    state.chat = vi.fn(async () => { throw new Error("no scope"); });
    renderSheet(true);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "บันทึก" }));
    });
    await act(async () => vi.advanceTimersByTime(800));
    expect(state.close).toHaveBeenCalledOnce();
  });

  it("sends nothing to the chat after a delete", async () => {
    vi.useFakeTimers();
    renderSheet(true);
    fireEvent.click(screen.getByRole("button", { name: "ลบรายการนี้" }));
    act(() => vi.advanceTimersByTime(500));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "แตะอีกครั้งเพื่อลบ" }));
    });
    await act(async () => vi.advanceTimersByTime(800));
    expect(state.chat).not.toHaveBeenCalled();
    expect(state.close).toHaveBeenCalledOnce();
  });

  it("shows the date in Thai while keeping the native picker", () => {
    renderSheet();
    expect(screen.getByText("3 ม.ค. 2569")).toBeTruthy();
    expect((screen.getByLabelText("วันที่") as HTMLInputElement).type).toBe("date");
  });

  it("does not close LINE when opened from the list", async () => {
    vi.useFakeTimers();
    const { onClose } = renderSheet(false);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "บันทึก" }));
    });
    await act(async () => vi.advanceTimersByTime(800));
    expect(state.close).not.toHaveBeenCalled();
    expect(state.chat).not.toHaveBeenCalled();
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

describe("EditSheet review follow-ups", () => {
  it("names a rejected type", async () => {
    state.send = vi.fn(async () => { throw new ApiError(422, "INVALID_FIELD", "transaction_type"); });
    renderSheet();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "บันทึก" }));
    });
    expect(screen.getByRole("alert").textContent).toBe("ตรวจช่องนี้อีกครั้ง");
  });

  it("keeps focus inside the sheet and gives it back on close", () => {
    const opener = document.createElement("button");
    document.body.append(opener);
    opener.focus();
    const view = render(<EditSheet id={7} fromChat={false} onClose={() => {}} onChanged={() => {}} />);
    const dialog = screen.getByRole("dialog");
    const focusable = Array.from(dialog.querySelectorAll<HTMLElement>("button, input, select"))
      .filter((node) => !node.hasAttribute("disabled"));
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    last.focus();
    fireEvent.keyDown(window, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
    view.unmount();
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });

  it("keeps what was typed when the app is hidden and shown again", () => {
    renderSheet();
    fireEvent.change(screen.getByLabelText("จำนวนเงิน"), { target: { value: "70" } });
    hidden(true);
    cleanup(); // hiding the app unmounts every screen
    hidden(false);
    expect(rememberedEdit()).toEqual({ id: 7, fromChat: false });
    renderSheet();
    expect((screen.getByLabelText("จำนวนเงิน") as HTMLInputElement).value).toBe("70");
  });

  it("forgets the sheet when it unmounts for any other reason", () => {
    renderSheet();
    cleanup(); // e.g. Back to another tab while the page stays visible
    expect(rememberedEdit()).toBeNull();
  });

  it("forgets the sheet as soon as a save succeeds", async () => {
    vi.useFakeTimers();
    renderSheet(true);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "บันทึก" }));
    });
    expect(rememberedEdit()).toBeNull();
  });

  it("does not close twice when Escape is pressed while the chat message is sending", async () => {
    vi.useFakeTimers();
    let release = () => {};
    state.chat = vi.fn(() => new Promise<void>((resolve) => { release = resolve; }));
    const { onClose } = renderSheet(true);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "บันทึก" }));
    });
    await act(async () => vi.advanceTimersByTime(800));
    fireEvent.keyDown(window, { key: "Escape" });
    await act(async () => release());
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("wraps Shift+Tab from the heading to the last control", () => {
    renderSheet();
    const dialog = screen.getByRole("dialog");
    expect(document.activeElement?.tagName).toBe("H2");
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    const nodes = dialog.querySelectorAll<HTMLElement>("button:not([disabled]), input, select");
    expect(document.activeElement).toBe(nodes[nodes.length - 1]);
  });

  it("forgets the draft once the sheet is closed", () => {
    renderSheet();
    fireEvent.change(screen.getByLabelText("จำนวนเงิน"), { target: { value: "70" } });
    fireEvent.click(screen.getAllByRole("button", { name: "ปิด" })[0]);
    expect(rememberedEdit()).toBeNull();
    cleanup();
    renderSheet();
    expect((screen.getByLabelText("จำนวนเงิน") as HTMLInputElement).value).toBe("50.00");
  });

  it.each(["", "   "])("offers a real category for a row saved without one (%j)", (blank) => {
    state.item = { ...ITEM, category: blank };
    renderSheet();
    expect(options()).toEqual(["อาหาร", "เดินทาง", "อื่นๆ"]);
    expect((screen.getByLabelText("หมวด") as HTMLSelectElement).value).toBe("อื่นๆ");
  });
});
