#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scraper.py — shared managed-scraper fetch layer for the car sources.

One GET helper used by all source adapters (AutoTrader, Kijiji, Marketplace) so
they all support the same providers and you can swap between them with a single
env var. Providers (auto-selected in this order, or forced with SCRAPER_PROVIDER):

    SCRAPINGBEE_API_KEY  -> ScrapingBee   (premium_proxy, country_code=ca)
    SCRAPEDO_TOKEN       -> Scrape.do      (super, geoCode=ca)
    SCRAPERAPI_KEY       -> ScraperAPI     (premium, country_code=ca)
    CAR_PROXY            -> your own residential proxy
    (nothing)            -> direct         (only works from a residential IP)

Force one with SCRAPER_PROVIDER=scrapingbee|scrapedo|scraperapi|direct.
All are metered services with free tiers — if one runs out of credits, set
SCRAPER_PROVIDER (or remove its key) to fall back to another.
"""

import os
import urllib.parse
import urllib.request
import urllib.error

SCRAPINGBEE_API_KEY = os.environ.get("SCRAPINGBEE_API_KEY", "").strip()
SCRAPEDO_TOKEN      = os.environ.get("SCRAPEDO_TOKEN", "").strip()
SCRAPERAPI_KEY      = os.environ.get("SCRAPERAPI_KEY", "").strip()
SCRAPER_PROVIDER    = os.environ.get("SCRAPER_PROVIDER", "").strip().lower()
SCRAPER_COUNTRY     = os.environ.get("SCRAPER_COUNTRY", "ca").strip().lower()
SCRAPER_RENDER_JS   = os.environ.get("SCRAPER_RENDER_JS", "true").strip().lower()
CAR_PROXY           = os.environ.get("CAR_PROXY", "").strip()

SCRAPINGBEE_ENDPOINT = "https://app.scrapingbee.com/api/v1/"
SCRAPEDO_ENDPOINT    = "https://api.scrape.do/"
SCRAPERAPI_ENDPOINT  = "https://api.scraperapi.com/"

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/122.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
}


def active_provider():
    if SCRAPER_PROVIDER in ("scrapingbee", "scrapedo", "scraperapi"):
        return SCRAPER_PROVIDER
    if SCRAPER_PROVIDER == "direct":
        return ""
    if SCRAPINGBEE_API_KEY:
        return "scrapingbee"
    if SCRAPEDO_TOKEN:
        return "scrapedo"
    if SCRAPERAPI_KEY:
        return "scraperapi"
    return ""


def provider_label():
    return active_provider() or ("proxy" if CAR_PROXY else "direct")


def _opener(use_proxy):
    handlers = []
    if use_proxy and CAR_PROXY:
        handlers.append(urllib.request.ProxyHandler(
            {"http": CAR_PROXY, "https": CAR_PROXY}))
    return urllib.request.build_opener(*handlers)


def _build(url, render, cookie):
    """Return (Request, use_proxy, label) for the active provider."""
    provider = active_provider()
    rjs = SCRAPER_RENDER_JS if render is None else ("true" if render else "false")

    if provider == "scrapingbee":
        params = {"api_key": SCRAPINGBEE_API_KEY, "url": url,
                  "premium_proxy": "true", "country_code": SCRAPER_COUNTRY,
                  "render_js": rjs}
        headers = {}
        if cookie:
            params["forward_headers"] = "true"
            headers["Spb-Cookie"] = cookie
        api = SCRAPINGBEE_ENDPOINT + "?" + urllib.parse.urlencode(params)
        return urllib.request.Request(api, headers=headers), False, "ScrapingBee"

    if provider == "scrapedo":
        params = {"token": SCRAPEDO_TOKEN, "url": url, "super": "true",
                  "geoCode": SCRAPER_COUNTRY, "render": rjs}
        headers = {}
        if cookie:
            params["customHeaders"] = "true"
            headers["Cookie"] = cookie
        api = SCRAPEDO_ENDPOINT + "?" + urllib.parse.urlencode(params)
        return urllib.request.Request(api, headers=headers), False, "Scrape.do"

    if provider == "scraperapi":
        params = {"api_key": SCRAPERAPI_KEY, "url": url,
                  "country_code": SCRAPER_COUNTRY, "render": rjs, "premium": "true"}
        headers = {}
        if cookie:
            params["keep_headers"] = "true"
            headers["Cookie"] = cookie
        api = SCRAPERAPI_ENDPOINT + "?" + urllib.parse.urlencode(params)
        return urllib.request.Request(api, headers=headers), False, "ScraperAPI"

    headers = dict(BROWSER_HEADERS)
    if cookie:
        headers["Cookie"] = cookie
    return urllib.request.Request(url, headers=headers), True, "direct"


def fetch(url, render=None, cookie=None, timeout=90):
    """GET url through the active provider. Returns HTML text or None."""
    req, use_proxy, label = _build(url, render, cookie)
    try:
        with _opener(use_proxy).open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:160]
        except Exception:
            pass
        if e.code in (401, 402, 403, 429):
            print(f"  [scraper {label}] HTTP {e.code} — out of credits or blocked. "
                  f"Set SCRAPER_PROVIDER to another provider. {body}")
        else:
            print(f"  [scraper {label}] HTTP {e.code} {e.reason} {body}")
        return None
    except Exception as e:
        print(f"  [scraper {label}] error: {e}")
        return None
