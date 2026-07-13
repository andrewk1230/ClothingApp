# GrailSeeker — Session Handoff (2026-07-14)

State of the project after the security-hardening session (which followed the
end-to-end implementation session). Read alongside [PRD.md](../PRD.md)
(product spec) and [README.md](README.md) (setup).

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
