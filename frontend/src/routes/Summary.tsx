import { Link } from "react-router-dom";
import type { CategoryTotals, RecentTransactions, Summary as SummaryData } from "../api";
import { Card, CardTitle, Empty, InlineError, Skeleton } from "../components/ui";
import { baht, calendarDate, isNegative, monthLabel, monthParam } from "../money";
import { useMe, useSession } from "../session";

export function Summary() {
  const { summary, summaryError, reload } = useSession();
  return (
    <div className="space-y-4">
      {summary ? <Totals data={summary} /> : summaryError && <InlineError onRetry={reload} />}
      {summary && <TopCategories data={summary} />}
      <Recent />
    </div>
  );
}

function Totals({ data }: { data: SummaryData }) {
  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <h2 className="font-display text-lg font-semibold">สรุป</h2>
        <span className="rounded-full bg-brand-soft px-3 py-1 text-sm text-brand">
          {monthLabel(data.month, data.year_be)}
        </span>
      </div>
      <p className="mt-3 text-sm text-muted">คงเหลือเดือนนี้</p>
      <p className={`font-display text-3xl font-semibold tabular-nums ${isNegative(data.balance_baht) ? "text-expense" : "text-income"}`}>
        {baht(data.balance_baht)}
      </p>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-2xl bg-expense-soft p-3">
          <p className="text-xs text-expense">รายจ่าย</p>
          <p className="font-display text-lg font-semibold tabular-nums text-expense">{baht(data.expense_baht)}</p>
        </div>
        <div className="rounded-2xl bg-income-soft p-3">
          <p className="text-xs text-income">รายรับ</p>
          <p className="font-display text-lg font-semibold tabular-nums text-income">{baht(data.income_baht)}</p>
        </div>
      </div>
      <p className="mt-3 text-xs text-muted">
        {data.transaction_count} รายการ · สุทธิของเดือน ไม่ใช่ยอดเงินในธนาคาร
      </p>
    </Card>
  );
}

function TopCategories({ data }: { data: SummaryData }) {
  const path = `/api/me/analytics/categories?month=${monthParam(data.year_ce, data.month)}&type=expense`;
  const { data: totals, error, loading, retry } = useMe<CategoryTotals>(path);
  return (
    <Card>
      <CardTitle>รายจ่ายตามหมวด</CardTitle>
      {loading && <div className="space-y-3"><Skeleton className="h-8" /><Skeleton className="h-8" /><Skeleton className="h-8" /></div>}
      {error && <InlineError onRetry={retry} />}
      {totals && totals.items.length === 0 && <Empty title="ยังไม่มีรายจ่ายเดือนนี้" hint="ลองพิมพ์ “ข้าว 50” ในแชต" />}
      {totals && totals.items.length > 0 && (
        <ul className="space-y-3">
          {totals.items.slice(0, 5).map((item) => (
            <li key={item.category}>
              <div className="flex justify-between gap-3 text-sm">
                <span>{item.category}</span>
                <span className="tabular-nums font-medium">{baht(item.amount_baht)}</span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-brand-soft">
                <div className="h-full rounded-full bg-brand" style={{ width: `${item.share_percent}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Recent() {
  const { data, error, loading, retry } = useMe<RecentTransactions>("/api/me/transactions/recent");
  return (
    <Card>
      <CardTitle action={<Link to="/transactions" className="min-h-11 content-center text-sm text-brand">ดูทั้งหมด</Link>}>
        รายการล่าสุด
      </CardTitle>
      {loading && <div className="space-y-3"><Skeleton className="h-12" /><Skeleton className="h-12" /></div>}
      {error && <InlineError onRetry={retry} />}
      {data && data.items.length === 0 && <Empty title="ยังไม่มีรายการ" hint="จดผ่านแชตกับน้องหมูตุ๋นได้เลย" />}
      {data && data.items.length > 0 && (
        <ul className="divide-y divide-line">
          {data.items.map((item) => (
            <li key={`${item.created_at}-${item.occurred_on}-${item.amount_baht}-${item.category}`} className="flex items-center justify-between gap-3 py-3">
              <div className="min-w-0">
                <p className="truncate font-medium">{item.description ?? item.category}</p>
                <p className="text-xs text-muted">{item.category} · {calendarDate(item.occurred_on)}</p>
              </div>
              <p className={`shrink-0 tabular-nums font-semibold ${item.transaction_type === "income" ? "text-income" : "text-expense"}`}>
                {item.transaction_type === "income" ? "+" : "−"}{baht(item.amount_baht)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
