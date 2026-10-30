// Display helpers for exact decimal strings from the API. Never parse money as a float.

const DECIMAL = /^(-?)(\d+)\.(\d{2})$/;

export function baht(value: string): string {
  const match = DECIMAL.exec(value);
  if (!match) throw new Error("INVALID_AMOUNT");
  const [, sign, integer, fraction] = match;
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${sign ? "−" : ""}฿${grouped}.${fraction}`;
}

export function isNegative(value: string): boolean {
  return value.startsWith("-") && !/^-0\.00$/.test(value);
}

const THAI_MONTHS = [
  "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
  "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
];

export function monthLabel(month: number, yearBe: number): string {
  return `${THAI_MONTHS[month - 1]} ${yearBe}`;
}

// "2026-10-02" (CE calendar date) -> "2 ต.ค. 2569"
export function calendarDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  return `${day} ${THAI_MONTHS[month - 1]} ${year + 543}`;
}

export function monthParam(yearCe: number, month: number): string {
  return `${yearCe}-${String(month).padStart(2, "0")}`;
}

export interface YearMonth {
  yearCe: number;
  month: number;
}

// Matches the API's accepted range (1900-01 .. 2099-12).
export function shiftMonth({ yearCe, month }: YearMonth, delta: number): YearMonth | null {
  const index = yearCe * 12 + (month - 1) + delta;
  const next = { yearCe: Math.floor(index / 12), month: (index % 12) + 1 };
  return next.yearCe < 1900 || next.yearCe > 2099 ? null : next;
}

// Fallback when the server summary is unavailable: today's month in Bangkok.
export function bangkokMonth(now: Date = new Date()): YearMonth {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Bangkok", year: "numeric", month: "2-digit" })
    .formatToParts(now);
  const value = (type: string) => Number(parts.find((part) => part.type === type)?.value);
  return { yearCe: value("year"), month: value("month") };
}

export function percentWidth(value: string): string {
  // Display-only geometry from an exact percent string; clamp to the drawable range.
  const number = Number(value);
  return `${Math.min(100, Math.max(0, Number.isFinite(number) ? number : 0))}%`;
}
