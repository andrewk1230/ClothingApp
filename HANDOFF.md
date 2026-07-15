# GrailSeeker — Session Handoff (2026-07-15)

State of the project after the security-hardening session and the PRD audit
(which followed the end-to-end implementation session). Read alongside
[PRD.md](../PRD.md) (product spec) and [README.md](README.md) (setup).

**Start here:** the "Next session — prioritized work plan" section below is
the marching order. Everything in it is self-contained code/writing work that
needs no credentials or hardware.

## Where things stand

**Phases 0–6 are code-complete and verified.** The full product works end to end
in code: upload → on-device compression (1024px JPEG) → `/segment` with tappable
SVG bounding boxes → tap a box / "Search entire image" / manual crop → `/find` →
results grid with confidence labels → listing detail with eBay stale-check →
"View on eBay". Auth (Supabase Google/Apple OAuth), rate limiting (5 guest / 50
user per day), saved items, search history, price filters, dark-mode override,
onboarding, and offline handling are all implemented per the PRD.

**The P0/P1 security hardening is now implemented too** (see the security
section below for what changed and what remains dashboard-side).

**Verification evidence (all re-runnable):**
- Backend: `cd backend && .venv/bin/python -m pytest -q` → **76 passed**
  (61 from the implementation session + 15 security tests in
  `tests/test_security.py`); `ruff check app tests scraper` clean.
- Mobile: `cd mobile && npx tsc --noEmit` clean; `npx expo export --platform ios` bundles.
- Live boot: uvicorn with real CLIP + YOLO weights starts warning-free on the Mac (CPU);
  real image POSTed through `/segment` and `/find` returns correct shapes and
  `X-RateLimit-*` headers.
- Two independent review agents audited backend and mobile against the PRD; 13
  confirmed bugs were fixed (event-loop-blocking torch inference, offline screen
  under native modals, quota burn on rejected uploads, non-eBay cleanup
  deactivation, stale-response races, and more).

## Decisions made (do not relitigate without cause)

1. **DeepFashion2 category gap → Option A.** The detector only finds 4 garment
   classes (top/outerwear/bottom/dress). Accessories are reached via the
   always-visible "Search entire image" action (bbox-less `/find` embeds the
   whole image) and the logged-in manual crop tool. PRD §4.2's 10-category table
   describes what is *searchable*, not what is auto-boxed.
2. **`/find` is unmetered** — PRD §4.5 defines 1 upload = 1 search, metered at
   `/segment`. (See security note below before publishing.)
3. **CLIP model is `ViT-B-32-quickgelu`** (config default + `.env`). Plain
   `ViT-B-32` with OpenAI weights silently degrades embeddings. Changed while the
   DB had 0 rows. **Never change the model after seeding without re-embedding
   everything** — stored vectors and query vectors must come from the same model.
4. **Price filter UI** is min/max inputs + presets (not a slider); settings live
   inside the Profile tab. Both are deliberate interpretations of the PRD.

## Key contracts (mobile ↔ backend)

- Bbox coordinates are pixels in the space returned by `/segment`
  (`image_width`/`image_height`). The mobile app compresses the photo **once**
  and sends the same file to both `/segment` and `/find`; scaling happens only
  for display. Backend resize (1024px cap) is deterministic, so spaces match.
- `confidence_label` values: `"match"` (>0.7, no badge) and `"similar"`
  (0.4–0.7, "Similar match" badge). Below 0.4 is excluded server-side.
- `/listings/{id}/check` returns `{"id", "active"}`. Stale check is best-effort:
  eBay failures assume active.
- 429 from `/segment` carries a user-facing `detail` string; the app shows it
  verbatim with no retry. `GET /api/v1/rate-limit` = `{limit, used, remaining}`.
- Saved: `GET/POST/DELETE /api/v1/saved[/{listing_id}]` (idempotent POST).
  History: `GET /api/v1/history`, `DELETE /api/v1/history/{id}` (ownership
  enforced). All auth'd routes 401 on missing/invalid Bearer token; invalid
  tokens are never treated as guests.

## Remaining launch checklist (needs physical resources, not code)

1. eBay production credentials in `.env` → run `scripts/seed_db.py` for the
   ~50k-listing initial ingest (on the Windows GPU PC).
2. Windows PC bring-up: Docker Postgres, backend under ROCm, Cloudflare Tunnel
   (`scripts/tunnel.sh`), set `EXPO_PUBLIC_API_BASE_URL` to the tunnel URL.
3. Supabase dashboard: enable Google + Apple providers, allow the
   `grailseeker://` redirect URL from `makeRedirectUri()`.
4. EAS builds (`mobile/eas.json` is ready): TestFlight (needs Apple dev account)
   + internal APK.
5. PRD §9 evaluation: 200–500 hand-labeled images; demo video.
6. ~~Init git repo~~ **Done** — repo exists with `origin`
   (github.com/andrewk1230/ClothingApp); local commits are NOT pushed
   (push when ready to publish). `.gitignore` covers `.env` and weights.
7. **Set `ENVIRONMENT=production` and a strong `POSTGRES_PASSWORD` in the
   serving PC's `.env` before first `docker compose up`** (postgres only
   applies the password when initializing an empty data volume; mirror it in
   `DATABASE_URL`).

## Security hardening — IMPLEMENTED 2026-07-14 (code side)

All P0/P1 code items are done, tested (`tests/test_security.py`), and
config-driven (`app/config.py`, documented in `.env.example`):

- **Docs off in prod:** `ENVIRONMENT=production` disables `/docs`, `/redoc`,
  `/openapi.json` (`create_app()` factory in `app/main.py`).
- **Proxy-header trust:** in production only `CF-Connecting-IP` keys guest
  rate limits (Cloudflare overwrites it; `X-Forwarded-For` is spoofable and
  honored only in development).
- **Postgres:** compose now binds `127.0.0.1:5432` and takes
  `POSTGRES_PASSWORD` from env (dev default unchanged). The Mac's running
  `grailseeker-db` container predates this — it still has the old binding
  until recreated; the Windows bring-up gets it from the start.
- **`/find` abuse cap:** `FIND_DAILY_LIMIT=200`/day per caller (separate
  `find:`-prefixed bucket in `rate_limits`; does NOT touch the user-visible
  quota — `/find` stays unmetered per PRD §4.5). 429 with generic detail.
- **`/check` throttle:** stored `is_active` served while `last_checked_at` is
  within `LISTING_CHECK_TTL_MINUTES=15`; live checks stamp the field.
- **uvicorn loopback:** `api_host` default + `.env` now `127.0.0.1` (tunnel
  connects locally; `fastapi dev` already defaulted to loopback).
- **Decompression-bomb guard:** pixel count checked after header parse,
  before full decode (`MAX_IMAGE_PIXELS=40000000` → 413, no quota burn).
- **Generic 500 handler:** JSON `{"detail": "Internal server error"}`,
  traceback only in server logs.
- **rate_limits retention:** nightly cleanup purges rows older than
  `RATE_LIMIT_RETENTION_DAYS=7`.

**Still open (not code):** Cloudflare edge rate-limit/bot rules (dashboard,
during tunnel bring-up). P2 if open-sourcing: rotate Supabase JWT + eBay
secrets if ever in doubt; SECURITY.md; `pip-audit`/`npm audit`/Dependabot;
document JWKS (not the HS256 legacy secret) as the example auth config.

## PRD audit (2026-07-15) — full compliance check

Every buildable requirement in PRD §4–§8 and §10–§13 was audited against the
code and is implemented, with these findings:

**Documented deviations (deliberate, see "Decisions made"):** 4-of-10
auto-detected categories (Option A); price inputs+presets instead of a slider;
ended listings soft-deleted (`is_active=False`, excluded from search) instead
of removed from the DB; `/find` unmetered with an abuse cap.

**Known code gaps (the only ones):**
1. **History tap-through** — `search_history` stores `bbox`, `category`, and
   `result_ids`, but the Profile screen's history rows only support delete;
   there is no way to re-open a past search's results. Biggest-value remaining
   feature work.
2. **Result "streaming" (§4.3)** — skeleton cards exist but all fill at once;
   the backend returns all 20 results in one response. Cosmetic; low priority.

**PRD self-contradiction, resolved:** §5.2 says the manual crop tool is
"always-visible" but §4.2 and the §12 matrix say logged-in only. Implementation
follows §4.2/§12 (logged-in only).

## Next session — prioritized work plan (no physical resources needed)

**0. FIRST: launch a parallel App Store readiness agent.** Before starting the
feature work below, spawn a background agent (general-purpose) to audit
everything Apple requires to publish, then fold its findings back into this
plan. The agent must:

- **Audit submission readiness** against current App Store Review Guidelines
  (research them — do not rely on training data): `mobile/app.json` +
  `mobile/eas.json` completeness (bundle IDs, icons, splash, version/build
  numbers), iOS permission usage strings (camera, photo library), privacy
  manifest / privacy nutrition labels, required support + privacy-policy URLs,
  age rating, export compliance (uses HTTPS only).
- **Check account-based app rules specifically:** Apple requires in-app
  account deletion for apps with account creation (guideline 5.1.1(v)) — we
  have Supabase accounts and NO delete-account flow; Sign in with Apple is
  already planned (required when offering Google sign-in, 4.8). Also: guest
  mode must not gate core functionality behind login (it doesn't).
- **Flag content/legal items:** app displays eBay listing images/prices
  (aggregator disclosure, no misrepresentation of affiliation), LICENSE says
  MIT, need an in-app privacy policy link and terms.
- **Define every missing component** it finds as a concrete work item (file,
  screen, endpoint, or store-listing asset), ranked blocking vs. nice-to-have.

While the agent runs, do the feature work below; when it reports, integrate
the blocking items (e.g. account deletion needs a backend endpoint that
deletes Supabase user + saved/history rows, plus a Profile screen action),
then **debug everything end-to-end**: full `pytest` + `ruff` + `tsc` +
`expo export`, live-boot the API and exercise the real flow, and fix whatever
surfaces. Nothing ships to the store this session — the goal is that when
Apple credentials arrive, submission is a mechanical step.

1. **History tap-through** (closes PRD gap #1): backend endpoint to fetch
   listings for a history entry's stored `result_ids` (preserve stored order;
   handle since-deactivated listings), make Profile history rows navigate to a
   results view, tests for ownership/401/order. Mind the Expo SDK 56 gotchas
   below.
2. **Windows bring-up runbook**: RUNBOOK.md + PowerShell scripts for the GPU
   PC — Docker Postgres (strong `POSTGRES_PASSWORD` + `ENVIRONMENT=production`
   BEFORE first `compose up`), ROCm backend install (`scripts/validate_rocm.py`
   exists), running the API as a service, `scripts/tunnel.sh`, smoke tests.
3. **§9 evaluation harness**: labeling template matching the PRD two-level
   taxonomy, a runner that feeds labeled images through `/segment`+`/find`,
   and a metrics report. Humans then only label the 200–500 images.
4. **eBay sandbox dry-run**: sandbox creds are in `.env`; run a small
   `seed_db.py` ingest on the Mac to shake out Browse-API surprises before the
   50k production ingest. (Note: `.env` currently points `EBAY_API_URL`/
   `EBAY_AUTH_URL` at production hosts — switch to sandbox hosts for this.)
5. **Open-sourcing hygiene (P2)**: SECURITY.md; run `pip-audit` + `npm audit`
   and fix; Dependabot config; document JWKS (not HS256) as the example auth
   setup.
6. **Result streaming** (optional, PRD gap #2) — only if the demo needs it.

**Do NOT attempt (needs the user):** pushing to GitHub (ask first — remote
holds stale partial state that the push will supersede), eBay production
credentials, Supabase dashboard, Apple/TestFlight, physical Windows setup,
demo video.

## Gotchas for the next session

- Expo SDK 56 changed APIs (`mobile/AGENTS.md`): `useFocusEffect` comes from
  `expo-router`, `ImageManipulator.manipulate()` replaces `manipulateAsync`,
  FlashList v2 has no `estimatedItemSize`. Verify against
  https://docs.expo.dev/versions/v56.0.0/ before writing Expo code.
- All theming goes through `hooks/useTheme.tsx` (ThemeProvider); do not use
  `useColorScheme` + `getColors` directly in screens — the in-app appearance
  override won't apply.
- `GestureHandlerRootView` is scoped to the segmentation screen; if more
  gesture screens are added, move it to `app/_layout.tsx`.
- Tests run against a `grailseeker_test` DB in the `grailseeker-db` docker
  container and mock all ML — no GPU/torch weights needed for CI.
- Guests *can* pass price filters directly to `/find` (UI gates it, server
  doesn't) — codified in tests as allowed; revisit only as a product decision.
