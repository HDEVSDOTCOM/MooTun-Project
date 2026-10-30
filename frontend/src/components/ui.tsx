import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-3xl bg-card p-4 shadow-[0_1px_2px_rgba(120,40,80,.06),0_8px_24px_-12px_rgba(120,40,80,.18)] ${className}`}>
      {children}
    </section>
  );
}

export function CardTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="font-display text-lg font-semibold">{children}</h2>
      {action}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-xl bg-brand-soft/70 ${className}`} />;
}

export function InlineError({ onRetry }: { onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-2xl bg-expense-soft/60 p-3 text-sm">
      <span>ข้อมูลไม่พร้อมใช้งานชั่วคราว กรุณาลองอีกครั้ง</span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="min-h-11 shrink-0 rounded-xl px-3 font-medium text-brand">
          ลองอีกครั้ง
        </button>
      )}
    </div>
  );
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="py-6 text-center">
      <p className="font-medium">{title}</p>
      {hint && <p className="mt-1 text-sm text-muted">{hint}</p>}
    </div>
  );
}
