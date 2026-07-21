# FitSnap

Visual search engine for second-hand clothing. Upload a photo, tap a detected garment, and get visually similar purchasable listings from resale platforms — no keyword search required.

GrailSeeker is **not** a marketplace: it doesn't host inventory or process transactions. It links out to existing listings on external platforms (eBay first, Depop/Poshmark/ThredUp planned for v2+).

**Core loop:** Upload photo → tap detected garment → see matching listings → buy on eBay.

## Why

Keyword search is broken for fashion — you can't type a "vibe," a specific denim fade, or a silhouette into a search bar. GrailSeeker replaces keyword search with visual search powered by computer vision and vector similarity, so users can screenshot an outfit from social media and find a purchasable equivalent.

## Tech Stack

| Layer | Technology |
|---|---|
| Mobile app | React Native + Expo SDK (Expo Router) |
| Backend API | FastAPI (Python) |
| Database | PostgreSQL + pgvector |
| Vision model | CLIP ViT (pre-trained, via ROCm on AMD GPU) |
| Segmentation model | YOLOv8 fine-tuned on DeepFashion2 |
| Data ingestion | eBay Browse API (official, 5,000 calls/day free tier) |
| Task scheduling | APScheduler (in-process) |
| Auth | Supabase Auth (Google + Apple sign-in) |
| Tunneling | Cloudflare Tunnel |
| Image storage | None — processed in memory, discarded after search |

## Architecture

```
Mobile App (Expo)  →  HTTPS via Cloudflare Tunnel  →  FastAPI backend
                                                          │
                                        ┌─────────────────┼─────────────────┐
                                        ▼                 ▼                 ▼
                                 PostgreSQL +        eBay Browse API   Supabase Auth
                                 pgvector            + APScheduler     (Google/Apple)
                                 (listings,
                                  embeddings)
```

The backend runs self-hosted on a Windows PC (AMD Ryzen 7 7700, RX 9070 XT 16GB via ROCm), exposed to the mobile app over a Cloudflare Tunnel. There's no cloud fallback in v1 — if the host machine sleeps or loses internet, the API is down.

## Repo Layout

```
ClothingApp/
├── backend/          FastAPI app, ML pipeline (CLIP + YOLOv8), eBay ingestion
│   ├── app/           API routes, models, schemas, services, ML inference
│   ├── scraper/        eBay Browse API client, ingestion + cleanup jobs, scheduler
│   ├── alembic/         DB migrations
│   └── tests/
├── mobile/           Expo Router app (camera/picker, segmentation UI, results, auth)
├── scripts/          Setup & ops scripts (seed DB, download model weights, tunnel, validation)
└── docker-compose.yml  Local Postgres + pgvector
```

## Getting Started

### Prerequisites
- Node.js + npm, Python 3.11+
- Docker (for local Postgres + pgvector), or a Postgres instance with the `pgvector` extension
- An [eBay Developer](https://developer.ebay.com) application (Browse API client ID/secret)
- A [Supabase](https://supabase.com) project (Auth)
- (Optional, for local inference) an AMD/ROCm or CUDA GPU — CPU works but is slow for CLIP/YOLOv8

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd .. && docker compose up -d          # starts Postgres + pgvector
cp .env.example .env                   # fill in Supabase + eBay credentials
cd backend && alembic upgrade head     # run DB migrations

python ../scripts/download_weights.py  # fetch YOLOv8 DeepFashion2 weights
python -m scripts.seed_db              # (optional) seed initial eBay listings

fastapi dev app/main.py                # start the API on :8000
```

Environment variables are documented in [.env.example](.env.example) — database URL, Supabase keys, eBay client credentials, CLIP/YOLO model config, rate limits, and image processing limits.

To expose the API to the mobile app over HTTPS:

```bash
./scripts/tunnel.sh
```

### Mobile

```bash
cd mobile
npm install
npm start          # then press i (iOS), a (Android), or w (web) — or scan the QR code in Expo Go
```

Configure the app via a `mobile/.env` (or shell env) with Expo public variables:

```bash
EXPO_PUBLIC_API_BASE_URL=https://<your-tunnel-or-local>:8000   # defaults to http://localhost:8000
EXPO_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=<anon key>
```

Without the Supabase variables the app still runs in guest mode; the login screen shows "Sign-in is not configured yet". Google/Apple providers must be enabled in the Supabase dashboard with the app's `grailseeker://` redirect URL allowed.

## Features (v1)

- **Upload:** camera capture or photo library picker; images processed in memory only, never persisted
- **Garment segmentation:** auto-detected bounding boxes for garments (tops, outerwear, bottoms, dresses — the DeepFashion2 class set); accessories (footwear, bags, headwear, jewelry, eyewear) are searchable via the always-available "Search entire image" fallback or the manual rectangle crop for logged-in users
- **Visual search:** top 20 similar listings per tapped garment, ranked by CLIP embedding cosine similarity via pgvector
- **Results:** confidence-labeled matches ("Similar match" between 0.4–0.7 similarity, hidden below 0.4), tap-through to the listing on eBay
- **Guest vs. logged-in:** guests get full upload/search; logged-in users (Supabase Auth) additionally get price filters, search history, and a saved items/wishlist
- **Rate limits:** 5 uploads/day (guest), 50 uploads/day (logged-in)

See [PRD.md](../PRD.md) for the full product spec, screen list, data pipeline, and out-of-scope items.

## Status

Phases 0–6 complete: full vertical slice (upload → segment → results → listing), Supabase auth with Google/Apple OAuth, rate limiting, saved items, search history, manual crop, price filters, dark mode, offline handling, and a passing backend test suite. Security hardening for self-hosting is in place: production mode (`ENVIRONMENT=production`) disables API docs and trusts only Cloudflare's client-IP header, Postgres binds to loopback with an env-driven password, `/find` has an abuse cap, listing stale-checks are throttled to protect the eBay call budget, oversized images are rejected before decode, and unhandled errors return a generic 500.

Remaining for launch (requires physical resources): eBay production credentials + initial 50k-listing seed on the Windows GPU host, Cloudflare Tunnel bring-up, Supabase OAuth provider configuration, EAS/TestFlight builds on a Mac with an Apple developer account, and the hand-labeled evaluation dataset (PRD §9).

Known scope decision: the DeepFashion2 segmentation model detects garments only (4 categories). Accessories are covered by whole-image search and manual crop — see PRD §4.2 vs. §8.1.
