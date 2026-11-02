# MooTun Mini App Edit Form (Phase 2A, part B) — Design Spec

**Status:** `DRAFT — awaiting owner review`
**Repository baseline:** `main` after PR #7 (always-on Help chips)
**Follows:** `phase2a_chat_cards_spec.md` (part A, shipped)

**Owner decisions (2026-11-02):** every field is editable and the form has a delete
button; saving sends nothing to the chat (the form just closes); approach A — a
separate write API, the existing read APIs stay read-only.

## 1. Outcome

A user can fix or delete any of their own transactions from the Mini App, opened
either from ✏️ on a chat card or by tapping a row in the Transactions tab.

Success criteria:

- ✏️ on a card opens the form for that exact transaction.
- Every field (type, amount, category, description, date) can be changed; the
  saved row is what the user sees on the next load of any Mini App tab.
- Delete needs two taps and never uses a browser dialog.
- A user can never read, change or delete another user's row, and cannot learn
  whether another user's id exists.
- All existing `/api/me/*` read endpoints stay on the read-only session.

Out of scope: chat messages after saving (no push, no `liff.sendMessages`), undo
for deletes made in the form, editing savings goals, bulk edit, optimistic
concurrency (last write wins; only the owner edits their rows).

## 2. User-facing behaviour

### 2.1 Entry points

| From | Opens |
|---|---|
| ✏️ on a record / edit / restore card | `https://liff.line.me/<liff_id>/transactions?edit=<id>` → Transactions tab with the sheet open for `<id>` |
| Tap a row in the Transactions tab | Same sheet for that row |

The Transactions page reads `edit` from the URL once on load; a value that is not
1–9 digits is ignored (plain Transactions tab).

### 2.2 Edit sheet

Bottom sheet over the Transactions page, title "แก้ไขรายการ".

| Field | Control | Rule |
|---|---|---|
| ประเภท | segmented รายจ่าย / รายรับ | switching type reloads the category options |
| จำนวนเงิน | text input, `inputMode="decimal"` | > 0, at most 2 decimals, same limits as chat |
| หมวด | select from `/api/me/categories` for the chosen type | the row's current category is always offered, even if not in the list (legacy rows) |
| รายละเอียด | text input | optional, ≤ 500 chars, trimmed, empty → none |
| วันที่ | `type="date"` | not after today (Bangkok), not before 2000-01-01 |

Buttons: บันทึก (primary, disabled while sending), ลบรายการนี้ (text button, red).

### 2.3 Save and delete

- **Save** → `PATCH`; on success the sheet shows "บันทึกแล้ว" for ~0.8 s, then:
  opened from chat (`?edit=`) → `liff.closeWindow()`; opened from the list → sheet
  closes and the month list reloads.
- **Delete** → first tap turns the button into "แตะอีกครั้งเพื่อลบ" for 3 s; the
  second tap within that window sends `DELETE`; afterwards same as save
  ("ลบแล้ว").
- Errors:
  - 404 → "รายการนี้ถูกลบไปแล้ว" with a ปิด button (no fields).
  - 422 → message under the offending field; inputs kept.
  - Network / 5xx → existing `InlineError` with retry; inputs kept.
  - 401 → existing session recovery (login) flow.

## 3. Architecture

### 3.1 Backend

| Unit | Change |
|---|---|
| `webapp_routes.py` | `_transaction_item` adds `id`. New `write_session` dependency (normal `Session`, commit on success, rollback on error, opened only after `verified_owner`). New routes below. |
| `webapp_routes.py` | `GET /api/me/transactions/{tx_id}`, `PATCH /api/me/transactions/{tx_id}`, `DELETE /api/me/transactions/{tx_id}`, `GET /api/me/categories` |
| `repository.py` | `update_transaction(user, tx_id, *, transaction_type, amount, category, description, occurred_on, session)` and `delete_transaction_by_id(user, tx_id, *, session)`; both scoped by `line_user_id`, return `None` when not found, and drop a pending `confirm_delete` that targets the row |
| `taxonomy.py` | `categories(transaction_type) -> tuple[str, ...]`: unique categories from `CATEGORY_RULES` plus the fallback, in a stable order |
| `flex.py` | ✏️ URI gains `?edit=<tx.id>` |

API contract:

- `tx_id` path segment: 1–9 digits, otherwise 404.
- `GET /api/me/transactions/{tx_id}` → the `_transaction_item` shape (with `id`).
- `PATCH` body (JSON, all five keys required, unknown keys → 422):
  `{"transaction_type": "expense"|"income", "amount_baht": "<decimal string>",
  "category": str, "description": str|null, "occurred_on": "YYYY-MM-DD"}`.
  Amount goes through `baht_to_satang` (Decimal, never float). Category must be in
  `categories(type)` **or** equal the row's current category. 200 → updated item.
- `DELETE` → 204.
- `GET /api/me/categories` → `{"expense": [...], "income": [...]}`.
- Not found and "belongs to someone else" both return the same 404
  `{"error": "NOT_FOUND"}`.
- 422 body: `{"error": "INVALID", "field": "<name>"}` so the form can place the
  message.
- Auth is the existing Bearer LIFF ID token (no cookies, so no CSRF surface).
  Query strings on the new routes are rejected like the existing allowlist does.

### 3.2 Pending-state interaction

- Edit or delete of a row that a pending `confirm_delete` targets removes that
  pending action, so a later "ยืนยัน" cannot act on a row whose values changed or
  no longer exist (the user gets the existing "nothing to confirm" reply).
- `undo_delete` snapshots are untouched (they refer to an already-deleted row).
- Pending transaction drafts are untouched.

### 3.3 Frontend

| Unit | Change |
|---|---|
| `api.ts` | `TransactionItem.id`; `sendMe(method, path, token, body?)` for PATCH/DELETE; `Categories` type |
| `components/EditSheet.tsx` (new) | the sheet: load item + categories, form state, save, two-tap delete, error states |
| `routes/Transactions.tsx` | rows become buttons that open the sheet; read `?edit=` once; reload after save/delete |
| `components/TransactionRow.tsx` | optional `onSelect` making the row a full-width button (≥ 44 px tall) |
| `liff.ts` | `closeWindow()` wrapper |

Visual polish (sheet motion, spacing, focus states) uses the design skills during
implementation, matching the existing tokens (brand #D81B72, Prompt font).

## 4. Invariants and limits

- Money stays integer satang; the API accepts and returns decimal strings.
- Dates are Bangkok calendar dates; "today" uses Asia/Bangkok.
- The read-only session and its SELECT-only guard are unchanged for every
  existing endpoint and for the new GET item and categories routes; only `PATCH`
  and `DELETE` use `write_session`.
- No schema change, no migration.

## 5. Tests

Backend (pytest):

- GET/PATCH/DELETE own row succeed; other user's id and missing id → identical 404.
- PATCH validation: bad type, amount `0`, `-1`, `1.234`, `abc`, float-looking JSON
  number, unknown category, future date, unknown key, missing key → 422 with field.
- Legacy category kept when unchanged; amount stored in satang exactly.
- Edit and delete each remove a pending `confirm_delete` on that row and leave one
  on another row alone; `undo_delete` and drafts untouched.
- Existing read endpoints still raise on write attempts (guard test unchanged).
- Card ✏️ URI contains `?edit=<id>`; `/app/transactions?edit=5` serves the shell.

Frontend (Vitest):

- `?edit=12` opens the sheet for 12; junk values are ignored.
- Switching type swaps the category options; legacy category is offered.
- Save sends the expected body and closes; from-chat path calls `closeWindow`.
- Delete needs two taps within 3 s; one tap then timeout does nothing.
- 404 and 422 render their messages.

## 6. Rollout

1. Merge → Render deploys backend and the built Mini App together.
2. Phone test: ✏️ from a new card, edit amount and category, back in chat; tap a
   row in the Transactions tab, delete it with two taps.
3. No LINE console change is needed (no new LIFF scopes).
