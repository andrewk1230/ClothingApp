"""
Depop scraper — DEFERRED.

Validation testing (2026-06-25) confirmed:
  - Default Playwright: 100% blocked (403 on all requests)
  - Stealth mode: 1/4 queries succeeded, then blocked
  - Only extracted image_url and listing_url (no price, title, size)

For v2, investigate:
  - Depop's undocumented mobile API endpoints
  - Residential proxy rotation (Bright Data, Oxylabs)
  - Headless browser services with CAPTCHA solving (Browserless, ScrapingBee)
"""
