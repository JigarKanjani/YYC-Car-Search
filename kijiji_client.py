#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kijiji_client.py — Kijiji (Cars & Trucks, Calgary) source adapter.

Fetches per-model Kijiji search pages through the shared scraper and parses the
listings from the page's embedded __NEXT_DATA__ JSON (with a regex fallback).
Returns normalized listing dicts matching the other car sources.

Best-effort: Kijiji uses bot protection and changes its markup, so if a run
returns 0 the log says so and AutoTrader still carries the search.
"""

import os
import re
import json
import time
import urllib.parse

import scraper

ENABLED = os.environ.get("KIJIJI_ENABLED", "1") not in ("0", "", "false")

# Calgary Cars & Trucks category/location codes in the Kijiji URL.
BASE = "https://www.kijiji.ca"
CAT_LOC = "k0c174l1700199"          # c174 = Cars & Trucks, l1700199 = Calgary

_YEAR_RE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")
_KM_RE   = re.compile(r"([\d,]{4,})\s*(?:km|kms|kilomet)", re.I)
_NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_LINK_RE = re.compile(r'href="(/v-cars-trucks/[^"]+/(\d{6,}))"')


def _search_url(make, model, price_max):
    kw = urllib.parse.quote(f"{make} {model}")
    return f"{BASE}/b-cars-trucks/calgary/{kw}/{CAT_LOC}?price=0__{price_max}&sort=dateDesc"


def _price_to_int(val):
    """Kijiji price -> int dollars. Handles cents, dicts, and '$15,000'."""
    if val is None:
        return None
    if isinstance(val, dict):
        val = val.get("amount", val.get("value"))
    if val is None:
        return None
    try:
        n = float(re.sub(r"[^\d.]", "", str(val)))
    except ValueError:
        return None
    if n <= 0:
        return None
    # Amounts over 50k in our ≤$18k market are cents (e.g. 1500000 = $15,000).
    return int(n / 100) if n > 50000 else int(n)


def _km_from(text):
    m = _KM_RE.search(text or "")
    return int(m.group(1).replace(",", "")) if m else None


def _looks_like_listing(d):
    return (isinstance(d, dict) and d.get("title")
            and ("price" in d or "priceAmount" in d)
            and (d.get("url") or d.get("seoUrl") or d.get("id")))


def _walk(node, out):
    """Recursively collect listing-like dicts from the __NEXT_DATA__ tree."""
    if isinstance(node, dict):
        if _looks_like_listing(node):
            out.append(node)
        for v in node.values():
            _walk(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk(v, out)


def _normalize(d, model_key):
    title = re.sub(r"\s+", " ", str(d.get("title") or "")).strip()
    price_int = _price_to_int(d.get("price") if "price" in d else d.get("priceAmount"))
    if not title or not price_int:
        return None

    rel = d.get("seoUrl") or d.get("url") or ""
    if not rel and d.get("id"):
        rel = f"/v-cars-trucks/calgary/item/{d['id']}"
    url = rel if str(rel).startswith("http") else BASE + str(rel)

    # Mileage: from an attributes list if present, else from the title.
    km = None
    attrs = d.get("attributes") or d.get("adAttributes") or []
    if isinstance(attrs, list):
        for a in attrs:
            if isinstance(a, dict):
                nm = str(a.get("name", a.get("label", ""))).lower()
                if "kilomet" in nm or "mileage" in nm or nm == "carmileageinkms":
                    digits = re.sub(r"[^\d]", "", str(a.get("value", a.get("values", ""))))
                    km = int(digits) if digits else None
    if km is None:
        km = _km_from(title)

    ym = _YEAR_RE.search(title)
    return {
        "id":        str(d.get("id") or url.rstrip("/").split("/")[-1]),
        "title":     title,
        "price":     f"${price_int:,}",
        "price_int": price_int,
        "km":        f"{km:,} km" if km else "",
        "km_int":    km,
        "year":      int(ym.group(1)) if ym else None,
        "location":  "Calgary, AB",
        "url":       url.split("?")[0],
        "transmission": "",
        "desc":      title,
        "source":    "kijiji",
        "model":     model_key,
    }


def _parse(html, model_key):
    rows, seen = [], set()
    m = _NEXT_RE.search(html)
    if m:
        try:
            data = json.loads(m.group(1))
            cand = []
            _walk(data, cand)
            for d in cand:
                row = _normalize(d, model_key)
                if row and row["url"] not in seen:
                    seen.add(row["url"])
                    rows.append(row)
        except (json.JSONDecodeError, RecursionError):
            pass

    # Fallback: pull listing links from the HTML directly.
    if not rows:
        for href, lid in _LINK_RE.findall(html):
            url = BASE + href
            if url in seen:
                continue
            seen.add(url)
            rows.append({
                "id": lid, "title": "", "price": "", "price_int": None,
                "km": "", "km_int": None, "year": None, "location": "Calgary, AB",
                "url": url, "transmission": "", "desc": "", "source": "kijiji",
                "model": model_key,
            })
    return rows


def fetch_listings(models, price_max, year_min, km_max, pause=1.2):
    """Fetch Calgary Kijiji car listings for each (make, model)."""
    if not ENABLED:
        print("  [Kijiji] disabled (set KIJIJI_ENABLED=1).")
        return []

    all_rows, seen = [], set()
    for make, model in models:
        html = scraper.fetch(_search_url(make, model, price_max), render=True)
        if not html:
            continue
        rows = _parse(html, model)
        got = 0
        for r in rows:
            if not r.get("price_int") or r["url"] in seen:
                continue
            seen.add(r["url"])
            r["make"] = make
            all_rows.append(r)
            got += 1
        print(f"  [Kijiji] {make} {model}: {got} listings")
        time.sleep(pause)

    print(f"  [Kijiji] {len(all_rows)} total listings.")
    return all_rows
