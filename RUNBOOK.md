# GrailSeeker — Windows GPU PC Bring-up Runbook

Step-by-step guide to stand up the production backend on the Windows PC
(AMD RX 9070 XT). Every step has a PowerShell script in `scripts/windows/`;
run them **in order** from the repo root in an elevated PowerShell (Docker
and scheduled-task steps need admin).

The end state: Docker Postgres (pgvector) on loopback, the FastAPI backend
under ROCm on `127.0.0.1:8000`, exposed via a Cloudflare Tunnel, seeded with
~50k eBay listings, restarting automatically on boot.

## 0. Prerequisites (manual installs)

| What | Where | Notes |
|---|---|---|
| Windows 11 + AMD Adrenalin **26.2.2+** | amd.com/en/support | Required for ROCm 7.2.1 on RX 9070 XT |
| Python **3.12** (64-bit) | python.org | ROCm torch wheels are cp312-only. Check "Add to PATH" |
| Git | git-scm.com | |
| Docker Desktop | docker.com | Enable "Start Docker Desktop when you sign in" |
| cloudflared | developers.cloudflare.com → Tunnel downloads | `winget install Cloudflare.cloudflared` |

Then clone the repo, e.g. to `C:\grailseeker`:

```powershell
git clone <repo-or-copy> C:\grailseeker
cd C:\grailseeker
```

## 1. Create the production .env — BEFORE anything else

```powershell
.\scripts\windows\01-setup-env.ps1
```

Creates `.env` from `.env.example` with `ENVIRONMENT=production`, a
generated 32-char `POSTGRES_PASSWORD`, and `DATABASE_URL` mirroring it.

> **Why first:** Postgres only applies `POSTGRES_PASSWORD` when initializing
> an **empty** data volume. If you `docker compose up` before setting it,
> the DB keeps the weak dev password until you wipe the volume.

Now open `.env` and fill in the real credentials the script cannot know:

- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
  (service-role key is required for in-app account deletion). Leave
  `SUPABASE_JWT_SECRET` empty to use JWKS verification (recommended).
- `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` — **production** keyset;
  `EBAY_API_URL`/`EBAY_AUTH_URL` stay `https://api.ebay.com`.

## 2. Start Postgres and migrate

```powershell
.\scripts\windows\02-start-db.ps1
```

Runs `docker compose up -d`, waits for the health check, then
`alembic upgrade head`. Postgres binds `127.0.0.1:5432` only.

## 3. Install the backend (ROCm PyTorch)

```powershell
.\scripts\windows\03-install-backend.ps1
```

Creates `backend\.venv`, installs the ROCm 7.2.1 SDK + PyTorch wheels
**first** (so `requirements.txt` doesn't pull the CPU torch), then the app
requirements, pins `numpy==1.26.4` (2.x is incompatible with ROCm torch
wheels), and downloads the YOLOv8 DeepFashion2 weights.

Validate the GPU:

```powershell
backend\.venv\Scripts\python.exe scripts\validate_rocm.py
```

All checks should PASS. If GPU detection fails, set
`HSA_OVERRIDE_GFX_VERSION=12.0.1` and retry; the script's docstring has the
full fallback ladder (WSL2 → DirectML → CPU).

## 4. First boot + smoke test

Terminal A:

```powershell
.\scripts\windows\04-run-api.ps1
```

Terminal B:

```powershell
.\scripts\windows\05-smoke-test.ps1
```

The smoke test checks: `/health` is ok; `/docs` is **404** (production);
`/api/v1/search/segment` accepts a generated image and returns
`X-RateLimit-*` headers; `/api/v1/search/find` returns a results array;
an invalid Bearer token gets **401**.

## 5. Seed the database (~50k listings)

With production eBay creds in `.env` (run inside `backend\.venv`):

```powershell
cd C:\grailseeker
backend\.venv\Scripts\python.exe -m scripts.seed_db
```

This runs CLIP over every fetched image — expect it to take a while even on
GPU. Re-running is safe (duplicates are skipped by `platform_id`). The
scheduler inside the API keeps ingesting every `INGEST_INTERVAL_MINUTES`
afterwards, so the seed only needs to reach critical mass, not perfection.

## 6. Cloudflare Tunnel

Quick start (ephemeral URL, fine for TestFlight testing):

```powershell
.\scripts\windows\06-run-tunnel.ps1
```

Copy the printed `https://<random>.trycloudflare.com` URL into the mobile
build env as `EXPO_PUBLIC_API_BASE_URL`.

For a **stable** hostname (needed for a real release — the URL is baked
into the app binary):

```powershell
cloudflared tunnel login
cloudflared tunnel create grailseeker
cloudflared tunnel route dns grailseeker api.<your-domain>
cloudflared tunnel run --url http://localhost:8000 grailseeker
```

**Cloudflare dashboard (do once, manual):** add a rate-limiting rule
(e.g. 30 req/min per IP on `/api/*`) and enable Bot Fight Mode — this is
the still-open edge-hardening item from the security review.

## 7. Auto-start on boot

```powershell
.\scripts\windows\07-install-autostart.ps1
```

Registers two Scheduled Tasks (run whether user is logged on or not):
`GrailSeeker API` → `04-run-api.ps1`, and `GrailSeeker Tunnel` →
`06-run-tunnel.ps1` (edit the task afterwards if you switched to a named
tunnel). Docker Desktop must be set to start at sign-in (step 0). Logs land
in `logs\api.log` / `logs\tunnel.log`.

## 8. Routine operations

| Task | Command |
|---|---|
| Tail API logs | `Get-Content logs\api.log -Wait -Tail 50` |
| Restart API | `Stop-ScheduledTask -TaskName "GrailSeeker API"; Start-ScheduledTask -TaskName "GrailSeeker API"` |
| DB shell | `docker exec -it grailseeker-db psql -U grailseeker` |
| Listing count | `docker exec grailseeker-db psql -U grailseeker -tc "SELECT count(*) FROM listings WHERE is_active"` |
| Backup DB | `docker exec grailseeker-db pg_dump -U grailseeker grailseeker > backup.sql` |
| Update code | `git pull`, rerun steps 2 (migrations) and restart the API task |

## Troubleshooting

- **API starts but /segment 500s** — weights missing: rerun step 3's
  download, check `YOLO_WEIGHTS_PATH` in `.env`.
- **GPU not used (slow inference)** — `torch.version.hip` must not be
  `None`; rerun `validate_rocm.py`; check `HSA_OVERRIDE_GFX_VERSION`.
- **401 on all signed-in requests** — `SUPABASE_URL` wrong or the project's
  JWKS unreachable; guests still work.
- **DB auth failures after changing POSTGRES_PASSWORD** — the volume was
  already initialized; either `ALTER USER grailseeker PASSWORD ...` inside
  psql, or wipe with `docker compose down -v` (destroys data) and re-seed.
- **Tunnel URL changed** — ephemeral trycloudflare URLs rotate on restart;
  use a named tunnel for anything you ship.
