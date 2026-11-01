# MooTun Rich Menu (Phase 2B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Owner decision: executed natively in the lead session, no subagents.

**Goal:** Ship a two-page LINE rich menu (owner art + code-composed page 2) deployed by a manual GitHub Actions workflow.

**Architecture:** `richmenu_config.py` holds pure data (geometry, actions) and builds LINE rich menu objects. `richmenu/build_images.py` (dev-only, Pillow) produces the two committed JPEGs. `richmenu_deploy.py` validates images and drives the Messaging API with `httpx`; a `workflow_dispatch` workflow runs it with a secret token. No webhook, parser, DB or Mini App change.

**Tech Stack:** Python 3.12+, httpx 0.28.1, pytest 8.4.2, Pillow (dev-only, not in requirements), GitHub Actions.

**Spec:** `plan/active/phase2b_rich_menu_spec.md`

## Global Constraints

- Canvas 2500 × 1686; each image ≤ 1 MB (use 1_000_000 bytes), JPEG.
- Aliases `mootoon-page1`, `mootoon-page2`; menu names equal the aliases; `chatBarText` "เมนู"; `selected: true`.
- `LIFF_ID = "2011960945-14GtwIlx"`; URIs `https://liff.line.me/{LIFF_ID}/{tab}` with tab in `webapp_routes.SPA_TABS`.
- Token only from env `LINE_CHANNEL_ACCESS_TOKEN`; never printed.
- Only menus whose name starts with `mootoon-` may be deleted.
- Labels contain no stacked Thai marks (no `ั/ิ/ี/ึ/ื/็` followed by a tone mark).
- Flat repo layout: modules and `test_*.py` at root; assets in `richmenu/`.

## Review Focus

1. Token unset on a real run → exit 1 with a clear message before any request (dry run works without a token).
2. LINE answers with a non-JSON body (HTML 502) → error names endpoint + status, no crash, no token.
3. Alias list contains other aliases → only `mootoon-page1/2` are created/updated.
4. Orphan `mootoon-` menus left by an earlier crashed run → deleted on the next successful run; foreign-named menus kept.
5. A PNG saved as `.jpg` → content type comes from the file signature, not the extension.

Each has a named test in Task 3.

---

## Geometry (decided here, used by Tasks 1–2)

Derived from `richmenu_parts/manifest.json` × 2500/1527, gaps split at midpoints,
areas tile the canvas. `(x, y, width, height)`:

| Area | Bounds | Tile drawn at (x0, y0, x1, y1) in 2500 space (Task 2) |
|---|---|---|
| BIG | (0, 0, 1375, 1067) | (34, 43, 1362, 1058) |
| WIDE | (0, 1067, 1375, 619) | (34, 1079, 1364, 1501) |
| R1A | (1375, 0, 563, 539) | (1387, 41, 1925, 526) |
| R1B | (1938, 0, 562, 539) | (1952, 41, 2474, 526) |
| R2A | (1375, 539, 563, 520) | (1387, 552, 1925, 1048) |
| R2B | (1938, 539, 562, 520) | (1952, 552, 2474, 1048) |
| R3A | (1375, 1059, 563, 627) | (1387, 1072, 1925, 1501) |
| R3B | (1938, 1059, 562, 627) | (1952, 1072, 2474, 1501) |

---

### Task 1: Rich menu config

**Files:**
- Create: `richmenu_config.py`
- Test: `test_richmenu.py`

**Interfaces:**
- Produces:
  - `CANVAS: tuple[int, int] = (2500, 1686)`
  - `LIFF_ID: str`, `ALIASES: dict[str, str]` (`{"page1": "mootoon-page1", "page2": "mootoon-page2"}`), `NAME_PREFIX = "mootoon-"`
  - `AREAS: dict[str, tuple[int, int, int, int]]` (keys BIG, WIDE, R1A, R1B, R2A, R2B, R3A, R3B)
  - `PAGES: dict[str, dict[str, dict]]` page → area → LINE action dict (each action includes a `label`)
  - `IMAGE_PATHS: dict[str, Path]` → `richmenu/page1.jpg`, `richmenu/page2.jpg` (relative to the module file)
  - `build_richmenu(page: str) -> dict` returns `{"size": {"width","height"}, "selected": True, "name", "chatBarText", "areas": [{"bounds": {...}, "action": {...}}]}` in AREAS order

- [ ] **Step 1: Write failing tests** in `test_richmenu.py`:
  - `test_areas_tile_canvas_without_overlap` — every area inside CANVAS; pairwise no overlap; sum of areas == 2500 × 1686.
  - `test_pages_share_geometry_and_limit` — both pages have exactly the AREAS keys; `len(areas) <= 20`.
  - `test_message_buttons_parse_to_commands` — expected kinds, page1: R1A MONTHLY_SUMMARY, R2B RECENT, R3B HELP; page2: BIG SAVINGS_STATUS, R2A DELETE_LATEST, R2B EXPORT, R3B HELP (via `parser.parse_command(text).kind`).
  - `test_keyboard_buttons_prefill_valid_commands` — page2 R1A `fillInText + "5000 ทริป"` → SET_SAVINGS_GOAL; R1B `+ "100"` → ADD_SAVINGS; R3A `+ "5 ดีมาก"` → FEEDBACK; page1 BIG is postback `openKeyboard` with no `fillInText`.
  - `test_uri_buttons_target_our_liff_tabs` — every `uri` action matches `https://liff.line.me/{LIFF_ID}/{tab}` with tab in `webapp_routes.SPA_TABS`; page1 R1B and R2A → analysis, R3A → settings.
  - `test_switch_buttons_target_defined_aliases` — page1 WIDE → `ALIASES["page2"]`, page2 WIDE → `ALIASES["page1"]`.
  - `test_line_limits` — `chatBarText` ≤ 14 chars; aliases match `^[a-z0-9_-]{1,32}$`; postback/switch `data` ≤ 300; every label ≤ 20 chars and has no stacked Thai marks (regex `[\u0e31\u0e34-\u0e37\u0e47][\u0e48-\u0e4b]`).
  - `test_build_richmenu_shape` — `build_richmenu("page1")["name"] == "mootoon-page1"`, `selected is True`, `size == {"width": 2500, "height": 1686}`, first area bounds `{"x": 0, "y": 0, "width": 1375, "height": 1067}`; unknown page raises `KeyError`.
- [ ] **Step 2:** Run `pytest test_richmenu.py -q` → FAIL (module missing).
- [ ] **Step 3:** Implement `richmenu_config.py` with the geometry table above and the action tables from spec §3 (postback data values `richmenu=compose|goal|save|feedback|page1|page2`).
- [ ] **Step 4:** Run `pytest test_richmenu.py -q` → all pass; `pytest -q` → full suite passes.
- [ ] **Step 5:** Commit `feat: add rich menu config (Phase 2B)`.

### Task 2: Rich menu images

**Files:**
- Create: `richmenu/build_images.py`, `richmenu/page1.jpg`, `richmenu/page2.jpg`

**Interfaces:**
- Consumes: nothing from Task 1 at runtime (geometry above is copied as tile rectangles).
- Produces: the two JPEGs at `IMAGE_PATHS`.

- [ ] **Step 1: Implement** `python richmenu/build_images.py <owner-art.png>`:
  - page1: owner art resized to 2500 × 1686 with `Image.LANCZOS`.
  - page2: start from page1; over each tile rectangle paint a rounded rectangle (radius 70, fill `#fdf0f4`; WIDE uses `#fbe3a0`, sampled from the owner "เพิ่มเติม" tile if it differs); BIG gets the pig cropped from owner art box (240, 300, 640, 645) scaled ×1.637 and pasted bottom-right, label "เป้าหมาย" / "การออม" two lines top-left; grid tiles get an emoji (Segoe UI Emoji `C:/Windows/Fonts/seguiemj.ttf`, `embedded_color=True`, size 160) above a centred label: R1A 🎯 สร้างเป้า, R1B 💰 ออม, R2A 🗑 ลบล่าสุด, R2B 📤 ส่งออกข้อมูล, R3A 💬 เสนอแนะ, R3B 📖 วิธีใช้; WIDE label "‹ กลับหน้าแรก". Labels: Prompt 700 from `frontend/node_modules/@fontsource/prompt/files/prompt-thai-700-normal.woff2`, colour `#9a1650`, size 100 (BIG 150).
  - Save both as RGB JPEG starting at quality 92, stepping down by 4 until ≤ 1_000_000 bytes; fail if quality < 60.
- [ ] **Step 2:** Run it against `ref-video-and-rich-menu-line/richmenu.png`; expect two files printed with size and quality.
- [ ] **Step 3: Visual check** — open both JPEGs; every label legible, no clipped/stacked marks, emoji in colour, tiles aligned with Task 1 areas (draw-check: overlay area borders on a scratch copy and look).
- [ ] **Step 4:** Commit `feat: add rich menu images and generator`.

### Task 3: Deploy script

**Files:**
- Create: `richmenu_deploy.py`
- Test: `test_richmenu.py` (append)

**Interfaces:**
- Consumes: `build_richmenu`, `ALIASES`, `NAME_PREFIX`, `IMAGE_PATHS` from Task 1; JPEGs from Task 2.
- Produces:
  - `class DeployError(Exception)`
  - `MAX_IMAGE_BYTES = 1_000_000`
  - `image_info(data: bytes) -> tuple[str, int, int]` → (`"image/jpeg"|"image/png"`, width, height) from PNG IHDR or JPEG SOFn marker; `DeployError` otherwise.
  - `load_images(paths: dict[str, Path] = IMAGE_PATHS) -> dict[str, tuple[bytes, str]]` — checks existence, signature, 2500 × 1686, ≤ MAX_IMAGE_BYTES.
  - `deploy(client: httpx.Client, images: dict[str, tuple[bytes, str]]) -> dict[str, str]` — spec §5 steps 2–5, returns page → new rich menu ID; on failure in steps 2–3 deletes the menus it created, then raises `DeployError`.
  - `main(argv: list[str] | None = None) -> int` — `--dry-run` prints `json.dumps({page: build_richmenu(page)}, ensure_ascii=False, indent=2)` after `load_images()` and returns 0 with no client; otherwise requires the token, builds `httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=30)` and prints the IDs. `DeployError` → message to stderr, return 1.

- [ ] **Step 1: Write failing tests** using `httpx.MockTransport` with an in-memory fake LINE (dict of menus, dict of aliases, request log):
  - `test_image_info_reads_jpeg_and_png` (Pillow-free fixtures: tiny hand-built PNG header and the committed JPEG) and `test_image_info_rejects_other_bytes`.
  - `test_committed_images_are_valid` — `load_images()` returns both pages with `image/jpeg`.
  - `test_load_images_rejects_wrong_size_and_oversize` (tmp_path files).
  - `test_png_named_jpg_uses_signature_type` (Review Focus 5).
  - `test_first_deploy_creates_aliases_and_default` — order: validate ×2/create/upload per page, alias create ×2, default set to page1 ID; returned IDs match.
  - `test_redeploy_updates_aliases_and_deletes_old_mootoon_menus` — pre-existing `mootoon-page1`, an orphan `mootoon-page2`, and `other-menu`; after run only `other-menu` + the two new menus remain (Review Focus 4); aliases updated not created.
  - `test_foreign_aliases_untouched` (Review Focus 3).
  - `test_failure_cleans_up_created_menus` — upload of page2 returns 400 `{"message": "bad image"}`: raises DeployError containing `400` and `bad image`; menus created in this run deleted; pre-existing menus and aliases unchanged; default not changed.
  - `test_non_json_error_body` — 502 HTML body → DeployError with endpoint and `502` (Review Focus 2).
  - `test_main_requires_token` — env without token, real run → returns 1, stderr mentions `LINE_CHANNEL_ACCESS_TOKEN`, transport never called (Review Focus 1); `test_main_dry_run_needs_no_token` → returns 0, stdout contains `mootoon-page2`.
  - `test_token_never_in_output` — failing run with token `secret-token-xyz`: not in the exception text or captured stdout/stderr.
- [ ] **Step 2:** Run `pytest test_richmenu.py -q` → new tests FAIL.
- [ ] **Step 3:** Implement `richmenu_deploy.py`. Endpoints: `https://api.line.me/v2/bot/richmenu/validate`, `/v2/bot/richmenu`, `https://api-data.line.me/v2/bot/richmenu/{id}/content`, `/v2/bot/richmenu/alias/list`, `/v2/bot/richmenu/alias`, `/v2/bot/richmenu/alias/{aliasId}`, `/v2/bot/user/all/richmenu/{id}`, `/v2/bot/richmenu/list`, `DELETE /v2/bot/richmenu/{id}`. Error text: `f"{method} {path} -> {status}: {message}"` where message is the JSON `message` field or the first 200 chars of the body.
- [ ] **Step 4:** `pytest -q` → full suite passes; `python richmenu_deploy.py --dry-run` prints both menus.
- [ ] **Step 5:** Commit `feat: add rich menu deploy script`.

### Task 4: Workflow and docs

**Files:**
- Create: `.github/workflows/richmenu-deploy.yml`
- Modify: `README.md`, `AGENTS.md`, `plan/active/phase2b_rich_menu_spec.md` (status line)

- [ ] **Step 1:** Workflow: `on: workflow_dispatch` with input `dry_run` (boolean, default true); `permissions: contents: read`; ubuntu-latest; `actions/checkout@v4`, `actions/setup-python@v5` (3.12), `pip install -r requirements.txt`, then `python richmenu_deploy.py ${{ inputs.dry_run && '--dry-run' || '' }}` with `env: LINE_CHANNEL_ACCESS_TOKEN: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}`.
- [ ] **Step 2:** Docs: AGENTS.md Commands gets `python richmenu_deploy.py --dry-run` and `python richmenu/build_images.py <art.png>`; Architecture gets one paragraph (config / images / deploy, separate from Render, labels avoid stacked Thai marks). README gets a "Rich menu" section with the secret + workflow steps. Spec status → `APPROVED — implemented`.
- [ ] **Step 3:** `pytest -q` passes; YAML parses (`python -c "import yaml"` not available → validate by pushing and `gh workflow view`).
- [ ] **Step 4:** Commit `ci: add rich menu deploy workflow and docs`; push branch; open PR.
- [ ] **Step 5 (after merge, owner adds secret):** run workflow `dry_run: true`, then `false`; owner checks every tap on a phone.
