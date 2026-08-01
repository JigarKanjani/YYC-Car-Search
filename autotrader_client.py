#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autotrader_client.py — Calgary used-car fetcher.

Fetches used-car listings from AutoTrader.ca's Calgary search results and
returns a list of normalized listing dicts. AutoTrader.ca supports the exact
filters we need via URL params: price range, year range, odometer range, and
a location + proximity radius.

This is the ONLY source-specific file. Everything downstream (dedup, filtering,
Telegram formatting) consumes the normalized dicts, so a different source
(Kijiji Autos, a managed Apify actor, etc.) can be dropped in by re-implementing
`fetch_listings()` with the same return shape.

BOT PROTECTION: AutoTrader.ca blocks datacenter IPs. Like the real-estate bot,
requests route through a managed scraper (residential proxy) that clears the
block. Fetch mode is auto-selected: ScrapingBee > Scrape.do > proxy > direct.
Set one of: SCRAPINGBEE_API_KEY, SCRAPEDO_TOKEN, CAR_PROXY. Force one with
SCRAPER_PROVIDER=scrapingbee|scrapedo|direct.
"""

import os
import re
import time
import urllib.parse
import urllib.request
import urllib.error

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - installed via requirements.txt
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                    "beautifulsoup4>=4.12.0"], check=True)
    from bs4 import BeautifulSoup

# ── AutoTrader.ca search ─────────────────────────────────────────────────────
SEARCH_BASE = "https://www.autotrader.ca/cars/ab/calgary/"
SITE_BASE   = "https://www.autotrader.ca"

# ── Managed scraper config (same secrets as the other bots) ──────────────────
SCRAPINGBEE_API_KEY = os.environ.get("SCRAPINGBEE_API_KEY", "").strip()
SCRAPEDO_TOKEN      = os.environ.get("SCRAPEDO_TOKEN", "").strip()
SCRAPER_PROVIDER    = os.environ.get("SCRAPER_PROVIDER", "").strip().lower()
SCRAPER_COUNTRY     = os.environ.get("SCRAPER_COUNTRY", "ca").strip().lower()
SCRAPER_RENDER_JS   = os.environ.get("SCRAPER_RENDER_JS", "true").strip().lower()
CAR_PROXY           = os.environ.get("CAR_PROXY", "").strip()

SCRAPINGBEE_ENDPOINT = "https://app.scrapingbee.com/api/v1/"
SCRAPEDO_ENDPOINT    = "https://api.scrape.do/"

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/122.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
}


def _active_provider():
    """Return the managed-scraper provider to use, or "" for a direct call."""
    if SCRAPER_PROVIDER:
        return "" if SCRAPER_PROVIDER == "direct" else SCRAPER_PROVIDER
    if SCRAPINGBEE_API_KEY:
        return "scrapingbee"
    if SCRAPEDO_TOKEN:
        return "scrapedo"
    return ""


def _opener(use_proxy):
    handlers = []
    if use_proxy and CAR_PROXY:
        handlers.append(urllib.request.ProxyHandler(
            {"http": CAR_PROXY, "https": CAR_PROXY}))
    return urllib.request.build_opener(*handlers)


def _build_request(target_url):
    """Wrap target_url for the active provider. Returns (Request, use_proxy, label)."""
    provider = _active_provider()

    if provider == "scrapingbee":
        params = {
            "api_key": SCRAPINGBEE_API_KEY,
            "url": target_url,
            "premium_proxy": "true",
            "country_code": SCRAPER_COUNTRY,
            "render_js": SCRAPER_RENDER_JS,
        }
        api = SCRAPINGBEE_ENDPOINT + "?" + urllib.parse.urlencode(params)
        return urllib.request.Request(api, headers={}), False, "ScrapingBee"

    if provider == "scrapedo":
        params = {
            "token": SCRAPEDO_TOKEN,
            "url": target_url,
            "super": "true",
            "geoCode": SCRAPER_COUNTRY,
            "render": SCRAPER_RENDER_JS,
        }
        api = SCRAPEDO_ENDPOINT + "?" + urllib.parse.urlencode(params)
        return urllib.request.Request(api, headers={}), False, "Scrape.do"

    return urllib.request.Request(target_url, headers=dict(BROWSER_HEADERS)), True, "direct"


def _fetch(target_url, timeout=70):
    """GET target_url (through the active provider). Returns HTML text or None."""
    req, use_proxy, label = _build_request(target_url)
    try:
        with _opener(use_proxy).open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        if e.code in (403, 429) and "captcha" in body.lower():
            print(f"  [AutoTrader BLOCKED via {label}] HTTP {e.code} bot-protection. "
                  f"Configure SCRAPINGBEE_API_KEY / SCRAPEDO_TOKEN or CAR_PROXY.")
        else:
            print(f"  [AutoTrader HTTP {e.code} via {label}] {e.reason} {body[:160]}")
        return None
    except Exception as e:
        print(f"  [AutoTrader ERROR via {label}] {e}")
        return None


def _search_url(price_max, year_min, km_max, make=None, model=None, rcs=0, rcp=100):
    """Build an AutoTrader.ca Calgary search URL with our filters.

    Ranges are 'min,max' with either side optional:
      pRng=,18000   price up to 18000
      yRng=2006,    year 2006 and newer
      oRng=,250000  odometer up to 250000
    """
    params = {
        "rcp": rcp,               # results per page
        "rcs": rcs,               # result start index (pagination)
        "srt": 9,                 # sort: newest first
        "prx": 100,               # proximity radius (km) around loc
        "loc": "Calgary, AB",
        "pRng": f",{price_max}",
        "yRng": f"{year_min},",
        "oRng": f",{km_max}",
        "hprc": "True",           # include listings with price shown
        "wcp": "True",
        "inMarket": "advancedSearch",
    }
    base = SEARCH_BASE
    if make and model:
        base = f"{SITE_BASE}/cars/{make}/{model}/ab/calgary/"
    return base + "?" + urllib.parse.urlencode(params)


# ── Parsing helpers ──────────────────────────────────────────────────────────
_PRICE_RE = re.compile(r"\$\s?([\d,]{3,})")
_KM_RE    = re.compile(r"([\d,]{3,})\s*km", re.IGNORECASE)
_YEAR_RE  = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")


def _to_int(s):
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", str(s))
    return int(digits) if digits else None


def _parse_card(card):
    """Extract a normalized listing dict from one result-card element."""
    link_el = card.select_one('a[href*="/a/"]') or card.select_one("a[href]")
    if not link_el:
        return None
    href = link_el.get("href", "")
    if href.startswith("/"):
        href = SITE_BASE + href
    if "/a/" not in href:
        return None

    text = card.get_text(" ", strip=True)

    price_m = _PRICE_RE.search(text)
    km_m    = _KM_RE.search(text)
    year_m  = _YEAR_RE.search(text)

    # Title: prefer an explicit title element, else the link text.
    title_el = card.select_one('[class*="title"]') or link_el
    title = title_el.get_text(" ", strip=True) if title_el else ""
    title = re.sub(r"\s+", " ", title)[:100]

    # Location: last "City, AB" fragment (city starts with a capital, so we
    # don't swallow a preceding token like "km"). Locations sit near the end.
    loc_matches = re.findall(r"([A-Z][A-Za-z .'-]*?,\s*AB)\b", text)
    loc = loc_matches[-1].strip() if loc_matches else ""

    # Transmission hint if the card text mentions it.
    tm = re.search(r"\b(cvt|automatic|manual|[0-9]+\s*-?\s*speed)\b", text, re.I)

    return {
        "id":       href.rstrip("/").split("/")[-1],
        "title":    title,
        "price":    price_m.group(0) if price_m else "",
        "price_int": _to_int(price_m.group(1)) if price_m else None,
        "km":       km_m.group(0) if km_m else "",
        "km_int":   _to_int(km_m.group(1)) if km_m else None,
        "year":     int(year_m.group(1)) if year_m else None,
        "location": loc,
        "url":      href.split("?")[0],
        "transmission": tm.group(0) if tm else "",
        "desc":     text[:400],       # card text for CVT/turbo keyword scanning
        "source":   "autotrader",
    }


def _parse_listings(html):
    """Parse all result cards from a search results page."""
    soup = BeautifulSoup(html, "html.parser")

    # AutoTrader has changed card markup over time — try several containers,
    # then fall back to grouping by listing anchors.
    selectors = [
        'div[id^="result-item"]', "div.result-item", "div.dealer-split-wrapper",
        'div[class*="result-item"]', 'div[class*="listing"]', "article",
    ]
    cards = []
    for sel in selectors:
        cards = soup.select(sel)
        if len(cards) >= 2:
            break

    listings, seen = [], set()
    if cards:
        for card in cards:
            row = _parse_card(card)
            if row and row["url"] not in seen:
                seen.add(row["url"])
                listings.append(row)

    # Fallback: no recognizable cards — walk each listing anchor's parent block.
    if not listings:
        for a in soup.select('a[href*="/a/"]'):
            parent = a
            for _ in range(4):
                parent = parent.parent or parent
            row = _parse_card(parent)
            if row and row["url"] not in seen:
                seen.add(row["url"])
                listings.append(row)

    return listings


def fetch_listings(models, price_max, year_min, km_max, max_pages=2, rcp=100, pause=1.0):
    """Fetch Calgary used-car listings for each (make, model) in `models`.

    `models` is a list of (make, model_slug) pairs. Returns normalized dicts
    (see `_parse_card`), each also tagged with make/model.
    """
    provider = _active_provider() or ("proxy" if CAR_PROXY else "direct")
    print(f"  [AutoTrader] fetch mode: {provider} | "
          f"price<= {price_max:,} year>= {year_min} km<= {km_max:,} | "
          f"{len(models)} models")

    listings, seen = [], set()
    for make, model in models:
        got = 0
        for page in range(max_pages):
            url = _search_url(price_max, year_min, km_max, make=make, model=model,
                              rcs=page * rcp, rcp=rcp)
            html = _fetch(url)
            if not html:
                break
            page_rows = _parse_listings(html)
            if not page_rows:
                break
            new = 0
            for row in page_rows:
                if row["url"] not in seen:
                    seen.add(row["url"])
                    row["make"] = make
                    row["model"] = model
                    listings.append(row)
                    new += 1
                    got += 1
            if new == 0:
                break
            time.sleep(pause)
        print(f"  [AutoTrader] {make} {model}: {got} listings")

    print(f"  [AutoTrader] {len(listings)} total unique listings fetched")
    return listings


if __name__ == "__main__":
    from datetime import datetime
    yr_min = datetime.now().year - 20
    got = fetch_listings([("toyota", "corolla"), ("honda", "civic")],
                         18000, yr_min, 180000, max_pages=1)
    for l in got[:8]:
        print(f"  {l['year']} | {l['price']} | {l['km']} | {l['location']} | {l['title']}")
    print(f"Total: {len(got)}")
