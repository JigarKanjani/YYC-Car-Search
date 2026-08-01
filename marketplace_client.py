#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
marketplace_client.py — Facebook Marketplace adapter (EXPERIMENTAL, best-effort).

Fetches Calgary Marketplace vehicle listings per model through the same managed
scraper as AutoTrader (residential proxy + JS render) and best-effort-parses the
listing JSON embedded in the page.

⚠️ RELIABILITY: Facebook Marketplace aggressively blocks bots and usually shows a
LOGIN WALL to unauthenticated requests from datacenter IPs. This adapter:
  • is DISABLED by default — enable with FB_MARKETPLACE_ENABLED=1
  • works best when you pass a logged-in session cookie via FB_COOKIE (forwarded
    to the scraper); without it you'll often get 0 results (login wall) — that's
    expected, not a bug, and it's logged clearly.
AutoTrader remains the reliable primary source; Marketplace is a bonus.
"""

import os
import re
import time
import json
import urllib.parse
import urllib.request
import urllib.error

ENABLED   = os.environ.get("FB_MARKETPLACE_ENABLED", "0") not in ("0", "", "false")
FB_COOKIE = os.environ.get("FB_COOKIE", "").strip()

SCRAPINGBEE_API_KEY = os.environ.get("SCRAPINGBEE_API_KEY", "").strip()
SCRAPEDO_TOKEN      = os.environ.get("SCRAPEDO_TOKEN", "").strip()
SCRAPER_PROVIDER    = os.environ.get("SCRAPER_PROVIDER", "").strip().lower()
SCRAPINGBEE_ENDPOINT = "https://app.scrapingbee.com/api/v1/"
SCRAPEDO_ENDPOINT    = "https://api.scrape.do/"

SEARCH = "https://www.facebook.com/marketplace/calgary/search"

_YEAR_RE  = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")
_KM_RE    = re.compile(r"([\d,]{4,})\s*(?:km|kms|kilometers)\b", re.I)
_TITLE_RE = re.compile(r'"marketplace_listing_title":"((?:[^"\\]|\\.)*)"')
_PRICE_RE = re.compile(r'"formatted_amount":"\$([\d,]+)"')
_ID_RE    = re.compile(r"marketplace/item/(\d+)")


def _provider():
    if SCRAPER_PROVIDER in ("scrapingbee", "scrapedo"):
        return SCRAPER_PROVIDER
    if SCRAPINGBEE_API_KEY:
        return "scrapingbee"
    if SCRAPEDO_TOKEN:
        return "scrapedo"
    return ""


def _fetch(url):
    """Fetch a Marketplace URL through the shared scraper (JS render + cookie)."""
    import scraper
    return scraper.fetch(url, render=True, cookie=FB_COOKIE or None)


def _looks_login_walled(html):
    low = html.lower()
    return ("you must log in to continue" in low
            or "log in to facebook" in low
            or ("login" in low and "marketplace_listing_title" not in low))


def _parse(html, model_key):
    """Best-effort extraction of (title, price, id) triples from the page JSON."""
    titles = [t.encode().decode("unicode_escape", "ignore")
              for t in _TITLE_RE.findall(html)]
    prices = _PRICE_RE.findall(html)
    ids    = list(dict.fromkeys(_ID_RE.findall(html)))   # unique, in order

    rows, seen = [], set()
    n = min(len(titles), len(prices))
    for i in range(n):
        title = re.sub(r"\s+", " ", titles[i]).strip()
        price_int = int(prices[i].replace(",", ""))
        lid = ids[i] if i < len(ids) else None
        if not lid or lid in seen:
            continue
        seen.add(lid)
        ym = _YEAR_RE.search(title)
        km = _KM_RE.search(title)
        rows.append({
            "id":        lid,
            "title":     title,
            "price":     f"${price_int:,}",
            "price_int": price_int,
            "km":        km.group(0) if km else "",
            "km_int":    int(km.group(1).replace(",", "")) if km else None,
            "year":      int(ym.group(1)) if ym else None,
            "location":  "Calgary, AB",
            "url":       f"https://www.facebook.com/marketplace/item/{lid}/",
            "transmission": "",
            "desc":      title,
            "source":    "marketplace",
            "model":     model_key,
        })
    return rows


def fetch_listings(models, price_max, year_min, km_max, pause=1.5):
    """Best-effort Marketplace fetch for each (make, model). Returns [] if disabled."""
    if not ENABLED:
        print("  [Marketplace] disabled (set FB_MARKETPLACE_ENABLED=1 to try).")
        return []

    all_rows, seen = [], set()
    for make, model in models:
        query = urllib.parse.quote(f"{make} {model}")
        url = (f"{SEARCH}?query={query}&maxPrice={price_max}"
               f"&sortBy=creation_time_descend&exact=false")
        html = _fetch(url)
        if not html:
            continue
        if _looks_login_walled(html):
            print(f"  [Marketplace] {make} {model}: login wall — set FB_COOKIE to a "
                  f"logged-in session to enable.")
            continue
        rows = _parse(html, model)
        got = 0
        for r in rows:
            if r["url"] in seen:
                continue
            seen.add(r["url"])
            r["make"] = make
            all_rows.append(r)
            got += 1
        print(f"  [Marketplace] {make} {model}: {got} listings")
        time.sleep(pause)

    print(f"  [Marketplace] {len(all_rows)} total listings (experimental).")
    return all_rows
