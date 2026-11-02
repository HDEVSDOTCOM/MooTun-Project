export type ErrorCode =
  | "UNAUTHORIZED"
  | "AUTH_UNAVAILABLE"
  | "DATA_UNAVAILABLE"
  | "WEBAPP_UNAVAILABLE"
  | "INVALID_REQUEST"
  | "NOT_FOUND"
  | "INVALID_FIELD";

export class ApiError extends Error {
  constructor(readonly status: number, readonly code: ErrorCode, readonly field?: string) {
    super(code);
  }
}

export interface Summary {
  year_ce: number;
  year_be: number;
  month: number;
  income_baht: string;
  expense_baht: string;
  balance_baht: string;
  transaction_count: number;
  as_of: string;
}

export interface TransactionItem {
  id: number;
  transaction_type: "income" | "expense";
  amount_baht: string;
  category: string;
  description: string | null;
  occurred_on: string;
  created_at: string;
}

export interface RecentTransactions {
  items: TransactionItem[];
  as_of: string;
}

export interface MonthTransactions {
  year_ce: number;
  year_be: number;
  month: number;
  type: "income" | "expense" | null;
  limit: number;
  truncated: boolean;
  items: TransactionItem[];
  as_of: string;
}

export interface SavingsGoal {
  title: string;
  target_baht: string;
  saved_baht: string;
  remaining_baht: string;
  progress_percent: string;
  deadline: string | null;
}

export interface Savings {
  goal: SavingsGoal | null;
  as_of: string;
}

export interface MonthlySeries {
  months: number;
  items: {
    year_ce: number;
    year_be: number;
    month: number;
    income_baht: string;
    expense_baht: string;
    income_satang: number;
    expense_satang: number;
  }[];
  as_of: string;
}

export interface CategoryTotals {
  type: "income" | "expense";
  total_baht: string;
  total_satang: number;
  items: {
    category: string;
    amount_baht: string;
    amount_satang: number;
    transaction_count: number;
    share_percent: string;
  }[];
  as_of: string;
}

const KNOWN: ReadonlySet<string> = new Set([
  "UNAUTHORIZED", "AUTH_UNAVAILABLE", "DATA_UNAVAILABLE", "WEBAPP_UNAVAILABLE", "INVALID_REQUEST",
  "NOT_FOUND", "INVALID_FIELD",
]);

export interface Categories {
  expense: string[];
  income: string[];
}

export interface EditBody {
  transaction_type: "income" | "expense";
  amount_baht: string;
  category: string;
  description: string | null;
  occurred_on: string;
}

async function readBody(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function toError(response: Response, body: unknown): ApiError {
  const { code, field } = (body ?? {}) as { code?: unknown; field?: unknown };
  const known = typeof code === "string" && KNOWN.has(code) ? (code as ErrorCode) : null;
  return new ApiError(
    response.status,
    known ?? (response.status === 401 ? "UNAUTHORIZED" : "DATA_UNAVAILABLE"),
    typeof field === "string" ? field : undefined,
  );
}

// Every financial read carries the LINE ID token; no cookies, no HTTP cache.
export async function getMe<T>(path: string, token: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    credentials: "omit",
    signal,
  });
  const body = await readBody(response);
  if (!response.ok) throw toError(response, body);
  if (body === null) throw new ApiError(response.status, "DATA_UNAVAILABLE");
  return body as T;
}

// The edit form's only writes. Same bearer-only transport as reads; 204 resolves to null.
export async function sendMe(
  method: "PATCH" | "DELETE",
  path: string,
  token: string,
  body?: EditBody,
): Promise<TransactionItem | null> {
  const response = await fetch(path, {
    method,
    headers: body
      ? { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }
      : { Authorization: `Bearer ${token}` },
    ...(body ? { body: JSON.stringify(body) } : {}),
    cache: "no-store",
    credentials: "omit",
  });
  if (response.status === 204) return null;
  const parsed = await readBody(response);
  if (!response.ok) throw toError(response, parsed);
  if (parsed === null) throw new ApiError(response.status, "DATA_UNAVAILABLE");
  return parsed as TransactionItem;
}
