import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { ApiError, sendMe, type Categories, type EditBody, type TransactionItem } from "../api";
import { closeWindow, sendToChat } from "../liff";
import { calendarDate } from "../money";
import { useMe, useSession } from "../session";
import { InlineError, Skeleton } from "./ui";

type Kind = TransactionItem["transaction_type"];
type Method = "PATCH" | "DELETE";

// Must match app.EDIT_RECEIPT on the bot side.
export function editReceipt(id: number): string {
  return `แก้รายการ #${id} แล้ว`;
}

const KINDS: { value: Kind; label: string }[] = [
  { value: "expense", label: "รายจ่าย" },
  { value: "income", label: "รายรับ" },
];
const FIELD_HINT = "ตรวจช่องนี้อีกครั้ง";
const DONE_MS = 800;
const ARM_MS = 3000;
// A second touch this soon after arming is a double tap, not a confirmation.
const CONFIRM_AFTER_MS = 400;

export function bangkokToday(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Bangkok" }).format(now);
}

// The row's own category stays selectable for its own type, so legacy rows save unchanged.
// A row saved without a category gets a real one instead, since an empty one cannot be saved.
export function categoryOptions(categories: Categories, kind: Kind, original: TransactionItem): string[] {
  const options = categories[kind];
  return kind === original.transaction_type && original.category && !options.includes(original.category)
    ? [original.category, ...options]
    : options;
}

function startingCategory(categories: Categories, kind: Kind, original: TransactionItem): string {
  return kind === original.transaction_type && original.category
    ? original.category
    : categories[kind][categories[kind].length - 1];
}

interface Draft {
  kind: Kind;
  amount: string;
  category: string;
  description: string;
  date: string;
}

// Hiding the app drops every rendered value (session.tsx), which unmounts this sheet.
// Remember which sheet was open and what was typed, in memory only, until it closes.
let open: { id: number; fromChat: boolean; draft: Draft | null } | null = null;

export const rememberedEdit = Object.assign(
  (): { id: number; fromChat: boolean } | null => (open ? { id: open.id, fromChat: open.fromChat } : null),
  { forget: () => { open = null; } },
);

const FOCUSABLE = "button:not([disabled]), input:not([disabled]), select:not([disabled])";

interface Props {
  id: number;
  fromChat: boolean;
  onClose: () => void;
  onChanged: () => void;
}

export function EditSheet({ id, fromChat, onClose, onChanged }: Props) {
  const item = useMe<TransactionItem>(`/api/me/transactions/${id}`);
  const categories = useMe<Categories>("/api/me/categories");
  const [gone, setGone] = useState(false);
  const busy = useRef(false);
  const titleId = useId();
  const title = useRef<HTMLHeadingElement>(null);
  const dialog = useRef<HTMLDivElement>(null);
  useState(() => {
    if (open?.id !== id) open = { id, fromChat, draft: null };
  });

  const close = () => {
    if (busy.current) return;
    rememberedEdit.forget();
    onClose();
  };

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    title.current?.focus();
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
      if (event.key !== "Tab" || !dialog.current) return;
      // Keep Tab inside the sheet: the page behind it is inert while it is open.
      const nodes = Array.from(dialog.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      const inside = active instanceof Node && dialog.current.contains(active);
      if (event.shiftKey && (active === first || !inside)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !inside)) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = overflow;
      window.removeEventListener("keydown", onKey);
      opener?.focus();
    };
    // Mount-only: close() reads the busy ref, so a stale closure is harmless.
  }, []);

  const finish = async (method: Method) => {
    rememberedEdit.forget();
    if (fromChat) {
      // The bot answers this with a card showing the saved values (app.EDIT_RECEIPT).
      if (method === "PATCH") await sendToChat(editReceipt(id)).catch(() => {});
      closeWindow();
    }
    onChanged();
    onClose();
  };

  let body: ReactNode;
  if (gone || item.error?.code === "NOT_FOUND") {
    body = (
      <div className="py-6 text-center">
        <p className="font-medium">รายการนี้ถูกลบไปแล้ว</p>
        <button type="button" onClick={close}
          className="mt-4 min-h-11 rounded-2xl bg-brand-soft px-6 font-medium text-brand">
          ปิด
        </button>
      </div>
    );
  } else if (item.error || categories.error) {
    body = <InlineError onRetry={() => { item.retry(); categories.retry(); }} />;
  } else if (item.data && categories.data) {
    body = (
      <EditForm item={item.data} categories={categories.data} busy={busy}
        onGone={() => setGone(true)} onDone={(method) => void finish(method)} />
    );
  } else {
    body = (
      <div className="space-y-3" aria-busy="true">
        <Skeleton className="h-11" /><Skeleton className="h-16" /><Skeleton className="h-11" /><Skeleton className="h-11" />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <div aria-hidden="true" onClick={close} className="sheet-backdrop absolute inset-0 bg-ink/40" />
      <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby={titleId}
        className="sheet relative max-h-[92dvh] w-full max-w-xl overflow-y-auto rounded-t-3xl bg-card px-4 pt-2 pb-[max(1.25rem,env(safe-area-inset-bottom))] shadow-[0_-8px_32px_-12px_rgba(120,40,80,.35)]">
        <div aria-hidden="true" className="mx-auto mb-2 h-1 w-10 rounded-full bg-line" />
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 id={titleId} ref={title} tabIndex={-1} className="font-display text-lg font-semibold outline-none">
            แก้ไขรายการ
          </h2>
          <button type="button" onClick={close} aria-label="ปิด"
            className="grid size-11 place-items-center rounded-full text-muted">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
        {body}
      </div>
    </div>
  );
}

interface FormProps {
  item: TransactionItem;
  categories: Categories;
  busy: { current: boolean };
  onGone: () => void;
  onDone: (method: Method) => void;
}

function EditForm({ item, categories, busy, onGone, onDone }: FormProps) {
  const { token, requireAuth } = useSession();
  const [saved] = useState(() => (open?.id === item.id ? open.draft : null));
  const [kind, setKind] = useState<Kind>(saved?.kind ?? item.transaction_type);
  const [amount, setAmount] = useState(saved?.amount ?? item.amount_baht);
  const [category, setCategory] = useState(
    () => saved?.category ?? startingCategory(categories, item.transaction_type, item),
  );
  const [description, setDescription] = useState(saved?.description ?? item.description ?? "");
  const [date, setDate] = useState(saved?.date ?? item.occurred_on);

  useEffect(() => {
    if (open?.id === item.id) open.draft = { kind, amount, category, description, date };
  }, [item.id, kind, amount, category, description, date]);
  const [sending, setSending] = useState(false);
  const [field, setField] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [armed, setArmed] = useState(false);
  const armedAt = useRef(0);
  const armTimer = useRef<number | undefined>(undefined);
  const [done, setDone] = useState<string | null>(null);
  const timers = useRef<number[]>([]);
  const ids = { amount: useId(), category: useId(), description: useId(), date: useId() };

  useEffect(() => () => {
    timers.current.forEach((timer) => window.clearTimeout(timer));
    window.clearTimeout(armTimer.current);
  }, []);

  const later = (callback: () => void, ms: number) => {
    timers.current.push(window.setTimeout(callback, ms));
  };

  const options = categoryOptions(categories, kind, item);

  const switchKind = (next: Kind) => {
    if (next === kind) return;
    setKind(next);
    // Back to the original type restores the original category, legacy ones included.
    setCategory(startingCategory(categories, next, item));
    setField(null);
  };

  const run = async (method: Method, message: string) => {
    if (!token || busy.current) return;
    busy.current = true;
    setSending(true);
    setField(null);
    setFailed(false);
    const body: EditBody | undefined = method === "PATCH"
      ? { transaction_type: kind, amount_baht: amount.trim(), category, description: description.trim() || null,
          occurred_on: date }
      : undefined;
    try {
      await sendMe(method, `/api/me/transactions/${item.id}`, token, body);
      setDone(message);
      later(() => {
        busy.current = false;
        onDone(method);
      }, DONE_MS);
    } catch (error) {
      busy.current = false;
      setSending(false);
      setArmed(false);
      if (error instanceof ApiError && error.status === 401) requireAuth();
      else if (error instanceof ApiError && error.code === "NOT_FOUND") onGone();
      else if (error instanceof ApiError && error.code === "INVALID_FIELD" && error.field && error.field !== "body") {
        setField(error.field);
      } else setFailed(true);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void run("PATCH", "บันทึกแล้ว");
  };

  const remove = () => {
    if (!armed) {
      setArmed(true);
      armedAt.current = Date.now();
      window.clearTimeout(armTimer.current);
      armTimer.current = window.setTimeout(() => setArmed(false), ARM_MS);
      return;
    }
    if (Date.now() - armedAt.current < CONFIRM_AFTER_MS) return;
    void run("DELETE", "ลบแล้ว");
  };

  if (done) {
    return (
      <p role="status" className="flex items-center justify-center gap-2 py-10 font-display text-lg font-medium text-income">
        <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2.4"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
        {done}
      </p>
    );
  }

  const income = kind === "income";
  const input = "min-h-11 w-full rounded-2xl border border-line bg-canvas px-3 text-base text-ink";
  const invalid = (name: string) => (field === name ? " border-expense" : "");

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <div role="radiogroup" aria-label="ประเภท" className="grid grid-cols-2 gap-1 rounded-full bg-canvas p-1">
        {KINDS.map((option) => {
          const active = kind === option.value;
          const tone = option.value === "income" ? "bg-income" : "bg-brand";
          return (
            <button key={option.value} type="button" role="radio" aria-checked={active}
              onClick={() => switchKind(option.value)}
              className={`min-h-11 rounded-full text-sm font-medium transition-colors duration-200 ${active ? `${tone} text-white` : "text-muted"}`}>
              {option.label}
            </button>
          );
        })}
      </div>
      <FieldHint show={field === "transaction_type"} />

      <div>
        <label htmlFor={ids.amount} className="text-sm text-muted">จำนวนเงิน</label>
        <div className={`mt-1 flex items-baseline gap-2 border-b-2 pb-1 transition-colors duration-200 ${field === "amount_baht" ? "border-expense" : income ? "border-income" : "border-brand"}`}>
          <span aria-hidden="true" className={`font-display text-2xl ${income ? "text-income" : "text-brand"}`}>฿</span>
          <input id={ids.amount} inputMode="decimal" autoComplete="off" value={amount}
            onChange={(event) => setAmount(event.target.value)}
            aria-invalid={field === "amount_baht"}
            className={`min-h-12 w-full bg-transparent font-display text-4xl font-semibold tabular-nums outline-none ${income ? "text-income" : "text-ink"}`} />
        </div>
        <FieldHint show={field === "amount_baht"} />
      </div>

      <div>
        <label htmlFor={ids.category} className="text-sm text-muted">หมวด</label>
        <select id={ids.category} value={category} onChange={(event) => setCategory(event.target.value)}
          aria-invalid={field === "category"} className={`mt-1 ${input}${invalid("category")}`}>
          {options.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
        <FieldHint show={field === "category"} />
      </div>

      <div>
        <label htmlFor={ids.description} className="text-sm text-muted">รายละเอียด</label>
        <input id={ids.description} value={description} maxLength={500} placeholder="ไม่ใส่ก็ได้"
          onChange={(event) => setDescription(event.target.value)}
          aria-invalid={field === "description"} className={`mt-1 ${input}${invalid("description")}`} />
        <FieldHint show={field === "description"} />
      </div>

      <div>
        <label htmlFor={ids.date} className="text-sm text-muted">วันที่</label>
        {/* iOS draws a native date input in the phone's language and lets it overflow; show
            the Thai date instead and lay the transparent native input over it for the picker. */}
        <div className={`relative mt-1 flex items-center ${input}${invalid("occurred_on")}`}>
          <span aria-hidden="true">{calendarDate(date)}</span>
          <input id={ids.date} type="date" value={date} min="2000-01-01" max={bangkokToday()} required
            onChange={(event) => { if (event.target.value) setDate(event.target.value); }}
            aria-invalid={field === "occurred_on"}
            className="absolute inset-0 block h-full w-full min-w-0 appearance-none opacity-0" />
        </div>
        <FieldHint show={field === "occurred_on"} />
      </div>

      {failed && <InlineError />}

      <div className="space-y-2 pt-2">
        <button type="submit" disabled={sending}
          className="min-h-12 w-full rounded-2xl bg-brand font-display font-medium text-white shadow-[0_6px_16px_-8px_rgba(216,27,114,.7)] disabled:opacity-60">
          บันทึก
        </button>
        <button type="button" onClick={remove} disabled={sending} aria-live="polite"
          className={`min-h-11 w-full rounded-2xl text-sm font-medium transition-colors duration-200 disabled:opacity-60 ${armed ? "bg-expense text-white" : "text-expense"}`}>
          {armed ? "แตะอีกครั้งเพื่อลบ" : "ลบรายการนี้"}
        </button>
      </div>
    </form>
  );
}

function FieldHint({ show }: { show: boolean }) {
  return show ? <p role="alert" className="mt-1 text-sm text-expense">{FIELD_HINT}</p> : null;
}
