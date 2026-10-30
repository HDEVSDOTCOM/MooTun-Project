import type { Savings as SavingsData, SavingsGoal } from "../api";
import { Card, CardTitle, Empty, InlineError, Skeleton } from "../components/ui";
import { baht, calendarDate } from "../money";
import { useMe } from "../session";

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function Savings() {
  const { data, error, loading, retry } = useMe<SavingsData>("/api/me/savings");
  return (
    <div className="space-y-4">
      {loading && <Skeleton className="h-80 rounded-3xl" />}
      {error && <InlineError onRetry={retry} />}
      {data && !data.goal && (
        <Card>
          <CardTitle>เป้าหมายการออม</CardTitle>
          <Empty title="ยังไม่มีเป้าหมาย" hint="ลองพิมพ์ “ตั้งเป้า 1500 ซื้อหนังสือ” ในแชต" />
        </Card>
      )}
      {data?.goal && <Goal goal={data.goal} />}
      <Card>
        <CardTitle>เพิ่มเงินออม</CardTitle>
        <p className="text-sm text-muted">
          พิมพ์ในแชต เช่น <span className="font-medium text-ink">“ออม 100”</span> ยอดออมแยกจากรายรับรายจ่ายของเดือน
        </p>
      </Card>
    </div>
  );
}

function Goal({ goal }: { goal: SavingsGoal }) {
  // Ring geometry only; every visible number is the exact string from the API.
  const ratio = Math.min(100, Math.max(0, Number(goal.progress_percent))) / 100;
  const done = goal.remaining_baht === "0.00";
  return (
    <Card>
      <CardTitle>{goal.title}</CardTitle>
      <div className="flex flex-col items-center">
        <div className="relative size-40">
          <svg viewBox="0 0 120 120" className="size-full -rotate-90" aria-hidden="true">
            <circle cx="60" cy="60" r={RADIUS} fill="none" strokeWidth="12" className="stroke-brand-soft" />
            <circle cx="60" cy="60" r={RADIUS} fill="none" strokeWidth="12" strokeLinecap="round"
              className={done ? "stroke-income" : "stroke-brand"}
              strokeDasharray={CIRCUMFERENCE} strokeDashoffset={CIRCUMFERENCE * (1 - ratio)} />
          </svg>
          <div className="absolute inset-0 grid place-content-center text-center">
            <span className="font-display text-2xl font-semibold tabular-nums">{goal.progress_percent}%</span>
            <span className="text-xs text-muted">{done ? "ถึงเป้าแล้ว 🎉" : "ความคืบหน้า"}</span>
          </div>
        </div>
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-2xl bg-brand-soft/60 p-2">
          <dt className="text-xs text-muted">ออมแล้ว</dt>
          <dd className="font-semibold tabular-nums">{baht(goal.saved_baht)}</dd>
        </div>
        <div className="rounded-2xl bg-brand-soft/60 p-2">
          <dt className="text-xs text-muted">เป้าหมาย</dt>
          <dd className="font-semibold tabular-nums">{baht(goal.target_baht)}</dd>
        </div>
        <div className="rounded-2xl bg-brand-soft/60 p-2">
          <dt className="text-xs text-muted">เหลือ</dt>
          <dd className="font-semibold tabular-nums">{baht(goal.remaining_baht)}</dd>
        </div>
      </dl>
      {goal.deadline && <p className="mt-3 text-center text-sm text-muted">กำหนด {calendarDate(goal.deadline)}</p>}
    </Card>
  );
}
