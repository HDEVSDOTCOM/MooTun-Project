import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TransactionItem } from "../api";

const state = vi.hoisted(() => ({
  resource: { data: null as unknown, error: null as unknown, loading: false, retry: () => {} },
  paths: [] as (string | null)[],
}));

vi.mock("../session", () => ({
  useSession: () => ({ summary: { year_ce: 2026, year_be: 2569, month: 1 } }),
  useMe: (path: string | null) => {
    state.paths.push(path);
    return state.resource;
  },
}));

const { Transactions, groupByDay } = await import("../routes/Transactions");
const { Savings } = await import("../routes/Savings");

function item(occurred_on: string, amount_baht: string, transaction_type: "income" | "expense" = "expense"): TransactionItem {
  return { transaction_type, amount_baht, category: "อาหาร", description: `<b>${amount_baht}</b>`, occurred_on, created_at: amount_baht };
}

afterEach(() => {
  cleanup();
  state.paths = [];
  state.resource = { data: null, error: null, loading: false, retry: () => {} };
});

describe("groupByDay", () => {
  it("keeps API order and groups consecutive days", () => {
    const groups = groupByDay([item("2026-01-03", "1.00"), item("2026-01-03", "2.00"), item("2026-01-01", "3.00")]);
    expect(groups.map(([day, items]) => [day, items.length])).toEqual([["2026-01-03", 2], ["2026-01-01", 1]]);
  });
});

describe("Transactions", () => {
  it("starts at the server month and requests filter and month changes", () => {
    state.resource.data = { items: [item("2026-01-03", "50.00")], truncated: false, limit: 500 };
    render(<Transactions />);
    expect(state.paths.at(-1)).toBe("/api/me/transactions?month=2026-01");
    expect(screen.getByText("ม.ค. 2569")).toBeTruthy();
    // User text renders as text, never markup.
    expect(screen.getByText("<b>50.00</b>")).toBeTruthy();

    fireEvent.click(screen.getByRole("radio", { name: "รายรับ" }));
    expect(state.paths.at(-1)).toBe("/api/me/transactions?month=2026-01&type=income");
    fireEvent.click(screen.getByRole("button", { name: "เดือนก่อนหน้า" }));
    expect(state.paths.at(-1)).toBe("/api/me/transactions?month=2025-12&type=income");
    expect(screen.getByText("ธ.ค. 2568")).toBeTruthy();
  });

  it("explains truncation and empty months", () => {
    state.resource.data = { items: [item("2026-01-03", "50.00")], truncated: true, limit: 500 };
    render(<Transactions />);
    expect(screen.getByText(/แสดง 500 รายการล่าสุดของเดือน/)).toBeTruthy();
    cleanup();
    state.resource.data = { items: [], truncated: false, limit: 500 };
    render(<Transactions />);
    expect(screen.getByText("ไม่มีรายการในเดือนนี้")).toBeTruthy();
  });

  it("offers a retry on errors", () => {
    const retry = vi.fn();
    state.resource = { data: null, error: { code: "DATA_UNAVAILABLE" }, loading: false, retry };
    render(<Transactions />);
    fireEvent.click(screen.getByRole("button", { name: "ลองอีกครั้ง" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});

describe("Savings", () => {
  it("shows exact API strings for a goal", () => {
    state.resource.data = {
      goal: { title: "หนังสือ", target_baht: "1500.00", saved_baht: "500.00", remaining_baht: "1000.00",
        progress_percent: "33.33", deadline: "2026-12-31" },
    };
    render(<Savings />);
    expect(screen.getByText("33.33%")).toBeTruthy();
    expect(screen.getByText("฿1,000.00")).toBeTruthy();
    expect(screen.getByText("กำหนด 31 ธ.ค. 2569")).toBeTruthy();
  });

  it("guides the user when no goal exists", () => {
    state.resource.data = { goal: null };
    render(<Savings />);
    expect(screen.getByText("ยังไม่มีเป้าหมาย")).toBeTruthy();
  });
});
