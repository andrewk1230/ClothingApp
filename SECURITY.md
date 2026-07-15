# Security Policy

## Reporting a vulnerability

Please email **andrewkao1230@gmail.com** with a description of the issue,
steps to reproduce, and impact. You should get a response within a few
business days. Please do not open a public issue for security reports, and
allow a reasonable window for a fix before any disclosure.

## Scope

- **Backend** (`backend/`): FastAPI service — image upload handling,
  auth (Supabase JWT), rate limiting, eBay API integration.
- **Mobile** (`mobile/`): Expo React Native app.

Out of scope: vulnerabilities in eBay, Supabase, or Cloudflare themselves;
denial-of-service findings that require exceeding the documented rate
limits; reports from automated scanners without a demonstrated impact.

## Design notes for researchers

- Uploaded images are size-capped (10 MB), pixel-capped before full decode
  (decompression-bomb guard), format-allowlisted (JPEG/PNG/WebP), and are
  **not persisted** server-side.
- Auth tokens are Supabase JWTs verified via JWKS (RS256/ES256); invalid
  tokens are rejected, never downgraded to guest.
- Guest rate limiting keys on `CF-Connecting-IP` only in production
  (Cloudflare overwrites it); `X-Forwarded-For` is honored only in
  development.
- API docs (`/docs`, `/openapi.json`) are disabled in production.
- Postgres binds to loopback only; the API is served through a Cloudflare
  Tunnel with the uvicorn listener on loopback.
- Secrets live in `.env` (gitignored). If you find a committed secret,
  report it — rotation is the immediate response.

## Dependency hygiene

- `pip-audit` (backend) and `npm audit` (mobile) should be clean at every
  release; Dependabot watches both ecosystems (`.github/dependabot.yml`).
- Known constraint: `torch` pins `setuptools<82` while the audit floor is
  83 — the conflict is accepted because setuptools is unused at runtime
  (no cpp_extension builds); the full test suite passes with 83.
