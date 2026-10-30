import type { TransactionItem } from "../api";
import { baht, calendarDate } from "../money";

export function transactionKey(item: TransactionItem, index: number): string {
  return `${index}-${item.created_at}-${item.amount_baht}`;
}

export function TransactionRow({ item, showDate = true }: { item: TransactionItem; showDate?: boolean }) {
  const income = item.transaction_type === "income";
  return (
    <li className="flex items-center justify-between gap-3 py-3">
      <div className="min-w-0">
        <p className="truncate font-medium">{item.description ?? item.category}</p>
        <p className="text-xs text-muted">
          {item.category}
          {showDate && ` · ${calendarDate(item.occurred_on)}`}
        </p>
      </div>
      <p className={`shrink-0 tabular-nums font-semibold ${income ? "text-income" : "text-expense"}`}>
        <span className="sr-only">{income ? "รายรับ " : "รายจ่าย "}</span>
        {income ? "+" : "−"}{baht(item.amount_baht)}
      </p>
    </li>
  );
}
