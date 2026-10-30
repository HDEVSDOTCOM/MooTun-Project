# MooTun Mini App — React Rebuild (Phase 2C)

**Status:** `APPROVED FOR BUILD` (owner, 2026-10-30) — steps 1–3 implemented; deploy option 1 (Render builds) chosen
**Repository baseline:** `main` at `888d572` (LINE Mini App read-only foundation)
**Stack decision (owner, 2026-10-30):** Vite + React + TypeScript

## 1. Product Outcome

Replace the single-page vanilla Mini App with a tabbed app that feels like the
reference recording (pink rounded cards, bottom tab bar, skeleton loading, charts),
while keeping every security property of the read-only foundation.

This phase is still **read-only**. Recording, editing and deleting stay in chat.
Budgets, custom categories, the onboarding wizard and any web write path are a
later phase (2D) because they need new tables and a write-safety design.

### Screens in scope

| Tab | Route | Content | Data |
|---|---|---|---|
| สรุป | `/app/summary` | Month picker, income / expense / net cards, top categories with bars, 5 recent items, link to รายการ | existing `/api/me/summary`, `/api/me/transactions/recent` + new category breakdown |
| วิเคราะห์ | `/app/analysis` | Last 6 months income vs expense bar chart, expense-by-category donut for selected month | new `/api/me/analytics/monthly`, `/api/me/analytics/categories` |
| รายการ | `/app/transactions` | Full month list grouped by day, filter ทั้งหมด / รายจ่าย / รายรับ, month picker | new `/api/me/transactions?month=YYYY-MM&type=` |
| การออม | `/app/savings` | Goal card, progress ring, remaining, deadline | existing `/api/me/savings` |
| ตั้งค่า | `/app/settings` | Help, privacy text (moved from current page), chat command cheat sheet, links that open chat with prefilled text (`ส่งออกข้อมูล`, `ลบข้อมูลทั้งหมด`) | static |

The reference's หมวด/งบ tab is deliberately absent until budgets exist; no empty tab ships.

## 2. Frontend

### Layout

```
frontend/                 Vite project (source, not served)
  src/
    main.tsx, App.tsx     router + LIFF bootstrap
    liff.ts               init, getIDToken, login recovery (port of current app.js logic)
    api.ts                typed fetch wrapper, Bearer header, AbortController, error codes
    money.ts              format decimal strings; never parseFloat for display values
    routes/               Summary, Analysis, Transactions, Savings, Settings
    components/           TabBar, Card, Skeleton, MonthPicker, EmptyState, ErrorState
  index.html
  vite.config.ts          base: "/app/", build.outDir: "../webapp/dist"
webapp/dist/              build output served by FastAPI
```

### Libraries (pinned exact versions at implementation time)

- `react`, `react-dom`, `react-router-dom` (browser router with `basename="/app"`)
- `@line/liff` from npm instead of the CDN tag (same 2.x line as today)
- `tailwindcss` for styling; design tokens for the pink palette on `:root`
- `chart.js` + `react-chartjs-2` (canvas, so no inline style attributes; CSP-friendly)
- `@fontsource/prompt` (headings) and `@fontsource/ibm-plex-sans-thai` (body), self-hosted
- Dev: `vitest`, `@testing-library/react`, `typescript`, `eslint`

No state-management library, no data-fetching library: five screens with
per-screen fetches do not need them. Revisit only if 2D adds forms.

### Behaviour carried over from the foundation (must not regress)

- Fetch `/app/config.json`, `liff.init` with the Developing LIFF ID, `withLoginOnExternalBrowser: false`.
- Every financial request sends `Authorization: Bearer <ID token>`, `credentials: "omit"`, `cache: "no-store"`.
- Summary request is the identity bootstrap; other reads start after it succeeds.
- 401 → explicit "เข้าสู่ระบบ LINE" button (logout then login to `/app/`), never an automatic login loop.
- `pagehide` / hidden visibility aborts in-flight requests and clears rendered financial data; `pageshow` / visible reloads.
- No token or financial data in `localStorage` / `sessionStorage` / IndexedDB.
- All user text rendered as text nodes (React default; `dangerouslySetInnerHTML` banned by lint rule).

### Money in charts

APIs keep returning exact decimal strings for display. Analytics endpoints also
return integer `*_satang` fields. Charts may convert satang to `Number` **only to
size bars/slices**; every visible label and tooltip uses the decimal string.

## 3. Backend changes

### New read endpoints (same `verified_owner` + `ReadSession` dependencies)

| Endpoint | Query | Returns |
|---|---|---|
| `GET /api/me/transactions` | `month=YYYY-MM` (required), `type=income\|expense` (optional) | items for that Bangkok month, newest first, hard cap 500 |
| `GET /api/me/analytics/monthly` | `months=6` (fixed allowlist: 3, 6, 12) | per-month income/expense strings + satang |
| `GET /api/me/analytics/categories` | `month=YYYY-MM`, `type=expense\|income` | per-category totals + share percent |

`verified_owner` currently rejects **any** query string. Change: each route declares
an explicit allowlist of parameter names and validated formats; unknown names,
duplicates, or malformed values → 400 `INVALID_REQUEST` before a session opens.
Existing endpoints keep rejecting all queries.

New repository functions go in `repository.py`, scoped by owner, using the existing
Bangkok month-boundary helpers. No new tables in this phase.

### Serving the SPA

- `/app/` and the five tab paths (exact allowlist) return `webapp/dist/index.html`.
  Any other `/app/*` path stays 404 (existing traversal tests keep passing).
- `/app/assets/*` serves `webapp/dist/assets` (Vite hashed filenames). Hashed assets
  may get `Cache-Control: public, max-age=31536000, immutable`; HTML and `/api/me/*`
  stay `no-store`.
- LIFF endpoint URL stays `/app/`; rich menu deep links use
  `https://liff.line.me/<liffId>/summary` etc., which LIFF maps to `/app/summary`.

### CSP update

Current policy plus: `font-src 'self'`, `img-src 'self' data:`.
`script-src` stays `'self' https://static.line-scdn.net` (LIFF bridge extensions).
Verify the Vite build emits no inline script (it does not by default; the module
preload polyfill is disabled via `build.modulePreload.polyfill = false`).

## 4. Build and deploy

Open decision for the owner (pick one before build):

1. **Render builds the frontend (recommended).** `buildCommand: pip install -r requirements.txt && cd frontend && npm ci && npm run build`.
   Needs confirming that the Render Python native runtime ships Node; if not, pin Node
   via `NODE_VERSION` env var. `webapp/dist/` is gitignored.
2. **Commit `webapp/dist/`.** Render stays Python-only, but every frontend change
   produces a noisy build diff and the dist can drift from source.

Local dev: `npm run dev` in `frontend/` with a Vite proxy for `/api` and `/app/config.json`
to `uvicorn` on :8000. LIFF login inside a desktop browser needs the LIFF endpoint
pointed at an HTTPS tunnel; document this in README.

## 5. Tests

- **pytest (backend):** new endpoint tests mirroring `test_webapp.py` style: two-user
  isolation, month boundaries in Bangkok, query allowlist rejections, read-only SQL,
  cap of 500, exact decimal strings. Update the static-shell tests to read
  `webapp/dist/index.html` and resolve asset paths from the built HTML instead of the
  hard-coded `app.js` / `styles.css`. Replace
  `test_frontend_source_authentication_rendering_and_lifecycle_contract` with an
  equivalent check over `frontend/src/liff.ts` and `api.ts`.
- **Vitest (frontend):** money formatting, B.E. dates, API error-code mapping,
  401 → login button, abort on `pagehide`, empty / error / skeleton states per screen.
- Manual: open in LINE (Developing) on iOS and Android, each tab, rotate, slow 3G.

## 6. Out of scope (later phases)

- 2A Flex Message replies, quick replies, postback handling in the webhook.
- 2B Rich menu image (2500×1686), area mapping, alias page 2, deploy script.
- 2D Budgets, custom categories, onboarding wizard, any Mini App write endpoint.
- Points/streaks, daily reminders (push quota), Pro tier.

## 7. Delivery order

1. Backend: query allowlist mechanism + three read endpoints + tests.
2. Scaffold `frontend/`, port LIFF/auth lifecycle, TabBar, Summary tab; SPA serving + CSP; update static tests.
3. Transactions tab, Savings tab, Settings tab.
4. Analysis tab with charts.
5. Render build change, README/AGENTS.md update (commands, layout), manual LINE test.
