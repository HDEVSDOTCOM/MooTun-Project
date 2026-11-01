import { cleanup, fireEvent, render as renderDom, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CategoryTotals, MonthlySeries } from "../api";

const SERIES: MonthlySeries = {
  months: 3,
  as_of: "x",
  items: [
    { year_ce: 2025, year_be: 2568, month: 12, income_baht: "500.00", expense_baht: "12.34", income_satang: 50000, expense_satang: 1234 },
    { year_ce: 2026, year_be: 2569, month: 1, income_baht: "0.00", expense_baht: "0.00", income_satang: 0, expense_satang: 0 },
    { year_ce: 2026, year_be: 2569, month: 2, income_baht: "0.00", expense_baht: "0.01", income_satang: 0, expense_satang: 1 },
  ],
};
const TOTALS: CategoryTotals = {
  type: "expense",
  total_baht: "6.00",
  total_satang: 600,
  as_of: "x",
  items: [
    { category: "อาหาร", amount_baht: "3.00", amount_satang: 300, transaction_count: 2, share_percent: "50.00" },
    { category: "<i>ของใช้</i>", amount_baht: "3.00", amount_satang: 300, transaction_count: 1, share_percent: "50.00" },
  ],
};

const state = vi.hoisted(() => ({ paths: [] as string[], empty: false }));

vi.mock("react-chartjs-2", () => ({ Bar: () => <canvas data-testid="bar" />, Doughnut: () => <canvas data-testid="donut" /> }));
vi.mock("../session", () => ({
  useSession: () => ({ summary: { year_ce: 2026, year_be: 2569, month: 2 } }),
  useMe: (path: string) => {
    state.paths.push(path);
    const series = state.empty
      ? { ...SERIES, items: SERIES.items.map((row) => ({ ...row, income_satang: 0, expense_satang: 0 })) }
      : SERIES;
    return { data: path.includes("monthly") ? series : TOTALS, error: null, loading: false, retry: () => {} };
  },
}));

const charts = await import("../charts");
const { Analysis } = await import("../routes/Analysis");

function render(ui: ReactElement, path = "/analysis") {
  return renderDom(<MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>);
}

afterEach(() => {
  cleanup();
  state.paths = [];
  state.empty = false;
});

describe("chart helpers", () => {
  it("size by satang but label with exact strings", () => {
    const bars = charts.barData(SERIES);
    expect(bars.labels).toEqual(["ธ.ค. 2568", "ม.ค. 2569", "ก.พ. 2569"]);
    expect(bars.datasets[0].data).toEqual([1234, 0, 1]);
    expect(charts.barTooltip(SERIES, 0, 0)).toBe("รายจ่าย ฿12.34");
    expect(charts.barTooltip(SERIES, 1, 0)).toBe("รายรับ ฿500.00");
    expect(charts.donutData(TOTALS).datasets[0].data).toEqual([300, 300]);
    expect(charts.donutTooltip(TOTALS, 0)).toBe("อาหาร ฿3.00 (50.00%)");
  });

  it("cycles category colors", () => {
    expect(charts.categoryColor(charts.CATEGORY_COLORS.length)).toBe(charts.categoryColor(0));
  });
});

describe("Analysis", () => {
  it("requests the default range and server month, then follows controls", () => {
    render(<Analysis />);
    expect(state.paths).toContain("/api/me/analytics/monthly?months=6");
    expect(state.paths).toContain("/api/me/analytics/categories?month=2026-02&type=expense");
    fireEvent.click(screen.getByRole("radio", { name: "12 เดือน" }));
    expect(state.paths).toContain("/api/me/analytics/monthly?months=12");
    fireEvent.click(screen.getByRole("radio", { name: "รายรับ" }));
    expect(state.paths.at(-1)).toBe("/api/me/analytics/categories?month=2026-02&type=income");
    fireEvent.click(screen.getByRole("button", { name: "เดือนก่อนหน้า" }));
    expect(state.paths.at(-1)).toBe("/api/me/analytics/categories?month=2026-01&type=income");
  });

  it("shows exact values in the table and legend, with text-only categories", () => {
    render(<Analysis />);
    expect(screen.getByTestId("bar")).toBeTruthy();
    expect(screen.getByText("฿12.34")).toBeTruthy();
    expect(screen.getByText("฿0.01")).toBeTruthy();
    expect(screen.getByText("<i>ของใช้</i>")).toBeTruthy();
    expect(screen.getByText("฿6.00")).toBeTruthy();
  });

  it("puts the category card first for the rich menu's หมวด/งบ link", () => {
    render(<Analysis />);
    let titles = screen.getAllByRole("heading").map((node) => node.textContent);
    expect(titles.indexOf("ประวัติรายรับรายจ่าย")).toBeLessThan(titles.indexOf("รายจ่ายตามหมวด"));
    cleanup();
    render(<Analysis />, "/analysis?section=categories");
    titles = screen.getAllByRole("heading").map((node) => node.textContent);
    expect(titles.indexOf("รายจ่ายตามหมวด")).toBeLessThan(titles.indexOf("ประวัติรายรับรายจ่าย"));
  });

  it("shows an empty state instead of a flat chart", () => {
    state.empty = true;
    render(<Analysis />);
    expect(screen.queryByTestId("bar")).toBeNull();
    expect(screen.getByText("ยังไม่มีข้อมูลในช่วงนี้")).toBeTruthy();
  });
});
