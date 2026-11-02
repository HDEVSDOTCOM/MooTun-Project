import type { TransactionItem } from "../api";
import { baht, calendarDate } from "../money";

export function transactionKey(item: TransactionItem): string {
  return String(item.id);
}

export function TransactionRow({ item, showDate = true, onSelect }: {
  item: TransactionItem;
  showDate?: boolean;
  onSelect?: () => void;
}) {
  const income = item.transaction_type === "income";
  const content = (
    <>
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
    </>
  );
  const layout = "flex w-full items-center justify-between gap-3 py-3 text-left";
  return (
    <li>
      {onSelect ? (
        <button type="button" onClick={onSelect} className={`${layout} min-h-11 rounded-xl active:bg-brand-soft/50`}>
          {content}
        </button>
      ) : (
        <div className={layout}>{content}</div>
      )}
    </li>
  );
}
