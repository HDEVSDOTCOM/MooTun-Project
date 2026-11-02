# Mini App Edit Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user edit or delete any of their own transactions from a Mini App bottom sheet, opened from a chat card's ✏️ or a Transactions row.

**Architecture:** Backend adds by-id repository writes, a category list in `taxonomy.py`, and a small JSON body validator (`webapp_edit.py`); `webapp_routes.py` gains GET/PATCH/DELETE item routes plus categories, with PATCH/DELETE using a committing `database.session_scope()` while every read keeps `ReadOnlySession`. Frontend adds `sendMe`, `closeWindow`, and an `EditSheet` component wired into the Transactions route.

**Tech Stack:** FastAPI, SQLAlchemy 2, pytest; React + TypeScript, react-router-dom, Vitest + Testing Library.

**Spec:** `plan/active/phase2b_edit_form_spec.md`

## Global Constraints

- Money is integer satang; parse amounts with `Decimal` via `repository.baht_to_satang`, never float.
- Dates: "today" = `routes.utc_now().astimezone(BANGKOK).date()`; earliest allowed date `2000-01-01`.
- Error JSON keeps the existing shape `{"code", "message"}` from `webapp_auth.ERROR_MESSAGES`; 422 adds `"field"`.
- Not found and other-user rows return the identical `404 {"code": "NOT_FOUND", ...}`.
- Every existing `/api/me/*` route keeps `ReadOnlySession`; new GET routes also use it. Only PATCH and DELETE write.
- No schema change. No new LIFF scope. No chat message after save.
- Thai copy (exact): sheet title `แก้ไขรายการ`; buttons `บันทึก`, `ลบรายการนี้`, `แตะอีกครั้งเพื่อลบ`, `ปิด`; toasts `บันทึกแล้ว`, `ลบแล้ว`; 404 text `รายการนี้ถูกลบไปแล้ว`; 422 text `ตรวจช่องนี้อีกครั้ง`.

## Review Focus

- A JSON number amount such as `50.1` (not a string) must be rejected (422 `amount_baht`), never coerced through float.
- A request body that is not a JSON object (array, string, invalid JSON, >4 KB) → 422 / 400, never 500.
- `?edit=` pointing at another user's id or a deleted id shows `รายการนี้ถูกลบไปแล้ว`, not a blank sheet or spinner forever.
- Switching type then back must not silently drop a legacy category the row had.
- A `PATCH`/`DELETE` with a query string is rejected 400 like every other `/api/me/*` route.

---

### Task 1: Category list and by-id writes

**Files:**
- Modify: `taxonomy.py` (add `categories`, export it)
- Modify: `repository.py` (add `update_transaction`, `delete_transaction_by_id`, `_drop_confirm_delete_for`)
- Test: `test_edit_repository.py` (new)

**Interfaces:**
- Produces:
  - `taxonomy.categories(transaction_type: TransactionType) -> tuple[str, ...]` — unique `rule.category` of `CATEGORY_RULES` with that type in first-seen order, then `fallback_category(type)` if not already present.
  - `repository.update_transaction(line_user_id: str, transaction_id: int, *, transaction_type: str, amount: MoneyInput, category: str, description: str | None, occurred_on: date, session: Session | None = None) -> Transaction | None`
  - `repository.delete_transaction_by_id(line_user_id: str, transaction_id: int, *, session: Session | None = None) -> bool`
  - Both return `None`/`False` for missing or other-user rows, and remove the user's `PendingAction` only when `action_type == "confirm_delete"` and `target_transaction_id == transaction_id`.

- [ ] **Step 1: Write failing tests** in `test_edit_repository.py` (tmp_path SQLite via `database.configure_database`, like `test_cards_repository.py`):
  - `test_categories_are_unique_and_end_with_fallback`: `categories("expense")[-1] == "อื่นๆ"`, `categories("income")[-1] == "รายรับอื่นๆ"`, no duplicates, `"อาหาร" in categories("expense")`.
  - `test_update_transaction_replaces_every_field`: amount `"12.34"` → `amount_satang == 1234`; type, category, description (`"  "` → `None`), occurred_on all changed; `created_at` unchanged.
  - `test_update_and_delete_other_user_row_returns_none`: user B gets `None` / `False`; row A unchanged.
  - `test_update_rejects_bad_type_and_amount`: `ValueError` for type `"x"`, amount `"0"`, `"1.234"`.
  - `test_write_drops_confirm_delete_for_that_row_only` (parametrize update/delete): pending `confirm_delete` on the row → gone; on another row → kept; `undo_delete` action → kept; `PendingTransaction` draft → kept.
  - `test_delete_transaction_by_id_removes_row`.
- [ ] **Step 2: Run** `pytest test_edit_repository.py -q` — Expected: FAIL (import errors).
- [ ] **Step 3: Implement** the three functions and `categories`. Reuse `_validate_user_id`, `_validate_transaction_type`, `baht_to_satang`, `_session_context`; strip category and reject empty like `update_latest_transaction`.
- [ ] **Step 4: Run** `pytest test_edit_repository.py test_cards_repository.py -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: by-id transaction edit and delete in the repository`.

### Task 2: Write API and card link

**Files:**
- Create: `webapp_edit.py` (body validation only)
- Modify: `webapp_auth.py` (`WebAppError.field`, `ERROR_MESSAGES["INVALID_FIELD"] = "ข้อมูลไม่ถูกต้อง"`)
- Modify: `webapp_routes.py` (`id` in `_transaction_item`, 4 routes, `error_response` adds `field` when set)
- Modify: `flex.py` (✏️ URI)
- Test: `test_webapp_edit.py` (new; imports `web`, `seed`, tokens, `A`, `B` from `test_webapp`), `test_flex.py`

**Interfaces:**
- Consumes: Task 1 functions.
- Produces:
  - `WebAppError(status_code: int, code: str, field: str | None = None)`.
  - `webapp_edit.EditFields` frozen dataclass `(transaction_type: str, amount_baht: str, category: str, description: str | None, occurred_on: date)`.
  - `webapp_edit.parse_edit_body(raw: bytes, *, today: date, current_category: str) -> EditFields` — raises `WebAppError(422, "INVALID_FIELD", field)`; `field` is the offending key, or `"body"` for non-object / invalid JSON / > 4096 bytes / missing or unknown keys. Amount must be a JSON string matching `^[0-9]{1,9}(\.[0-9]{1,2})?$` and > 0. Category must be in `taxonomy.categories(type)` or equal `current_category`. Description ≤ 500 chars after strip, `""` → `None`.
  - Routes (all paths `/api/me/transactions/{tx_id}` with `tx_id: str`; non-`[0-9]{1,9}` → 404):
    - `GET` → `_transaction_item` (uses `ReadSession`).
    - `PATCH` → 200 updated item; `DELETE` → 204. Both: `owner: Owner` (rejects query strings), read body with `await request.body()`, then `with database.session_scope() as session:`; `SQLAlchemyError` → `WebAppError(503, "DATA_UNAVAILABLE")`.
    - `GET /api/me/categories` → `{"expense": [...], "income": [...]}` (no DB session).
  - `TransactionItem` JSON gains `"id": int`.
  - Card ✏️ URI: `https://liff.line.me/{liff_id}/transactions?edit={tx.id}`.

- [ ] **Step 1: Write failing tests** in `test_webapp_edit.py`:
  - `test_items_include_id` (month list and recent).
  - `test_get_patch_delete_own_row`: PATCH body `{"transaction_type":"income","amount_baht":"99.50","category":"รายรับอื่นๆ","description":"แก้","occurred_on":"2026-10-03"}` → 200, DB `amount_satang == 9950`; DELETE → 204 then GET → 404.
  - `test_other_user_and_missing_ids_are_identical_404` (GET/PATCH/DELETE with token B on A's id, and id `999999`, and id `abc`): same status and JSON.
  - `test_patch_validation` parametrized → 422 with `field`: type `"x"`→`transaction_type`; amount `"0"`, `"-1"`, `"1.234"`, `"abc"`, `50.1` (number) → `amount_baht`; category `"ไม่มีหมวดนี้"` → `category`; date tomorrow, `"1999-12-31"`, `"2026-13-01"` → `occurred_on`; extra key, missing key, `[]`, `b"not json"`, 5000-byte body → `body`.
  - `test_patch_keeps_legacy_category` (seeded `"อาหาร A"` accepted unchanged).
  - `test_write_routes_reject_query_and_missing_token` (`?x=1` → 400, no token → 401, DB untouched).
  - `test_reads_still_use_read_only_session` (extend the existing assertion style: new GET item route session is `ReadOnlySession`).
  - In `test_flex.py`: ✏️ uri ends with `/transactions?edit=<id>`.
  - `test_shell_serves_transactions_with_edit_query`: `/app/transactions?edit=5` → 200 shell.
- [ ] **Step 2: Run** `pytest test_webapp_edit.py test_flex.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** `webapp_edit.py`, the `WebAppError`/`error_response` change, routes, and the flex URI.
- [ ] **Step 4: Run** `pytest -q` — Expected: all pass (existing `test_webapp.py` included).
- [ ] **Step 5: Commit** `feat: Mini App write API for editing and deleting a transaction`.

### Task 3: Edit sheet in the Mini App

**Files:**
- Modify: `frontend/src/api.ts`, `frontend/src/liff.ts`, `frontend/src/components/TransactionRow.tsx`, `frontend/src/routes/Transactions.tsx`
- Create: `frontend/src/components/EditSheet.tsx`
- Test: `frontend/src/test/edit.test.tsx` (new), `frontend/src/test/api.test.ts`, `frontend/src/test/screens.test.tsx`

**Interfaces:**
- Consumes: Task 2 routes and JSON shapes.
- Produces:
  - `api.ts`: `TransactionItem.id: number`; `ErrorCode` adds `"NOT_FOUND" | "INVALID_FIELD"`; `ApiError` gains optional `readonly field?: string`; `interface Categories { expense: string[]; income: string[] }`; `interface EditBody { transaction_type: "income" | "expense"; amount_baht: string; category: string; description: string | null; occurred_on: string }`; `sendMe(method: "PATCH" | "DELETE", path: string, token: string, body?: EditBody): Promise<TransactionItem | null>` (JSON body, Bearer header, `credentials: "omit"`, 204 → `null`, errors like `getMe`).
  - `liff.ts`: `closeWindow(): void` (calls `liff.closeWindow()` only when initialized).
  - `EditSheet({ id, fromChat, onClose, onChanged }: { id: number; fromChat: boolean; onClose: () => void; onChanged: () => void })`.
  - `TransactionRow` gains optional `onSelect?: () => void`; when set the row content is a full-width `<button>` with `min-h-11`.
  - `transactionKey(item)` → `String(item.id)`.
- Behaviour (spec §2.2–2.3): loads `/api/me/transactions/{id}` and `/api/me/categories` with `useMe`; `role="dialog"` `aria-modal`, Esc and backdrop close; type switch swaps options and keeps the row's original category offered for its original type; save disabled while sending; success shows toast ~800 ms then `fromChat ? closeWindow() : (onChanged(), onClose())`; delete arms for 3000 ms; 404 → `รายการนี้ถูกลบไปแล้ว` + `ปิด`; 422 → `ตรวจช่องนี้อีกครั้ง` under `field`; other errors → `InlineError` keeping inputs; 401 → `requireAuth()`.
- `Transactions.tsx`: read `edit` once with `useSearchParams`; accept only `/^[0-9]{1,9}$/`; clear the param when the sheet closes; row tap opens the sheet with `fromChat=false`; `onChanged` calls `retry()` to reload the month.
- Polish the sheet with the `impeccable` (or `frontend-design`) skill during Step 3, using existing tokens (`bg-card`, `text-muted`, `bg-brand`, `text-expense`).

- [ ] **Step 1: Write failing tests**:
  - `api.test.ts`: `sendMe` sends method/body/Bearer, returns `null` on 204, throws `ApiError` with `field` on 422.
  - `edit.test.tsx`: renders fields from a mocked item; switching to รายรับ shows income categories; legacy category offered; save posts the exact `EditBody` and (fromChat) calls `closeWindow`; delete needs two taps — one tap + `vi.advanceTimersByTime(3000)` sends nothing; 404 shows `รายการนี้ถูกลบไปแล้ว`; 422 `amount_baht` shows `ตรวจช่องนี้อีกครั้ง` beside amount.
  - `screens.test.tsx`: `?edit=12` opens the sheet for 12; `?edit=abc` does not; tapping a row opens it.
- [ ] **Step 2: Run** `npm test --prefix frontend` — Expected: FAIL.
- [ ] **Step 3: Implement** the units above.
- [ ] **Step 4: Run** `npm test --prefix frontend` and `npm run build --prefix frontend` — Expected: tests pass, typecheck + build succeed.
- [ ] **Step 5: Commit** `feat: edit sheet in the Mini App`.

### Task 4: Docs and full verification

**Files:**
- Modify: `AGENTS.md` (Mini App paragraph: write routes, `webapp_edit.py`, session rule), `plan/active/phase2b_edit_form_spec.md` (status → implemented)

- [ ] **Step 1: Update docs** — one short paragraph; keep "read-only" wording accurate (reads read-only, PATCH/DELETE write via `session_scope`).
- [ ] **Step 2: Run** `pytest -q` and `npm test --prefix frontend` — Expected: all pass.
- [ ] **Step 3: Commit** `docs: document the Mini App edit form`.
- [ ] **Step 4: Whole-branch review** by a fresh reviewer (opus) against the spec and Review Focus; fix findings; push and hand the PR to the owner.
