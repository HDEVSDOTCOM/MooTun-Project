import { useState } from "react";
import type { MonthTransactions, TransactionItem } from "../api";
import { MonthPicker } from "../components/MonthPicker";
import { TransactionRow, transactionKey } from "../components/TransactionRow";
import { Card, Empty, InlineError, Skeleton } from "../components/ui";
import { bangkokMonth, calendarDate, monthParam, type YearMonth } from "../money";
import { useMe, useSession } from "../session";

type Filter = "all" | "expense" | "income";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "ทั้งหมด" },
  { value: "expense", label: "รายจ่าย" },
  { value: "income", label: "รายรับ" },
];

// Items arrive newest first; keep that order while grouping by calendar day.
export function groupByDay(items: TransactionItem[]): [string, TransactionItem[]][] {
  const groups: [string, TransactionItem[]][] = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    if (last && last[0] === item.occurred_on) last[1].push(item);
    else groups.push([item.occurred_on, [item]]);
  }
  return groups;
}

export function Transactions() {
  const { summary } = useSession();
  const [month, setMonth] = useState<YearMonth>(() =>
    summary ? { yearCe: summary.year_ce, month: summary.month } : bangkokMonth(),
  );
  const [filter, setFilter] = useState<Filter>("all");
  const type = filter === "all" ? "" : `&type=${filter}`;
  const { data, error, loading, retry } = useMe<MonthTransactions>(
    `/api/me/transactions?month=${monthParam(month.yearCe, month.month)}${type}`,
  );

  return (
    <div className="space-y-4">
      <MonthPicker value={month} onChange={setMonth} />
      <div role="radiogroup" aria-label="ประเภทรายการ" className="grid grid-cols-3 gap-2">
        {FILTERS.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={filter === option.value}
            onClick={() => setFilter(option.value)}
            className={`min-h-11 rounded-full text-sm font-medium ${filter === option.value ? "bg-brand text-white" : "bg-card text-muted"}`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {loading && (
        <Card>
          <div className="space-y-3"><Skeleton className="h-5 w-24" /><Skeleton className="h-12" /><Skeleton className="h-12" /></div>
        </Card>
      )}
      {error && <InlineError onRetry={retry} />}
      {data && data.items.length === 0 && (
        <Card><Empty title="ไม่มีรายการในเดือนนี้" hint="จดผ่านแชต เช่น “ข้าว 50” หรือ “เงินเดือน 20000”" /></Card>
      )}
      {data && groupByDay(data.items).map(([day, items]) => (
        <Card key={day}>
          <h2 className="text-sm font-medium text-muted">{calendarDate(day)}</h2>
          <ul className="divide-y divide-line">
            {items.map((item, index) => <TransactionRow key={transactionKey(item, index)} item={item} showDate={false} />)}
          </ul>
        </Card>
      ))}
      {data?.truncated && (
        <p className="text-center text-sm text-muted">
          แสดง {data.limit} รายการล่าสุดของเดือน ดูทั้งหมดได้ด้วยคำสั่ง “ส่งออกข้อมูล” ในแชต
        </p>
      )}
    </div>
  );
}
