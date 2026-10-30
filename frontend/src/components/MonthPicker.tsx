import { monthLabel, shiftMonth, type YearMonth } from "../money";

function Arrow({ direction }: { direction: "left" | "right" }) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={direction === "left" ? "M15 6l-6 6 6 6" : "M9 6l6 6-6 6"} />
    </svg>
  );
}

export function MonthPicker({ value, onChange }: { value: YearMonth; onChange: (next: YearMonth) => void }) {
  const previous = shiftMonth(value, -1);
  const next = shiftMonth(value, 1);
  const button = "grid size-11 place-items-center rounded-full text-brand disabled:opacity-30";
  return (
    <div className="flex items-center justify-between rounded-full bg-brand-soft/60 px-1">
      <button type="button" className={button} disabled={!previous} onClick={() => previous && onChange(previous)}
        aria-label="เดือนก่อนหน้า">
        <Arrow direction="left" />
      </button>
      <span className="font-display font-medium" aria-live="polite">{monthLabel(value.month, value.yearCe + 543)}</span>
      <button type="button" className={button} disabled={!next} onClick={() => next && onChange(next)}
        aria-label="เดือนถัดไป">
        <Arrow direction="right" />
      </button>
    </div>
  );
}
