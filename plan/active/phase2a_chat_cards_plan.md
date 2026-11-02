# MooTun Chat Cards (Phase 2A part A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Owner decision: executed in the lead session; a `worker` only for the mechanical test-helper migration in Task 6.

**Goal:** Flex cards for record/edit/delete/restore, one-tap delete with undo, Quick Replies, and the loading indicator.

**Architecture:** Pure builders (`replies.py`, `postback.py`, `flex.py`, `media.py`) produce LINE JSON; `repository.py` gains one-tap delete and a category month total; `app.py` returns `Reply` from selected branches, accepts postbacks, caches the exact message list, and fires the loading call. Existing text formatters stay as `altText`/fallback.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2, httpx 0.28.1, pytest.

**Spec:** `plan/active/phase2a_chat_cards_spec.md`

## Global Constraints

- Money: satang ints + `messages.format_amount` strings; no float in shown amounts.
- All DB access scoped by the event's `source.userId`.
- Flex bubble JSON ≤ 10 KB in tests; `altText` ≤ 400 chars; ≤ 13 quick reply items, labels ≤ 20 chars; postback `data` ≤ 300; ≤ 5 messages per reply.
- Brand `#D81B72`, income `#1F9E74`, header `#FBF1E6`, muted `#8A6F7B`.
- Postback data formats exactly: `a=del&t=<1-9 digits>`, `a=undo&id=<32 lowercase hex>`, `a=help&t=<expense|income|savings|edit|privacy|other>`.
- Loading: `POST https://api.line.me/v2/bot/chat/loading/start` `{"chatId": userId, "loadingSeconds": 5}`, timeout 2 s, failures logged and ignored.
- Images only via `_export_base_url()` + `/media/<file>`; no new env vars. ✏️ uses `MINIAPP_DEVELOPING_LIFF_ID`, omitted if unset.
- Flat layout; tests at repo root.

## Review Focus

1. Rich menu postbacks (`richmenu=compose`, `richmenu=page2`) → claimed, no reply, no error.
2. Double-tap ✕ (two events, same id) → second reply `รายการนี้ลบไปแล้วครับ`, no exception.
3. ✕ while a pending transaction draft exists → draft row unchanged.
4. 500-char note / 100-char category → card ≤ 10 KB, `altText` ≤ 400.
5. Redelivery of a row written before this change (no `response_messages`) → replays text.

Each has a named test in the owning task.

---

### Task 1: Reply and postback primitives

**Files:** Create `replies.py`, `postback.py`; Test `test_replies.py`, `test_postback.py`

**Interfaces — Produces:**
- `replies.Reply(text: str, flex: dict | None = None, quick_reply: tuple[dict, ...] = ())` (frozen) with `to_messages() -> list[dict]` and `replies.as_reply(value: str | Reply) -> Reply`. Text message `{"type":"text","text":text}`; Flex message `{"type":"flex","altText":alt,"contents":flex}` where `alt` = text truncated to 400 (`…` at 400); if `quick_reply`, the last message gets `"quickReply":{"items":list(quick_reply)}`.
- `postback.DeleteTx(transaction_id: int)`, `postback.Undo(action_id: str)`, `postback.HelpTopic(topic: str)` (frozen dataclasses); `HELP_TOPICS = ("expense","income","savings","edit","privacy","other")`; `parse_postback(data: object) -> DeleteTx | Undo | HelpTopic | None`.

- [ ] **Step 1: Tests** — `test_to_messages_text_only`, `test_to_messages_flex_uses_truncated_alt_text` (text of 450 chars → alt length 400, ends with `…`), `test_quick_reply_attached_to_last_message`, `test_as_reply_wraps_str_and_passes_reply`; `test_parse_postback_accepts` (table: `a=del&t=42`→`DeleteTx(42)`, `a=undo&id=`+32 hex → `Undo`, each topic → `HelpTopic`), `test_parse_postback_rejects` (table: `richmenu=compose`, `richmenu=page2`, `a=del&t=0`, `a=del&t=1234567890`, `a=del&t=-1`, `a=del&t=4&t=5`, `a=del`, `a=undo&id=XYZ`, `a=undo&id=`+31 hex, `a=help&t=admin`, `a=del&t=4&x=1`, `""`, 301-char string, `None`, bytes).
- [ ] **Step 2:** `pytest test_replies.py test_postback.py -q` → FAIL (modules missing).
- [ ] **Step 3:** Implement. `parse_postback` uses `urllib.parse.parse_qs(data, keep_blank_values=True, strict_parsing=True)` inside `try/except ValueError`, requires the exact key set per action and single values.
- [ ] **Step 4:** Same command → PASS.
- [ ] **Step 5:** Commit `feat: add reply and postback primitives`.

### Task 2: Flex builders, media lookup and copy

**Files:** Create `flex.py`, `media.py`, `media/.gitkeep`; Modify `messages.py`; Test `test_flex.py`

**Interfaces:**
- Consumes: `messages.format_amount`, `messages.format_buddhist_date`.
- Produces:
  - `flex.MonthTotal(category_satang: int, type_total_satang: int)` (frozen) with `percent -> int` (round half up, 0 when total 0).
  - `flex.transaction_card(variant: str, tx: Mapping[str, object], total: MonthTotal, *, liff_id: str | None, image_url: str | None) -> dict` — `variant` ∈ `record|edit|restore`; `tx` keys `id, type, amount (Decimal|str), category, note, date (date)`.
  - `flex.deleted_card(tx: Mapping[str, object], total: MonthTotal, *, action_id: str, image_url: str | None) -> dict`.
  - `flex.help_quick_reply() -> tuple[dict, ...]`, `flex.direction_quick_reply()`, `flex.confirm_quick_reply()`.
  - `media.POSES = ("record","edit","delete","restore")`, `media.MEDIA_DIR: Path`, `media.MEDIA_NAME: re.Pattern` (`pig-(record|edit|delete|restore)\.[0-9a-f]{8}\.png`), `media.media_url(pose: str, base_url: str | None) -> str | None` (first sorted match in `MEDIA_DIR`; `restore` falls back to `record`).
  - `messages.HELP_TOPIC_TEXT: dict[str, str]` (copy from spec §2.4, title line + blank line + body), `messages.format_already_deleted() -> "รายการนี้ลบไปแล้วครับ"`, `messages.format_undo_button_expired() -> "เลย 10 นาทีแล้ว หรือมีคำสั่งใหม่มาแทน เลยเอาคืนไม่ได้ครับ"`.

- [ ] **Step 1: Tests** in `test_flex.py`:
  - `test_record_card_expense` — header title `จดแล้ว! ✅`, pill text `รายจ่าย` with background `#D81B72`, amount text `-฿50`, date `1 พ.ย. 69`, footer `อาหารเดือนนี้ ฿1,250` and `40% ของรายจ่าย` for `MonthTotal(125000, 312500)`; ✕ action `{"type":"postback","data":"a=del&t=7"}`; ✏️ action uri `https://liff.line.me/LIFF/transactions`.
  - `test_income_card_is_green_and_signed_plus` (`+฿20,000`, `#1F9E74`, `ของรายรับ`).
  - `test_edit_and_restore_titles` (`แก้แล้ว ✏️`, `เอาคืนมาแล้ว ↩️`).
  - `test_note_fallback_uses_category` (note `ไม่ระบุรายการ` → item text equals category).
  - `test_no_liff_id_omits_edit_button`, `test_image_only_when_url_given`.
  - `test_deleted_card` — title `ลบแล้ว 🗑️`, amount has `"decoration":"line-through"`, no `a=del` anywhere, button action data `a=undo&id=<id>`.
  - `test_month_total_percent` (0 total → 0; 1/3 → 33; 1/8 → 13).
  - `test_long_text_card_limits` (Review Focus 4: note 500 chars, category 100 chars → `len(json.dumps(card, ensure_ascii=False).encode()) <= 10_240`).
  - `test_quick_replies` — help: 6 items, postback data `a=help&t=<topic>` in `HELP_TOPICS` order, labels ≤ 20; direction: messages `รายจ่าย`,`รายรับ`; confirm: `ยืนยัน`,`ยกเลิก`.
  - `test_media_url` (tmp dir with `pig-record.0123abcd.png`; `media_url("record", "https://x")` → `https://x/media/pig-record.0123abcd.png`; `restore` falls back; missing pose or `base_url=None` → `None`; monkeypatch `media.MEDIA_DIR`).
  - `test_help_topic_examples_parse` — every `"..."` inside `HELP_TOPIC_TEXT` values parses to a non-Unresolved, non-Incomplete command (reuse the approach in `test_copy.py`).
- [ ] **Step 2:** `pytest test_flex.py -q` → FAIL.
- [ ] **Step 3:** Implement. Bubble `size: "kilo"`; header box `backgroundColor #FBF1E6`, horizontal [vertical(title bold lg, subtitle xs muted), image 72px when given]; body rows per spec §2.1; icon buttons are small boxes with `action` and emoji text `✏️`/`✕`; bar = outer box (`#F1E3E9`, height 8px, cornerRadius 4px) containing inner box `width: f"{max(percent, 2)}%"` brand/income colour (omit inner box when percent is 0); wrap long text (`wrap: true`, `maxLines: 2`).
- [ ] **Step 4:** `pytest test_flex.py test_copy.py -q` → PASS.
- [ ] **Step 5:** Commit `feat: add flex card builders and media lookup`.

### Task 3: LINE API multi-message reply and loading

**Files:** Modify `line_api.py`; Test `test_line_api.py` (create)

**Interfaces — Produces:**
- `async reply_messages(reply_token: str, messages: list[dict], channel_access_token: str, *, client: httpx.AsyncClient | None = None, timeout: float = 10.0) -> None` — validates token/reply token as today, `1 <= len(messages) <= 5`, each a dict with `type`; posts `{"replyToken":..., "messages": messages}`.
- `reply_text(...)` unchanged signature, delegates to `reply_messages` with one text message after its existing validation.
- `async start_loading(user_id: str, channel_access_token: str, *, seconds: int = 5, client: httpx.AsyncClient | None = None, timeout: float = 2.0) -> None` — posts to the loading endpoint; non-2xx or transport error raises the existing `LineAPIError` subclasses.

- [ ] **Step 1: Tests** with `httpx.MockTransport`: `test_reply_messages_posts_payload`, `test_reply_messages_rejects_empty_and_six`, `test_reply_text_still_sends_single_text`, `test_start_loading_payload` (URL path `/v2/bot/chat/loading/start`, body `{"chatId":"U1","loadingSeconds":5}`), `test_start_loading_error_has_no_token` (500 → raises, `str(exc)` lacks the token).
- [ ] **Step 2:** `pytest test_line_api.py -q` → FAIL.
- [ ] **Step 3:** Implement, sharing the existing request/error-mapping code path.
- [ ] **Step 4:** `pytest test_line_api.py test_webhook.py -q` → PASS (existing webhook tests still use `reply_text`).
- [ ] **Step 5:** Commit `feat: add multi-message reply and loading indicator API`.

### Task 4: Repository and schema

**Files:** Modify `models.py`, `database.py`, `repository.py`; Test `test_repository.py`

**Interfaces — Produces:**
- `ProcessedWebhookEvent.response_messages: Mapped[str | None]` (`Text`, nullable); migration in `_upgrade_webhook_event_table` (`ALTER TABLE processed_webhook_events ADD COLUMN response_messages TEXT`).
- `set_webhook_response(webhook_event_id, response_text, *, messages_json: str | None = None, session=None)` stores both.
- `get_transaction(line_user_id: str, transaction_id: int, *, session=None) -> Transaction | None`.
- `category_month_total(line_user_id: str, transaction_type: str, category: str, year: int, month: int, *, session=None) -> tuple[int, int]` — (category satang, type total satang) for that Bangkok month (reuse `_month_bounds`).
- `class DeleteOutcome(str, Enum): DELETED = "deleted"; NOT_FOUND = "not_found"`; `@dataclass(frozen=True) class DeleteWithUndoResult: outcome: DeleteOutcome; transaction: Transaction | None; action_id: str | None`.
- `delete_transaction_with_undo(line_user_id: str, transaction_id: int, *, now: datetime | None = None, session=None) -> DeleteWithUndoResult` per spec §3.3; raises `PendingActionConflictError`.

- [ ] **Step 1: Tests:** `test_init_db_adds_response_messages_column` (old-schema SQLite table without the column → `init_db` adds it), `test_set_webhook_response_stores_messages_json`, `test_get_transaction_is_user_scoped`, `test_category_month_total_bangkok_bounds` (rows on Bangkok 31 Oct 23:30 vs 1 Nov 00:10 land in different months; other category/type/user excluded), `test_delete_with_undo_no_pending_action` (tx gone; action `undo_delete`, snapshot fields equal tx, expires +10 min), `test_delete_with_undo_replaces_confirm_delete_all`, `test_delete_with_undo_replaces_existing_undo`, `test_delete_with_undo_other_user_not_found` (no writes), `test_delete_with_undo_missing_not_found`, `test_delete_with_undo_keeps_pending_draft` (Review Focus 3), `test_delete_with_undo_conflict` (monkeypatch to bump action version between read and delete → `PendingActionConflictError`, tx still present), `test_restore_after_one_tap_delete` (existing `restore_deleted_transaction` with returned `action_id` restores the exact row).
- [ ] **Step 2:** `pytest test_repository.py -q` → new tests FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `pytest -q` → all pass.
- [ ] **Step 5:** Commit `feat: add one-tap delete with undo and category month totals`.

### Task 5: Media route

**Files:** Modify `webapp_routes.py`; Test `test_webapp.py`

**Interfaces:** Consumes `media.MEDIA_DIR`, `media.MEDIA_NAME`. Produces `GET /media/{name}` → `image/png` with `Cache-Control: public, max-age=31536000, immutable`; anything not matching `MEDIA_NAME` or missing → 404 `NOT_FOUND`. Not gated by `WEBAPP_ENABLED` (LINE fetches images for chat cards).

- [ ] **Step 1: Tests:** `test_media_serves_allowlisted_png`, `test_media_rejects_other_names` (table: `../app.py`, `pig-record.png`, `pig-other.0123abcd.png`, `pig-record.0123ABCD.png`, `x.svg`).
- [ ] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** `pytest test_webapp.py -q` PASS.
- [ ] **Step 5:** Commit `feat: serve card artwork from /media`.

### Task 6: Wire it into the bot

**Files:** Modify `app.py`; Create `line_fakes.py` (test helper); Modify webhook-driving tests (`test_webhook.py`, `test_onboarding.py`, `test_export.py`, `test_feedback.py`, `test_app.py`); Test additions in `test_webhook.py`

**Interfaces:**
- Consumes everything above.
- Produces:
  - `handle_text_message(...) -> str | Reply`. `Reply` branches: transaction recorded (record card + `format_transaction_confirmation` text), chat edit (edit card), restore via `เลิกทำ` (restore card), text-confirmed delete (deleted card with the new undo action id read back via `get_pending_action`), help (`format_help_message` + `help_quick_reply`), direction prompt (when `amount` is known: `direction_quick_reply`), both delete confirmation prompts (`confirm_quick_reply`).
  - `handle_postback(line_user_id: str, command: DeleteTx | Undo | HelpTopic, event_time: datetime, session: Session) -> str | Reply`.
  - `_card_context(line_user_id, tx, session) -> tuple[dict, MonthTotal]` builds `tx` mapping and month total (Bangkok month of `occurred_on`).
  - Webhook: accepts `postback`; `parse_postback(None result)` → claim only; stores `messages_json`; replays `response_messages` (or text for legacy rows); `_send(reply_token, messages)` calls `reply_text` when there is exactly one text message without `quickReply`, else `reply_messages`; loading: `await start_loading(...)` before handling, inside `try/except LineAPIError` (2 s timeout; sequential because handling is synchronous DB work on the same loop).
  - `line_fakes.LineRecorder` with `.reply_text(token, text, access_token)` and `.reply_messages(token, messages, access_token)` appending `(token, text_or_alt)` to `.replies` and full message lists to `.messages`; `.install(monkeypatch, app_module)` patches both plus `start_loading` (records calls).

- [ ] **Step 1 (worker, mechanical):** replace each test file's local `fake_reply` capture with `LineRecorder` so replies sent through either function land in the same `replies` list as `(token, text)` where text is the message text or Flex `altText`. No assertion changes beyond that; suite green on the current `app.py`.
- [ ] **Step 2: New tests** in `test_webhook.py`: `test_record_reply_is_flex_with_alt_text`, `test_postback_delete_then_undo_end_to_end` (record → postback `a=del&t=<id>` → deleted card with `a=undo&id=` → postback undo → restore card; DB row back with same id), `test_double_delete_postback_second_reports_already_deleted` (Review Focus 2), `test_stale_undo_button_does_not_restore_other_deletion`, `test_other_users_transaction_id_is_not_found`, `test_rich_menu_postback_claimed_without_reply` (Review Focus 1), `test_help_topic_postback_replies_topic_text`, `test_help_has_quick_reply`, `test_direction_prompt_has_quick_reply`, `test_delete_prompts_have_confirm_quick_reply`, `test_redelivery_replays_cached_flex`, `test_legacy_row_without_messages_replays_text` (Review Focus 5), `test_loading_called_for_message_and_postback_not_follow`, `test_loading_failure_does_not_block_reply`.
- [ ] **Step 3:** `pytest test_webhook.py -q` → new tests FAIL.
- [ ] **Step 4:** Implement in `app.py`.
- [ ] **Step 5:** `pytest -q` → all pass; `npm test --prefix frontend` untouched.
- [ ] **Step 6:** Commit `feat: chat cards, one-tap delete, quick replies and loading`.

### Task 7: Docs, review, PR

**Files:** Modify `AGENTS.md`, `README.md`, `plan/active/phase2a_chat_cards_spec.md` (status)

- [ ] **Step 1:** AGENTS.md Architecture: `replies.py`/`flex.py`/`postback.py`/`media.py` roles, postback allowlist, `response_messages` cache, card images in `media/`. README: card artwork drop-in instructions (file names, size). Spec status → `APPROVED — implemented`.
- [ ] **Step 2:** Fresh reviewer (most capable model) on `origin/main..HEAD` with spec, plan and Review Focus; fix Critical/Important with RED→GREEN tests.
- [ ] **Step 3:** `pytest -q` green; push; open PR.
