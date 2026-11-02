# MooTun Chat Cards (Phase 2A, part A) — Design Spec

**Status:** `DRAFT — awaiting owner review` (2026-11-02)
**Repository baseline:** `main` at `18d4172`
**Reference:** `ref-video-and-rich-menu-line/lasted 2.11.69.mp4` (ป้านวล bot), analysed 2026-11-02.

**Owner decisions (2026-11-02):** part A first (chat only), part B (Mini App edit
form) later; ✕ deletes in one tap with a 10-minute "เอาคืน" button; ✏️ opens the
Mini App until part B ships; card footer shows this category's month total; Help
"ปัญหาอื่นๆ" points to the `เสนอแนะ` command; the owner will supply pig artwork.

## 1. Outcome

Replies that matter look like app cards instead of plain text, common answers are
one tap, and the user sees the "..." typing indicator while the bot works.
Everything else (parser, money handling, pending-state rules) stays as it is.

Success criteria:

- Recording, chat edit, one-tap delete and restore each reply with a Flex card;
  every card has a readable `altText` (the existing text reply).
- ✕ on a card deletes that exact transaction (not "the latest"), and the delete
  card's เอาคืน restores it within 10 minutes; a stale button never restores a
  different deletion.
- Help, the direction follow-up and both delete confirmations offer Quick Reply
  buttons.
- A LINE redelivery replays exactly the same messages (cards included).
- Loading-indicator failures never block or change the reply.

Out of scope: Mini App edit form (part B), points, share images, onboarding
carousel, budgets (2D), push messages.

## 2. User-facing behaviour

### 2.1 Transaction card (record / chat edit / restore)

Flex bubble, top to bottom:

| Block | Content |
|---|---|
| Header (background `#FBF1E6`) | Title: `จดแล้ว! ✅` / `แก้แล้ว ✏️` / `เอาคืนมาแล้ว ↩️`; subtitle `อย่าลืมเช็กว่าถูกไหมนะครับ` (record) / `ตรวจอีกทีนะครับ` (edit) / `กลับมาอยู่ในรายการแล้ว` (restore); pig image on the right when artwork is configured (§3.4), otherwise no image |
| Row 1 | Pill (`รายจ่าย` brand `#D81B72` / `รายรับ` income `#1F9E74`, white text) + `· {category}` |
| Row 2 | Date `1 พ.ย. 69` (grey, small) — `occurred_on` has no time |
| Row 3 | Item (note, or category when note is `ไม่ระบุรายการ`) left; amount right, bold: `-฿50` (brand) / `+฿20,000` (income); then ✏️ and ✕ icon buttons |
| Separator | |
| Footer | `{category}เดือนนี้ ฿{total}` and a bar whose filled width is this category's share of the month's total for the same type, with `{pct}% ของรายจ่าย/รายรับ` (Asia/Bangkok month of `occurred_on`) |

Buttons:
- ✏️ → `uri` `https://liff.line.me/{LIFF_ID}/transactions` (part B replaces it).
- ✕ → `postback` `a=del&t={transaction_id}` (no `displayText`).

Amounts use the exact decimal strings already produced by `messages.format_amount`;
the bar width may use integer satang only to size the bar. Percent is
`round_half_up(category / type_total * 100)`, `0` when the total is 0.

### 2.2 Deleted card (one-tap ✕)

Header `ลบแล้ว 🗑️`, subtitle `กดเอาคืนได้ภายใน 10 นาที`; rows 1–3 as above but
the amount uses `decoration: line-through` in grey and no ✏️/✕; footer shows the
category month total after deletion; a full-width secondary button
`เอาคืน` → `postback` `a=undo&id={action_id}`.

### 2.3 Postback replies (text)

| Situation | Reply |
|---|---|
| ✕ on a transaction that no longer exists / belongs to nobody visible | `รายการนี้ลบไปแล้วครับ` |
| เอาคืน after 10 minutes, or after another action replaced the undo window | `เลย 10 นาทีแล้ว หรือมีคำสั่งใหม่มาแทน เลยเอาคืนไม่ได้ครับ` |
| เอาคืน hits an id collision | existing `format_undo_id_collision()` |
| OCC loser | existing `PENDING_ACTION_RETRY_REPLY` (cached like today) |

### 2.4 Quick replies

| Reply | Items (action) |
|---|---|
| Help | `จดรายจ่าย`, `จดรายรับ`, `เงินออม`, `แก้หรือลบ`, `ความเป็นส่วนตัว`, `ปัญหาอื่นๆ` → `postback a=help&t={expense,income,savings,edit,privacy,other}` |
| Direction follow-up (`… เป็นรายรับหรือรายจ่ายครับ?`) | `รายจ่าย`, `รายรับ` → `message` with that text |
| `ลบล่าสุด` / `ลบข้อมูลทั้งหมด` confirmation | `ยืนยัน`, `ยกเลิก` → `message` with that text |

`message` actions reuse the existing text paths, so state rules are unchanged.
Help topic replies are plain text (copy in `messages.py`, owner-reviewable):

- expense: `💸 จดรายจ่าย` / `พิมพ์ชื่อของกับราคาได้เลย เช่น "ข้าว 50" หรือ "BTS 47" หมูตุ๋นจะเดาหมวดให้เอง`
- income: `💰 จดรายรับ` / `พิมพ์ที่มากับจำนวนเงิน เช่น "เงินเดือน 20000" หรือ "แม่ให้ 500"`
- savings: `🎯 เงินออม` / `ตั้งเป้า: "ตั้งเป้า 1500 ซื้อหนังสือ"` · `เก็บเพิ่ม: "ออม 100"` · `ดูความคืบหน้า: "เป้าหมายการออม"`
- edit: `✏️ แก้หรือลบ` / `กด ✕ บนการ์ดเพื่อลบ (เอาคืนได้ใน 10 นาที) หรือพิมพ์ "แก้ไข ข้าว 60" เพื่อแก้รายการล่าสุด`
- privacy: `🔒 ความเป็นส่วนตัว` / `หมูตุ๋นเก็บแค่รายการที่คุณจด แยกตามบัญชี LINE ไม่เก็บชื่อหรือเบอร์โทร ลบทั้งหมดได้ทุกเมื่อด้วย "ลบข้อมูลทั้งหมด"`
- other: `🙋 ปัญหาอื่นๆ` / `บอกหมูตุ๋นได้เลย พิมพ์ "เสนอแนะ" ตามด้วยคะแนน 1-5 และเรื่องที่เจอ เช่น "เสนอแนะ 3 สรุปไม่ขึ้น"`

### 2.5 Loading indicator

For every accepted `message`/`postback` event, before handling it, call
`POST /v2/bot/chat/loading/start` with `{"chatId": userId, "loadingSeconds": 5}`.
It runs concurrently with handling, has a 2-second timeout, and any error is
logged at warning level and ignored. Not called for `follow` or redelivered
events that replay a cached reply.

## 3. Architecture

### 3.1 New and changed units

| Unit | Change |
|---|---|
| `replies.py` (new) | `@dataclass(frozen=True) class Reply: text: str; flex: dict | None = None; quick_reply: tuple[dict, ...] = ()` and `to_messages() -> list[dict]` producing at most 2 LINE messages: the Flex message (`altText` = `text` truncated to 400 chars) or a text message, with `quickReply` attached to the last message. `as_reply(value: str | Reply) -> Reply`. |
| `flex.py` (new, pure) | `transaction_card(kind, tx, month_total, image_url) -> dict`, `deleted_card(tx, month_total, action_id, image_url) -> dict`, quick-reply builders `help_quick_reply()`, `direction_quick_reply()`, `confirm_quick_reply()`. Only builds JSON; no DB, no env. |
| `postback.py` (new, pure) | `parse_postback(data: str) -> PostbackCommand | None`. Accepts exactly: `a=del&t=<1-9 digit int>`, `a=undo&id=<32 hex>`, `a=help&t=<topic>`; anything else (including the rich menu's `richmenu=…`) → `None`. |
| `messages.py` | Help topic copy; postback reply texts in §2.3. |
| `line_api.py` | `reply_messages(reply_token, messages, token, *, client=None)` validates 1–5 messages and posts them; `reply_text` becomes a thin wrapper. `start_loading(user_id, token, *, client=None, seconds=5)`. Errors keep the existing exception classes; the token never appears in errors. |
| `repository.py` | `delete_transaction_with_undo(line_user_id, transaction_id, *, now, session) -> DeleteWithUndoResult` (§3.3); `category_month_total(line_user_id, transaction_type, category, year, month, *, session) -> tuple[int, int]` returning (category satang, type total satang); `get_transaction(line_user_id, transaction_id, *, session)`. |
| `app.py` | Accepts `postback` events from users; `handle_postback(user, command, event_time, session) -> Reply`; selected branches of `handle_text_message` return `Reply` (record, chat edit, help, direction prompt, both delete prompts, text-confirmed delete (deleted card, §2.2), restore via `เลิกทำ`); webhook normalises with `as_reply`, caches, replies with `reply_messages`, fires `start_loading`. |
| `models.py` / `database.py` | `processed_webhook_events.response_messages TEXT NULL` (JSON list), added through the hand-rolled migration path. |
| `webapp_routes.py` | `GET /media/{name}` serving an allowlisted set of PNGs from `media/` with long cache headers (same pattern as `/app/assets`). |

### 3.2 Webhook flow (changes only)

1. Event filter adds `type == "postback"` with `postback.data` a string ≤ 300 chars.
2. New event: claim id → handle (`handle_text_message` or `handle_postback`) →
   `reply = as_reply(result)` → `set_webhook_response(id, reply.text,
   messages_json=json.dumps(reply.to_messages()))` → commit → `reply_messages`.
3. Redelivery of an unsent event: replay `response_messages` when present,
   otherwise build a text message from `response_text` (rows written before
   this change).
4. A postback that parses to `None` is claimed and recorded with no reply
   (`response_text` empty), so it is never processed twice.

Signature verification, dedupe, per-event session scope and the 502-on-reply-
failure behaviour are unchanged.

### 3.3 One-tap delete and undo

`delete_transaction_with_undo` runs in the caller's transaction:

1. Load the transaction by `(id, line_user_id)`. Missing → `NOT_FOUND`, no writes.
2. Read the user's current pending action (any type, may be expired).
3. If one exists: conditionally delete it by `(line_user_id, action_id, version)`;
   0 rows → `PendingActionConflictError`.
4. Insert a new `undo_delete` action with the transaction snapshot (same columns
   `confirm_delete_transaction` writes), fresh `action_id`, version 1,
   `expires_at = now + UNDO_DELETE_TTL`, inside a nested savepoint; an
   `IntegrityError` (concurrent create) → `PendingActionConflictError`.
5. Delete the transaction; return `DELETED` with the snapshot and `action_id`.

Replacing an existing action matches today's rule that a newer destructive
command supersedes older pending state (e.g. delete-all overrides an active undo).
The pending *transaction draft* (`pending_transactions`) is not touched.

`a=undo&id=X` → read the current action; restore only if it is `undo_delete`,
unexpired and `action_id == X`, via the existing `restore_deleted_transaction`
with its version. Otherwise reply with the expiry text (§2.3). The restored
transaction gets the restore card (§2.1).

### 3.4 Images

Artwork files live in `media/` (committed, PNG, ≤ 1024 px, ≤ 300 KB each) with
names `pig-<pose>.<8 hex>.png` for poses `record`, `edit`, `delete`, `restore`
(restore may reuse `record`). `PUBLIC_BASE_URL` (new env var, e.g.
`https://mootoon-line-bot.onrender.com`) builds absolute HTTPS URLs; when it is
unset or a pose file is missing, cards render without the image. `.env.example`
gets an empty placeholder.

## 4. Invariants and limits

- Money: satang integers and Decimal strings only; no float in amounts shown.
- Every DB read/write is scoped by the event's `source.userId`; postback ids from
  another user resolve to `NOT_FOUND`.
- Flex bubble JSON ≤ 30 KB (asserted ≤ 10 KB in tests); `altText` ≤ 400 chars;
  ≤ 13 quick reply items, labels ≤ 20 chars; postback `data` ≤ 300 chars;
  ≤ 5 messages per reply.
- Pending-state rules from AGENTS.md hold: OCC losers get the cached retry reply;
  stateless commands do not touch versions.

## 5. Tests

- `test_flex.py`: card structure for expense/income/record/edit/restore/delete,
  amounts and dates exact, image present only when configured, ✕/เอาคืน data
  formats, size and limit checks, quick-reply builders.
- `test_postback.py`: accepted/rejected data strings (fuzzed-ish table, rich menu
  data ignored, overlong, wrong id format).
- `test_replies.py`: `to_messages` shapes, altText truncation, quick reply on the
  last message, `as_reply`.
- `test_repository.py` additions: one-tap delete with no / confirm_delete /
  confirm_delete_all / undo_delete pending action, other user's id, missing id,
  concurrent conflict, undo by matching and stale action_id, category month total
  across Bangkok month boundary.
- `test_webhook.py` additions: postback delete→undo end to end, unknown postback
  claimed without reply, redelivery replays cached Flex, legacy rows replay text,
  loading call made and its failure ignored, follow does not call loading.
- `test_line_api.py` additions (or existing file): `reply_messages` validation,
  `start_loading` payload and token redaction.
- Full suite stays green.

## 6. Rollout

1. Merge; Render redeploys (migration adds the column on startup).
2. Owner sets `PUBLIC_BASE_URL` in Render; artwork lands in a follow-up commit
   when supplied (cards work without it).
3. Phone check: record, ✕, เอาคืน (inside and after 10 min), Help topics,
   direction quick reply, delete confirmations, "..." indicator.
