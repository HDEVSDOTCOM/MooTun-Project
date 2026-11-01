import { useState } from "react";
import { Bar, Doughnut } from "react-chartjs-2";
import { useSearchParams } from "react-router-dom";
import type { CategoryTotals, MonthlySeries } from "../api";
import { barData, barTooltip, categoryColor, COLORS, donutData, donutTooltip } from "../charts";
import { MonthPicker } from "../components/MonthPicker";
import { Card, CardTitle, Empty, InlineError, Skeleton } from "../components/ui";
import { bangkokMonth, baht, monthLabel, monthParam, type YearMonth } from "../money";
import { useMe, useSession } from "../session";

type Range = "3" | "6" | "12";
type Kind = "expense" | "income";

function Segmented<T extends string>({ label, value, options, onChange }: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex rounded-full bg-brand-soft/60 p-1">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          onClick={() => onChange(option.value)}
          className={`min-h-9 flex-1 rounded-full px-3 text-sm font-medium ${value === option.value ? "bg-card text-brand shadow-sm" : "text-muted"}`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Analysis() {
  // The rich menu's หมวด/งบ button opens ?section=categories: categories come first.
  const [params] = useSearchParams();
  const categoriesFirst = params.get("section") === "categories";
  return (
    <div className="space-y-4">
      {categoriesFirst ? <><CategoryBreakdown /><MonthlyHistory /></> : <><MonthlyHistory /><CategoryBreakdown /></>}
    </div>
  );
}

function MonthlyHistory() {
  const [range, setRange] = useState<Range>("6");
  const { data, error, loading, retry } = useMe<MonthlySeries>(`/api/me/analytics/monthly?months=${range}`);
  const empty = data?.items.every((row) => row.income_satang === 0 && row.expense_satang === 0);
  return (
    <Card>
      <CardTitle>ประวัติรายรับรายจ่าย</CardTitle>
      <Segmented label="ช่วงเวลา" value={range} onChange={setRange}
        options={[{ value: "3", label: "3 เดือน" }, { value: "6", label: "6 เดือน" }, { value: "12", label: "12 เดือน" }]} />
      <div className="mt-4">
        {loading && <Skeleton className="h-52" />}
        {error && <InlineError onRetry={retry} />}
        {data && empty && <Empty title="ยังไม่มีข้อมูลในช่วงนี้" hint="จดรายการในแชตแล้วกลับมาดูกราฟได้เลย" />}
        {data && !empty && (
          <>
            <div className="h-52" aria-hidden="true">
              <Bar
                data={barData(data)}
                options={{
                  maintainAspectRatio: false,
                  animation: false,
                  scales: {
                    x: { grid: { display: false } },
                    // Axis numbers would be float-derived; exact values live in tooltips and the table.
                    y: { ticks: { display: false }, grid: { color: COLORS.line }, border: { display: false } },
                  },
                  plugins: {
                    tooltip: { callbacks: { label: (context) => barTooltip(data, context.datasetIndex, context.dataIndex) } },
                  },
                }}
              />
            </div>
            <div className="mt-2 flex justify-center gap-4 text-xs text-muted">
              <span className="flex items-center gap-1.5"><i className="size-2.5 rounded-full bg-expense" />รายจ่าย</span>
              <span className="flex items-center gap-1.5"><i className="size-2.5 rounded-full bg-income" />รายรับ</span>
            </div>
            <table className="mt-3 w-full text-sm">
              <caption className="sr-only">รายรับและรายจ่ายรายเดือน</caption>
              <thead className="text-xs text-muted">
                <tr><th className="py-1 text-left font-normal">เดือน</th><th className="text-right font-normal">รายจ่าย</th><th className="text-right font-normal">รายรับ</th></tr>
              </thead>
              <tbody className="divide-y divide-line tabular-nums">
                {[...data.items].reverse().map((row) => (
                  <tr key={`${row.year_ce}-${row.month}`}>
                    <td className="py-1.5">{monthLabel(row.month, row.year_be)}</td>
                    <td className="text-right text-expense">{baht(row.expense_baht)}</td>
                    <td className="text-right text-income">{baht(row.income_baht)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </Card>
  );
}

function CategoryBreakdown() {
  const { summary } = useSession();
  const [month, setMonth] = useState<YearMonth>(() =>
    summary ? { yearCe: summary.year_ce, month: summary.month } : bangkokMonth(),
  );
  const [kind, setKind] = useState<Kind>("expense");
  const { data, error, loading, retry } = useMe<CategoryTotals>(
    `/api/me/analytics/categories?month=${monthParam(month.yearCe, month.month)}&type=${kind}`,
  );
  return (
    <Card>
      <CardTitle>{kind === "expense" ? "รายจ่ายตามหมวด" : "รายรับตามหมวด"}</CardTitle>
      <div className="space-y-3">
        <Segmented label="ประเภท" value={kind} onChange={setKind}
          options={[{ value: "expense", label: "รายจ่าย" }, { value: "income", label: "รายรับ" }]} />
        <MonthPicker value={month} onChange={setMonth} />
      </div>
      <div className="mt-4">
        {loading && <Skeleton className="mx-auto size-48 rounded-full" />}
        {error && <InlineError onRetry={retry} />}
        {data && data.items.length === 0 && <Empty title="ไม่มีรายการในเดือนนี้" />}
        {data && data.items.length > 0 && (
          <>
            <div className="relative mx-auto size-52">
              <div className="size-full" aria-hidden="true">
                <Doughnut
                  data={donutData(data)}
                  options={{
                    cutout: "68%",
                    animation: false,
                    plugins: { tooltip: { callbacks: { label: (context) => donutTooltip(data, context.dataIndex) } } },
                  }}
                />
              </div>
              <div className="pointer-events-none absolute inset-0 grid place-content-center text-center">
                <span className="text-xs text-muted">รวม</span>
                <span className="font-display text-lg font-semibold tabular-nums">{baht(data.total_baht)}</span>
              </div>
            </div>
            <ul className="mt-4 divide-y divide-line">
              {data.items.map((item, index) => (
                <li key={item.category} className="flex items-center gap-3 py-2.5 text-sm">
                  <i className="size-3 shrink-0 rounded-full" style={{ backgroundColor: categoryColor(index) }} />
                  <span className="min-w-0 flex-1 truncate">{item.category}</span>
                  <span className="text-xs text-muted tabular-nums">{item.share_percent}%</span>
                  <span className="w-28 text-right font-medium tabular-nums">{baht(item.amount_baht)}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </Card>
  );
}
