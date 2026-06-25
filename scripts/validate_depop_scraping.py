"""
Depop & eBay Scraping Feasibility Validation
=============================================
GrailSeeker Project — Visual search for second-hand clothing.

This script validates whether scraping Depop and eBay listings with Playwright
is viable for building our image+metadata pipeline. It tests anti-bot detection,
data extraction quality, and sustainable request pacing.

Usage:
    pip install playwright
    playwright install chromium
    python validate_depop_scraping.py

Legal note:
    This script accesses only publicly visible pages (no login required).
    Scraping publicly available data is generally protected under the hiQ Labs v.
    LinkedIn (2022) precedent, but platform Terms of Service may restrict automated
    access. For production use, prefer official APIs where available.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

# ---------------------------------------------------------------------------
# Check Playwright availability before importing it
# ---------------------------------------------------------------------------
try:
    from playwright.async_api import async_playwright, Error as PlaywrightError
except ImportError:
    print(
        "ERROR: playwright is not installed.\n"
        "  pip install playwright\n"
        "  playwright install chromium"
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Standardised listing dataclass — reused by the production scraper
# ---------------------------------------------------------------------------
class Platform(str, Enum):
    DEPOP = "depop"
    EBAY = "ebay"


@dataclass
class ScrapedListing:
    """Normalised representation of a scraped listing, platform-agnostic."""

    platform: Platform
    listing_url: str
    image_url: str
    title: str
    price: str  # kept as string to preserve currency symbol
    description: str = ""
    seller: str = ""
    size: str = ""
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["platform"] = self.platform.value
        return d


# ---------------------------------------------------------------------------
# Stealth helpers
# ---------------------------------------------------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 "
    "Firefox/126.0",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 720},
]

DEPOP_SEARCH_QUERIES = ["vintage jacket", "sneakers", "designer bag", "y2k top"]
EBAY_SEARCH_QUERIES = ["vintage leather jacket", "nike sneakers", "designer handbag"]

DELAY_BETWEEN_REQUESTS = 2  # seconds


# ---------------------------------------------------------------------------
# Report accumulator
# ---------------------------------------------------------------------------
@dataclass
class PlatformReport:
    platform: str
    total_pages_attempted: int = 0
    total_pages_loaded: int = 0
    total_listings_scraped: int = 0
    fields_extracted: list[str] = field(default_factory=list)
    blocked_at_request: Optional[int] = None
    block_type: Optional[str] = None  # "captcha", "403", "redirect", "timeout"
    errors: list[str] = field(default_factory=list)
    sample_listings: list[dict] = field(default_factory=list)
    stealth_mode: str = "default"

    @property
    def passed(self) -> bool:
        return self.total_listings_scraped >= 5

    def summary_line(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"[{status}] {self.platform} ({self.stealth_mode}): "
            f"{self.total_listings_scraped} listings from "
            f"{self.total_pages_loaded}/{self.total_pages_attempted} pages"
        )


# ---------------------------------------------------------------------------
# Browser context factories
# ---------------------------------------------------------------------------
async def make_default_context(playwright_instance):
    """Vanilla Playwright — no stealth mitigations."""
    browser = await playwright_instance.chromium.launch(headless=True)
    context = await browser.new_context()
    return browser, context


async def make_stealth_context(playwright_instance):
    """Playwright with stealth mitigations applied."""
    ua = random.choice(USER_AGENTS)
    vp = random.choice(VIEWPORTS)

    browser = await playwright_instance.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    context = await browser.new_context(
        user_agent=ua,
        viewport=vp,
        locale="en-US",
        timezone_id="America/New_York",
        # Pretend we have a normal browser fingerprint
        java_script_enabled=True,
        has_touch=False,
        is_mobile=False,
    )
    # Remove the webdriver flag that signals automation
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        // Overwrite the chrome.runtime to look non-automated
        window.chrome = { runtime: {} };
        // Overwrite permissions query
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);
        // Overwrite plugins length
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        // Overwrite languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
    """)
    return browser, context


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------
def is_blocked(page) -> Optional[str]:
    """Heuristic check for common blocking signals."""
    url = page.url.lower()
    if "captcha" in url or "challenge" in url or "recaptcha" in url:
        return "captcha"
    if "blocked" in url or "denied" in url:
        return "403"
    if "login" in url and "depop.com/login" in url:
        return "redirect"
    return None


async def check_response_block(response) -> Optional[str]:
    if response is None:
        return "timeout"
    if response.status == 403:
        return "403"
    if response.status == 429:
        return "rate_limit"
    if response.status >= 500:
        return "server_error"
    return None


# ---------------------------------------------------------------------------
# Depop scraper
# ---------------------------------------------------------------------------
async def scrape_depop_search(page, query: str) -> list[ScrapedListing]:
    """Scrape listings from a Depop search results page."""
    listings: list[ScrapedListing] = []

    url = f"https://www.depop.com/search/?q={query.replace(' ', '+')}"
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as exc:
        print(f"    Navigation error for Depop '{query}': {exc}")
        return listings

    block = await check_response_block(response)
    if block:
        print(f"    Blocked on Depop '{query}': {block} (status {response.status if response else 'N/A'})")
        return listings

    # Wait for content to render (Depop is a React SPA)
    await page.wait_for_timeout(3000)

    page_block = is_blocked(page)
    if page_block:
        print(f"    Blocked on Depop '{query}' (page-level): {page_block}")
        return listings

    # Depop uses various selectors across versions; try multiple strategies
    selectors_to_try = [
        # Strategy 1: anchor links to product pages with images
        'a[href*="/products/"]',
        # Strategy 2: listing card containers
        '[data-testid*="product"]',
        'li[class*="listing"]',
        # Strategy 3: generic product image containers
        'a[href^="/products/"] img',
    ]

    product_links = []
    for selector in selectors_to_try:
        try:
            elements = await page.query_selector_all(selector)
            if elements:
                product_links = elements
                print(f"    Found {len(elements)} elements with selector: {selector}")
                break
        except Exception:
            continue

    if not product_links:
        # Fallback: try to extract from page source / JSON-LD / __NEXT_DATA__
        try:
            next_data = await page.evaluate("""
                () => {
                    const el = document.querySelector('#__NEXT_DATA__');
                    return el ? JSON.parse(el.textContent) : null;
                }
            """)
            if next_data:
                print("    Found __NEXT_DATA__ JSON payload")
                # Extract products from Next.js data if available
                props = next_data.get("props", {}).get("pageProps", {})
                products = props.get("products", [])
                for p in products[:20]:
                    slug = p.get("slug", "")
                    image = ""
                    previews = p.get("preview", {})
                    if isinstance(previews, dict):
                        image = previews.get("url", "")
                    elif isinstance(previews, list) and previews:
                        image = previews[0].get("url", "") if isinstance(previews[0], dict) else str(previews[0])

                    listings.append(ScrapedListing(
                        platform=Platform.DEPOP,
                        listing_url=f"https://www.depop.com/products/{slug}/" if slug else "",
                        image_url=image,
                        title=p.get("description", "")[:100],
                        price=str(p.get("price", {}).get("amount", "")) if isinstance(p.get("price"), dict) else str(p.get("price", "")),
                        seller=p.get("seller", {}).get("username", "") if isinstance(p.get("seller"), dict) else "",
                        size=p.get("size", ""),
                    ))
                return listings
        except Exception as exc:
            print(f"    __NEXT_DATA__ extraction failed: {exc}")

    # DOM-based extraction from product link elements
    for elem in product_links[:20]:
        try:
            href = await elem.get_attribute("href") or ""
            listing_url = f"https://www.depop.com{href}" if href.startswith("/") else href

            # Try to find an image inside or near this element
            img = await elem.query_selector("img")
            image_url = ""
            if img:
                image_url = await img.get_attribute("src") or await img.get_attribute("data-src") or ""

            # Try to find price text
            price_text = ""
            price_el = await elem.query_selector('[class*="price"], [class*="Price"]')
            if price_el:
                price_text = (await price_el.inner_text()).strip()

            # Title from alt text or aria-label
            title = ""
            if img:
                title = await img.get_attribute("alt") or ""
            if not title:
                title = await elem.get_attribute("aria-label") or ""

            if listing_url and (image_url or title):
                listings.append(ScrapedListing(
                    platform=Platform.DEPOP,
                    listing_url=listing_url,
                    image_url=image_url,
                    title=title[:100],
                    price=price_text,
                ))
        except Exception:
            continue

    return listings


# ---------------------------------------------------------------------------
# eBay scraper
# ---------------------------------------------------------------------------
# NOTE: eBay has an official Browse API (https://developer.ebay.com/api-docs/buy/browse/overview.html)
# that provides structured search results, item details, and images.
# For production use in GrailSeeker, the Browse API is STRONGLY PREFERRED over scraping:
#   - No risk of being blocked
#   - Structured JSON responses
#   - Higher rate limits with a registered app
#   - Compliant with eBay ToS
#   - Free tier available for up to 5000 calls/day
# This scraping test exists only to validate whether eBay's public pages are
# parseable as a quick prototype path before API integration.

async def scrape_ebay_search(page, query: str) -> list[ScrapedListing]:
    """Scrape listings from an eBay search results page."""
    listings: list[ScrapedListing] = []

    url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sacat=11450"
    # _sacat=11450 is "Clothing, Shoes & Accessories"

    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as exc:
        print(f"    Navigation error for eBay '{query}': {exc}")
        return listings

    block = await check_response_block(response)
    if block:
        print(f"    Blocked on eBay '{query}': {block}")
        return listings

    await page.wait_for_timeout(2000)

    page_block = is_blocked(page)
    if page_block:
        print(f"    Blocked on eBay '{query}' (page-level): {page_block}")
        return listings

    # eBay's search results use a fairly stable DOM structure
    item_selectors = [
        ".s-item",            # standard search result item
        "[data-viewport]",    # newer layout
        ".srp-results .s-item__wrapper",
    ]

    items = []
    for selector in item_selectors:
        try:
            elements = await page.query_selector_all(selector)
            # Filter out the "Results matching fewer words" separator
            if len(elements) > 1:
                items = elements
                print(f"    Found {len(elements)} elements with selector: {selector}")
                break
        except Exception:
            continue

    for elem in items[:20]:
        try:
            # Title
            title_el = await elem.query_selector(".s-item__title")
            title = ""
            if title_el:
                title = (await title_el.inner_text()).strip()
                if title.lower().startswith("shop on ebay") or title.lower() == "results matching fewer words":
                    continue

            # Price
            price_el = await elem.query_selector(".s-item__price")
            price = ""
            if price_el:
                price = (await price_el.inner_text()).strip()

            # Image
            img_el = await elem.query_selector(".s-item__image-wrapper img")
            image_url = ""
            if img_el:
                image_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-src") or ""

            # Listing URL
            link_el = await elem.query_selector("a.s-item__link")
            listing_url = ""
            if link_el:
                listing_url = await link_el.get_attribute("href") or ""

            # Seller (sometimes visible in search results)
            seller = ""
            seller_el = await elem.query_selector(".s-item__seller-info-text, .s-item__seller-info")
            if seller_el:
                seller = (await seller_el.inner_text()).strip()

            if title and (image_url or listing_url):
                listings.append(ScrapedListing(
                    platform=Platform.EBAY,
                    listing_url=listing_url,
                    image_url=image_url,
                    title=title[:100],
                    price=price,
                    seller=seller,
                ))
        except Exception:
            continue

    return listings


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------
async def run_platform_test(
    playwright_instance,
    platform: str,
    queries: list[str],
    scrape_fn,
    stealth: bool = False,
) -> PlatformReport:
    """Run a scraping test for a given platform and stealth mode."""
    mode = "stealth" if stealth else "default"
    report = PlatformReport(platform=platform, stealth_mode=mode)
    print(f"\n{'='*60}")
    print(f"Testing {platform.upper()} — mode: {mode}")
    print(f"{'='*60}")

    try:
        if stealth:
            browser, context = await make_stealth_context(playwright_instance)
        else:
            browser, context = await make_default_context(playwright_instance)
    except Exception as exc:
        if "Executable doesn't exist" in str(exc) or "browserType.launch" in str(exc):
            print(
                "\nERROR: Chromium browser not installed for Playwright.\n"
                "  Run: playwright install chromium\n"
            )
            report.errors.append("Browser not installed")
            return report
        raise

    page = await context.new_page()
    all_listings: list[ScrapedListing] = []

    try:
        for i, query in enumerate(queries):
            report.total_pages_attempted += 1
            print(f"\n  [{i+1}/{len(queries)}] Searching: '{query}'")

            page_listings = await scrape_fn(page, query)

            if page_listings:
                report.total_pages_loaded += 1
                all_listings.extend(page_listings)
                print(f"    Scraped {len(page_listings)} listings")
            else:
                print(f"    No listings extracted")
                # Check if this looks like a block
                page_block = is_blocked(page)
                if page_block:
                    report.blocked_at_request = i + 1
                    report.block_type = page_block
                    report.errors.append(
                        f"Blocked at request {i+1}: {page_block}"
                    )
                    print(f"    BLOCKED ({page_block}) — stopping further requests")
                    break

            # Pacing delay
            if i < len(queries) - 1:
                delay = DELAY_BETWEEN_REQUESTS + random.uniform(0.5, 1.5)
                print(f"    Waiting {delay:.1f}s before next request...")
                await asyncio.sleep(delay)

    except Exception as exc:
        report.errors.append(f"Unexpected error: {exc}")
        print(f"  ERROR: {exc}")

    finally:
        await browser.close()

    report.total_listings_scraped = len(all_listings)

    # Determine which fields were successfully extracted
    fields_seen: set[str] = set()
    for listing in all_listings:
        if listing.image_url:
            fields_seen.add("image_url")
        if listing.title:
            fields_seen.add("title")
        if listing.price:
            fields_seen.add("price")
        if listing.listing_url:
            fields_seen.add("listing_url")
        if listing.seller:
            fields_seen.add("seller")
        if listing.size:
            fields_seen.add("size")
        if listing.description:
            fields_seen.add("description")
    report.fields_extracted = sorted(fields_seen)

    # Keep a few samples for the report
    report.sample_listings = [l.to_dict() for l in all_listings[:3]]

    print(f"\n  Result: {report.summary_line()}")
    return report


# ---------------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------------
def print_report(reports: list[PlatformReport]) -> None:
    print("\n")
    print("=" * 70)
    print("  SCRAPING FEASIBILITY REPORT — GrailSeeker")
    print(f"  Generated: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    for r in reports:
        print(f"\n--- {r.platform.upper()} ({r.stealth_mode}) ---")
        print(f"  Status:             {'PASS' if r.passed else 'FAIL'}")
        print(f"  Pages attempted:    {r.total_pages_attempted}")
        print(f"  Pages loaded:       {r.total_pages_loaded}")
        print(f"  Listings scraped:   {r.total_listings_scraped}")
        print(f"  Fields extracted:   {', '.join(r.fields_extracted) or 'none'}")
        if r.blocked_at_request:
            print(f"  Blocked at request: #{r.blocked_at_request} ({r.block_type})")
        if r.errors:
            print(f"  Errors:")
            for e in r.errors:
                print(f"    - {e}")
        if r.sample_listings:
            print(f"  Sample listing:")
            sample = r.sample_listings[0]
            for k, v in sample.items():
                if v:
                    print(f"    {k}: {str(v)[:80]}")

    # Overall verdict
    print("\n" + "=" * 70)
    print("  RECOMMENDATIONS")
    print("=" * 70)
    print("""
  1. DEPOP:
     - Depop is a React SPA with aggressive anti-bot protections.
     - Default Playwright will almost certainly be blocked.
     - Stealth mode may work for small-batch scraping but is fragile.
     - RECOMMENDED: Investigate Depop's undocumented mobile API endpoints
       (used by the app) or partner/affiliate data feeds.
     - Alternative: Use a headless browser service (Browserless, ScrapingBee)
       with built-in CAPTCHA solving for initial dataset bootstrapping.

  2. EBAY:
     - eBay's Browse API is the correct production approach.
       https://developer.ebay.com/api-docs/buy/browse/overview.html
     - Free tier: 5000 calls/day — sufficient for MVP.
     - Scraping works as a quick prototype but violates eBay ToS at scale.

  3. GENERAL:
     - For production scraping of any platform, use proxy rotation
       (residential proxies via Bright Data, Oxylabs, or SmartProxy).
     - Implement exponential backoff and request jitter.
     - Cache aggressively — avoid re-scraping the same listing within 24h.
     - Consider Poshmark and ThredUp as additional sources (both have APIs
       or more scraper-friendly pages).

  4. LEGAL:
     - Scraping publicly accessible pages is generally permissible under
       hiQ Labs v. LinkedIn (9th Cir. 2022) for non-CFAA purposes.
     - However, platforms' Terms of Service may prohibit automated access.
     - For GrailSeeker production: prefer APIs, attribute sources, and
       respect robots.txt rate limits.
     - Do NOT scrape behind-login content or circumvent access controls.
""")

    # Write machine-readable report
    report_path = "/Users/andrewkao/Documents/Codex/ClothingAPP/ClothingApp/scripts/scraping_report.json"
    report_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": [],
    }
    for r in reports:
        report_data["results"].append({
            "platform": r.platform,
            "stealth_mode": r.stealth_mode,
            "passed": r.passed,
            "pages_attempted": r.total_pages_attempted,
            "pages_loaded": r.total_pages_loaded,
            "listings_scraped": r.total_listings_scraped,
            "fields_extracted": r.fields_extracted,
            "blocked_at_request": r.blocked_at_request,
            "block_type": r.block_type,
            "errors": r.errors,
            "sample_listings": r.sample_listings,
        })
    try:
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)
        print(f"  Machine-readable report written to: {report_path}")
    except Exception as exc:
        print(f"  Could not write report file: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    print("GrailSeeker — Scraping Feasibility Validator")
    print(f"Started at {datetime.now(timezone.utc).isoformat()}")
    print(f"Delay between requests: {DELAY_BETWEEN_REQUESTS}s + jitter")
    print()

    reports: list[PlatformReport] = []

    async with async_playwright() as p:
        # --- Depop: default mode ---
        report = await run_platform_test(
            p, "depop", DEPOP_SEARCH_QUERIES, scrape_depop_search, stealth=False
        )
        reports.append(report)

        # --- Depop: stealth mode ---
        report = await run_platform_test(
            p, "depop", DEPOP_SEARCH_QUERIES, scrape_depop_search, stealth=True
        )
        reports.append(report)

        # --- eBay: default mode ---
        report = await run_platform_test(
            p, "ebay", EBAY_SEARCH_QUERIES, scrape_ebay_search, stealth=False
        )
        reports.append(report)

        # --- eBay: stealth mode ---
        report = await run_platform_test(
            p, "ebay", EBAY_SEARCH_QUERIES, scrape_ebay_search, stealth=True
        )
        reports.append(report)

    print_report(reports)


if __name__ == "__main__":
    asyncio.run(main())
