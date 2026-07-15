# GrailSeeker — Session Handoff (2026-07-16)

State after the launch-prep session (App Store compliance + feature/infra
work). Read alongside [PRD.md](../PRD.md) (product spec), [README.md](README.md)
(setup), [RUNBOOK.md](RUNBOOK.md) (Windows bring-up), [SECURITY.md](SECURITY.md).

## Where things stand

**Phases 0–6 code-complete and verified**, plus everything from the previous
handoff's work plan is now DONE:

1. ✅ **App Store readiness** — a research agent audited against the live
   July-2026 guidelines; all code-side blocking items implemented:
   - **Account deletion (5.1.1(v))**: `DELETE /api/v1/account` removes saved
     items, history, rate-limit rows, and the Supabase auth user via the
     Admin API (`SUPABASE_SERVICE_ROLE_KEY`, server-only; endpoint 503s if
     unconfigured, 502+rollback if Supabase fails so retries work). Profile
     has a double-confirmed "Delete Account" row.
   - **app.json**: `ITSAppUsesNonExemptEncryption=false`; aggregated iOS
     `privacyManifests` (UserDefaults CA92.1, FileTimestamp C617.1/DDA9.1,
     SystemBootTime 35F9.1, DiskSpace E174.1 — verify against the first
     TestFlight upload's ITMS-91053 email); image-picker camera permission
     string added, microphone permission disabled; unused `expo-camera`
     removed; splash screen configured.
   - **Legal**: Privacy Policy / Terms / Support pages authored in `docs/`
     (for GitHub Pages), linked in-app from Profile (both signed-in AND the
     guest gate); eBay non-affiliation disclosures on listing detail +
     Profile.
2. ✅ **History tap-through** (was PRD gap #1): `GET /api/v1/history/{id}/results`
   returns listings in stored order (deleted ones skipped, ended ones
   `active=false`); Profile history rows navigate to the results screen in
   replay mode (no filter bar; ended listings dimmed + "No longer available").
3. ✅ **Windows runbook**: RUNBOOK.md + `scripts/windows/01…07-*.ps1`
   (env generation with strong password BEFORE first compose up, DB+migrate,
   ROCm install, API runner, smoke test, tunnel, Scheduled-Task autostart).
4. ✅ **§9 eval harness**: `eval/` — labels template (two-level taxonomy),
   `run_eval.py` (drives /segment+/find, auto metrics report, review.html +
   grading sheet), `score_grading.py` (precision@1/@K per category). Humans
   only need to collect+label 200–500 images and grade.
5. ✅ **eBay sandbox dry-run** — OAuth, Browse search, getItem all validated.
   **Found+fixed a real bug**: `item_summary/search` has no `categoryPath`
   (getItem-only field) so every ingested listing had `category=None`; now
   maps from the `categories` name list (excluding the root category whose
   "shoes" mis-mapped everything unmatched to footwear). `tests/test_scraper.py`
   covers it. Note: `localizedAspects` (size) is also getItem-only → size is
   usually None from ingest; the mobile UI already handles null size.
6. ✅ **Open-sourcing hygiene**: SECURITY.md; `pip-audit` clean (Pillow
   floor 12.3.0 pinned in requirements.txt; setuptools 83 vs torch's <82 pin
   — accepted, build-time only, suite passes); `npm audit` 0 vulns (override
   `xcode→uuid ^11.1.1` in mobile/package.json); `.github/dependabot.yml`;
   `.env.example` documents JWKS (empty `SUPABASE_JWT_SECRET`) as the
   recommended auth config.

**Verification (2026-07-16, all re-runnable):**
- `cd backend && .venv/bin/python -m pytest -q` → **92 passed**; `ruff check
  app tests scraper` clean.
- `cd mobile && npx tsc --noEmit` clean; `npx expo export --platform ios`
  bundles; `npx expo config --type introspect` resolves (no mic permission,
  camera+photo strings present).
- **Live e2e (18/18 PASS)**: uvicorn with real CLIP+YOLO on the Mac; real
  JPEG through guest `/segment` (2 boxes, rate headers) → auth'd `/find`
  (seeded listings, similarity 1.0) → history list (thumbnails) → history
  replay (stored order, `active` flips after deactivation, guest 401) →
  account delete 503-when-unconfigured → auth'd `/segment` metering →
  history delete. Dev DB wiped after.

## Decisions made (do not relitigate without cause)

1. **DeepFashion2 gap → Option A**: only top/outerwear/bottom/dress are
   auto-boxed; accessories via "Search entire image" + logged-in manual crop.
2. **`/find` unmetered** (PRD §4.5, metered at `/segment`) with a 200/day
   abuse cap in a separate `find:` bucket.
3. **CLIP is `ViT-B-32-quickgelu`** — never change after seeding without
   re-embedding everything.
4. Price filter = min/max + presets; settings in Profile tab.
5. Ended listings are soft-deleted (`is_active=false`), excluded from
   search, still shown (flagged) in history replay.

## Key contracts (mobile ↔ backend)

Unchanged from before, plus:
- `GET /api/v1/history/{id}/results` → `[{...listing fields, active: bool}]`
  in stored order; 404 for missing/other-user entries; 401 guests.
- `DELETE /api/v1/account` → 204 (deletes everything), 503 if service-role
  key unconfigured, 502 (nothing deleted) if Supabase call fails.
- Results screen accepts `historyId` param → replay mode (no re-search).

## Remaining launch checklist

**Needs the user / physical resources (not code):**
1. **Push to GitHub** (ask user first — remote has stale partial state).
   Then enable **GitHub Pages** for `docs/` — the in-app legal links point
   at `https://andrewk1230.github.io/ClothingApp/{privacy-policy,terms,support}`
   (constants in `mobile/constants/config.ts`; update if the URL differs).
2. eBay **production** credentials → `scripts/seed_db.py` 50k ingest on the
   Windows PC. (Mac `.env` currently points at **sandbox** hosts — that's
   deliberate for dev; production hosts are in `.env.example`.)
3. Windows PC bring-up → follow RUNBOOK.md top to bottom.
4. Supabase dashboard: enable Google+Apple providers, allow `grailseeker://`
   redirect; copy the **service_role key** into the server `.env` (account
   deletion 503s without it).
5. App Store Connect (needs Apple dev account): privacy nutrition labels
   (Photos=app functionality/linked; Email+UserID=linked; SearchHistory=
   linked; hashed-IP=not linked; tracking=NO), age rating questionnaire
   (expect 4+), support URL + privacy policy URL fields, demo account notes
   for review (mention guest mode + eBay Browse API authorization).
6. EAS builds → TestFlight + internal APK. Watch the first upload for an
   ITMS-91053 privacy-manifest email; add any flagged reason codes to
   `app.json → ios.privacyManifests`.
7. **Apple token revocation on account deletion** (Apple "should"): needs
   the Apple client-secret JWT — wire into `delete_supabase_user()` in
   `backend/app/routers/account.py` once Apple credentials exist.
8. §9 evaluation: collect+label 200–500 images (`eval/README.md`), run the
   harness, grade, report. Demo video.
9. Cloudflare dashboard during tunnel bring-up: edge rate-limit rule + Bot
   Fight Mode (last open security item).

**Optional code (nice-to-have, from the audit):**
- Native Sign in with Apple (`expo-apple-authentication` +
  `signInWithIdToken`) instead of the web-OAuth sheet — reviewers sometimes
  flag the browser flow as poor UX.
- Result streaming (§4.3) — cosmetic, only if the demo needs it.
- `eas.json` submit.production block (ascAppId) once ASC exists; bump
  version to 1.0.0 at launch.

## Gotchas for the next session

- Expo SDK 56 API changes (`mobile/AGENTS.md`): `useFocusEffect` from
  `expo-router`, `ImageManipulator.manipulate()`, FlashList v2 without
  `estimatedItemSize`. Verify at https://docs.expo.dev/versions/v56.0.0/.
- All theming through `hooks/useTheme.tsx`; never `useColorScheme`+`getColors`
  directly in screens.
- `GestureHandlerRootView` is scoped to the segmentation screen.
- Tests use the `grailseeker_test` DB in the `grailseeker-db` container and
  mock all ML. The Mac's dev `grailseeker` DB is empty (0 listings) — seed
  via sandbox if you need local results.
- Guests *can* pass price filters directly to `/find` (server allows;
  UI gates) — codified in tests; product decision if revisited.
- The Mac's running `grailseeker-db` container predates the loopback-bind +
  password hardening in docker-compose; recreate it if that matters locally.
- `mobile/package.json` has an npm `overrides` entry (`xcode → uuid ^11.1.1`)
  — don't remove it or `npm audit` regresses to 11 moderates.
