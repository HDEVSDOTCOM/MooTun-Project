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
