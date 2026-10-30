import {
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  DoughnutController,
  LinearScale,
  Tooltip,
} from "chart.js";
import type { CategoryTotals, MonthlySeries } from "./api";
import { baht, monthLabel } from "./money";

// Register only what the Analysis tab draws, keeping the lazy chunk small.
Chart.register(BarController, BarElement, CategoryScale, LinearScale, DoughnutController, ArcElement, Tooltip);
Chart.defaults.font.family = '"IBM Plex Sans Thai", system-ui, sans-serif';
Chart.defaults.color = "#8a6f7b";

// Canvas cannot read CSS variables; keep in step with @theme in index.css.
export const COLORS = { income: "#1f9e74", expense: "#d81b72", line: "#f1e3e9" };
export const CATEGORY_COLORS = [
  "#d81b72", "#f6a723", "#2bb5a0", "#7c5cd6", "#3b8beb", "#f2709c", "#9bc53d", "#ff8a5b",
];

export function categoryColor(index: number): string {
  return CATEGORY_COLORS[index % CATEGORY_COLORS.length];
}

// Satang only sizes bars and slices. Every label and tooltip uses the API's decimal strings.
export function barData(series: MonthlySeries) {
  return {
    labels: series.items.map((row) => monthLabel(row.month, row.year_be)),
    datasets: [
      { label: "รายจ่าย", data: series.items.map((row) => row.expense_satang), backgroundColor: COLORS.expense },
      { label: "รายรับ", data: series.items.map((row) => row.income_satang), backgroundColor: COLORS.income },
    ],
  };
}

export function barTooltip(series: MonthlySeries, datasetIndex: number, index: number): string {
  const row = series.items[index];
  return datasetIndex === 0 ? `รายจ่าย ${baht(row.expense_baht)}` : `รายรับ ${baht(row.income_baht)}`;
}

export function donutData(totals: CategoryTotals) {
  return {
    labels: totals.items.map((item) => item.category),
    datasets: [{
      data: totals.items.map((item) => item.amount_satang),
      backgroundColor: totals.items.map((_, index) => categoryColor(index)),
      borderWidth: 2,
      borderColor: "#ffffff",
    }],
  };
}

export function donutTooltip(totals: CategoryTotals, index: number): string {
  const item = totals.items[index];
  return `${item.category} ${baht(item.amount_baht)} (${item.share_percent}%)`;
}
