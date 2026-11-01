# MooTun Rich Menu (Phase 2B) — Design Spec

**Status:** `DRAFT — awaiting owner review` (2026-11-01)
**Repository baseline:** `main` at `9d96246`
**Decisions (owner, 2026-11-01):** 2B before 2A; mixed destinations (chat for
summary/recent, Mini App for analysis/categories/settings); "เพิ่มเติม" switches to a
second page; page 2 art is composed in code from existing assets; deploy via a
manually-run GitHub Actions workflow.

## 1. Outcome

Every chat with the bot shows a two-page rich menu that matches the reference look
(`ref-video-and-rich-menu-line/richmenu.png`, owner-supplied MooTun art). Common
actions become one tap; nothing about recording, parsing or the webhook changes.

Success criteria:

- Page 1 opens by default for every user (default rich menu, `selected: true`).
- Every tap does what the tables below say, for any user. Mini App taps work for
  admins/testers while the Mini App stays in Developing.
- Re-running the deploy replaces both pages with no moment where users see no menu.
- A future change to a chat command that a button relies on fails pytest.

## 2. Scope

In: two rich menu images, area/action definitions, a deploy script, a manual GitHub
Actions workflow, tests, docs.

Out (later phases): Flex replies, quick replies and any postback *handling* (2A);
budgets (2D); per-user rich menus; publishing the Mini App.

The webhook is not modified. It already ignores `postback` events
(`app.py:801`, asserted in `test_onboarding.py`), so the keyboard-opening postbacks
and rich-menu-switch postbacks below produce no reply and no DB write.

## 3. Menu pages

Canvas: 2500 × 1686 px (LINE large size). Both pages share one area geometry,
derived from the tile bounds in `richmenu_parts/manifest.json` scaled by
2500 / 1527 and widened so the areas tile the whole canvas (gaps and the footer
belong to the nearest tile, so near-miss taps still land):

```
+---------------------------+-------------+-------------+
|                           |   R1 (A)    |   R1 (B)    |
|          BIG              +-------------+-------------+
|                           |   R2 (A)    |   R2 (B)    |
+---------------------------+-------------+-------------+
|          WIDE             |   R3 (A)    |   R3 (B)    |
+---------------------------+-------------+-------------+
```

### Page 1 — alias `mootoon-page1`, image = owner art upscaled

| Area | Label | Action |
|---|---|---|
| BIG | จดรายรับรายจ่าย | `postback`, data `richmenu=compose`, `inputOption: openKeyboard` |
| WIDE | เพิ่มเติม › | `richmenuswitch` → `mootoon-page2`, data `richmenu=page2` |
| R1A | สรุป | `message` "สรุปเดือนนี้" |
| R1B | วิเคราะห์ | `uri` `https://liff.line.me/<LIFF_ID>/analysis` |
| R2A | หมวด/งบ | `uri` `https://liff.line.me/<LIFF_ID>/analysis` (category donut lives there) |
| R2B | รายการ | `message` "รายการล่าสุด" |
| R3A | ตั้งค่า | `uri` `https://liff.line.me/<LIFF_ID>/settings` |
| R3B | Help | `message` "ช่วยเหลือ" |

### Page 2 — alias `mootoon-page2`, image composed in code

| Area | Label | Action |
|---|---|---|
| BIG | เป้าหมายการออม | `message` "เป้าหมาย" |
| WIDE | ‹ กลับหน้าแรก | `richmenuswitch` → `mootoon-page1`, data `richmenu=page1` |
| R1A | สร้างเป้า | `postback` data `richmenu=goal`, `openKeyboard`, `fillInText` "ตั้งเป้า " |
| R1B | ออม | `postback` data `richmenu=save`, `openKeyboard`, `fillInText` "ออม " |
| R2A | ลบล่าสุด | `message` "ลบล่าสุด" (existing confirm step still applies) |
| R2B | ส่งออกข้อมูล | `message` "ส่งออกข้อมูล" |
| R3A | เสนอแนะ | `postback` data `richmenu=feedback`, `openKeyboard`, `fillInText` "เสนอแนะ " |
| R3B | วิธีใช้ | `message` "ช่วยเหลือ" |

"ลบข้อมูลทั้งหมด" is deliberately not on the menu (too easy to mis-tap); it stays a
typed command. Labels avoid stacked Thai marks (e.g. "ตั้ง") because Pillow here has
no raqm shaping and drops the upper mark; "สร้างเป้า" is used instead.

Both menus: `chatBarText` "เมนู", `selected: true`, names `mootoon-page1` /
`mootoon-page2`. `LIFF_ID` is the Developing Mini App ID `2011960945-14GtwIlx`
(already public via `/app/config.json`), held as a constant.

## 4. Files

All flat at repo root except the asset folder, matching the existing layout.

| File | Purpose |
|---|---|
| `richmenu_config.py` | Pure data: canvas size, area rectangles, the two page definitions, alias IDs, LIFF ID; `build_richmenu(page) -> dict` returns the LINE rich menu object. No I/O. |
| `richmenu_deploy.py` | CLI. `python richmenu_deploy.py [--dry-run]`. Reads `LINE_CHANNEL_ACCESS_TOKEN` from the environment; uses `httpx` (already a dependency). |
| `richmenu/page1.jpg`, `richmenu/page2.jpg` | Final images, committed, each ≤ 1 MB, 2500 × 1686. |
| `richmenu/build_images.py` | Dev-only generator (Pillow, not added to `requirements.txt`). Upscales the owner art for page 1 (Lanczos) and composes page 2: pink background and footer reused from the owner art, rounded pale tiles, pig mascot cropped from the page 1 big tile, Segoe UI Emoji icons, labels in Prompt 700 loaded from `frontend/node_modules/@fontsource/prompt`. Writes JPEGs, lowering quality until each is ≤ 1 MB. |
| `.github/workflows/richmenu-deploy.yml` | `workflow_dispatch` with a `dry_run` boolean input; installs `requirements.txt`; runs the script with secret `LINE_CHANNEL_ACCESS_TOKEN`. |
| `test_richmenu.py` | Tests (section 7). |

The owner art source stays outside the repo; `build_images.py` takes its path as an
argument. Only the generated JPEGs are committed.

## 5. Deploy flow (`richmenu_deploy.py`)

Order chosen so the default menu is never missing:

1. Validate locally: image exists, JPEG/PNG signature, dimensions 2500 × 1686 (read
   from the file header, no Pillow), size ≤ 1 MB. Abort before any API call on failure.
2. For each page: `POST /v2/bot/richmenu/validate`, then `POST /v2/bot/richmenu`
   → new ID, then `POST api-data.line.me/v2/bot/richmenu/{id}/content` with the image.
3. List aliases (`GET /v2/bot/richmenu/alias/list`). For each alias: update
   (`POST /v2/bot/richmenu/alias/{aliasId}`) if it exists, otherwise create
   (`POST /v2/bot/richmenu/alias`).
4. `POST /v2/bot/user/all/richmenu/{page1Id}` (set default).
5. `GET /v2/bot/richmenu/list`; delete (`DELETE /v2/bot/richmenu/{id}`) every menu
   whose name starts with `mootoon-` and is not one of the two just created. Menus
   made in LINE OA Manager are not returned by this API and are never touched.
6. Print the two new IDs.

Failure handling: any non-2xx stops the run with the endpoint, status and LINE's
error message (never the token). If steps 2–3 fail, newly created menus are deleted
before exit so retries do not pile up orphans; the previous menus and aliases remain
live. `--dry-run` performs step 1 and prints both rich menu JSON objects, no network.

## 6. Security and invariants

- Token only from the environment / GitHub secret; never logged, never in the repo.
- URI actions are restricted to `https://liff.line.me/<LIFF_ID>/` + a tab in the
  Mini App's `SPA_TABS` (asserted in tests).
- Message actions only send existing commands; no new command words are introduced.
- No DB, webhook, parser, or Mini App change.

## 7. Tests (`test_richmenu.py`, pytest, no network)

- Geometry: every area lies inside 2500 × 1686, areas do not overlap, and together
  they cover the canvas; ≤ 20 areas per page; both pages use the same geometry.
- Command contract: each `message` action text, run through `parser.parse_command`,
  yields the expected kind (MONTHLY_SUMMARY, RECENT, HELP, SAVINGS_STATUS,
  DELETE_LATEST, EXPORT). Each `fillInText` prefix plus a sample value parses as the
  intended command (`ตั้งเป้า 5000 ทริป` → SET_SAVINGS_GOAL, `ออม 100` →
  ADD_SAVINGS, `เสนอแนะ 5 ดีมาก` → FEEDBACK). All nine were verified against the
  current parser while writing this spec.
- URIs: LIFF host + ID + a tab in `webapp_routes.SPA_TABS`.
- LINE limits: `chatBarText` ≤ 14 chars, alias IDs match `[a-z0-9_-]{1,32}`,
  postback `data` ≤ 300 chars, labels ≤ 20 chars, `richmenuswitch` targets an alias
  that is defined.
- Image checks: committed JPEGs are 2500 × 1686 and ≤ 1 MB; the header parser rejects
  wrong sizes and non-image bytes.
- Deploy sequence with `httpx.MockTransport`: fresh account (aliases created), second
  run (aliases updated, old `mootoon-` menus deleted, foreign menus kept), failure
  mid-way (new menus cleaned up, nothing else deleted, token absent from output),
  `--dry-run` makes no requests.
- Existing `test_onboarding.py` postback-ignored assertion keeps passing.

## 8. Rollout

1. Owner adds GitHub secret `LINE_CHANNEL_ACCESS_TOKEN` (same value as in Render).
2. Merge; run the workflow with `dry_run: true`, then `false`.
3. Check on a phone: menu appears, each tap behaves per section 3, page switch works
   both ways.
4. Rollback: re-run after reverting, or delete the menus from the API; the bot works
   without a rich menu.

## 9. Docs

README and AGENTS.md: new files, the deploy command and workflow, the "keep labels
free of stacked Thai marks" note, and that the menu deploy is separate from Render.
