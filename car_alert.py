#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
car_alert.py — Calgary Used-Car Telegram Sender.

Fetches Calgary used-car listings from AutoTrader.ca, deduplicates against a
committed tracker file, applies the hard filters, and sends each new listing to
Telegram directly (no LLM, no extra deps beyond BeautifulSoup for parsing).

Filters (all overridable via env / CLI):
  • price   <= $18,000 CAD
  • age     <= 20 years  (year >= current_year - 20, computed dynamically)
  • odometer<= 250,000 km
  • location = Calgary

"New" = "not seen before" (tracked by listing URL), so running every 6 hours
surfaces whatever went up since last time.

Usage: python car_alert.py [--max-price 18000] [--max-km 250000] [--max-age 20]
"""

import os
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from autotrader_client import fetch_listings

WORKSPACE    = Path(__file__).parent
TRACKER_FILE = WORKSPACE / "car-tracker-seen.md"
BOT_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID      = os.environ.get("TELEGRAM_CHAT_ID", "")

# Filter defaults (overridable via env or CLI).
MAX_PRICE = int(os.environ.get("CAR_MAX_PRICE", "18000"))
MAX_KM    = int(os.environ.get("CAR_MAX_KM", "250000"))
MAX_AGE   = int(os.environ.get("CAR_MAX_AGE_YEARS", "20"))
# Location substring a listing must match (lowercase). Set "" to allow all.
LOCATION_MUST_MATCH = os.environ.get("CAR_LOCATION", "calgary").strip().lower()

MAX_PER_RUN = 40   # safety cap on messages per run


def parse_ids(raw):
    return [c.strip() for c in (raw or "").split(",") if c.strip()]


# TELEGRAM_CHAT_ID_CARS may hold a comma-separated list; falls back to CHAT_ID.
CHAT_IDS = parse_ids(os.environ.get("TELEGRAM_CHAT_ID_CARS")) or \
           (parse_ids(CHAT_ID) if CHAT_ID else [])


def tg_send(text, chat_id):
    """Send a plain-text message to Telegram. Auto-trims to 4000 chars."""
    if len(text) > 4000:
        text = text[:3990] + "..."
    payload = json.dumps({
        "chat_id": str(chat_id),
        "text": text,
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        print(f"  [TG ERROR] chat_id={chat_id} HTTP {e.code}: {body or e.reason}")
        return False
    except Exception as e:
        print(f"  [TG ERROR] chat_id={chat_id} {e}")
        return False


def load_seen_urls():
    """Return set of listing URLs already sent."""
    seen = set()
    if not TRACKER_FILE.exists():
        TRACKER_FILE.write_text(
            "| Year | Title | Price | KM | Location | Date | URL |\n"
            "|------|-------|-------|----|----------|------|-----|\n",
            encoding="utf-8",
        )
        return seen
    for line in TRACKER_FILE.read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 8 and parts[7].startswith("http"):
            seen.add(parts[7])
    return seen


def append_tracker(listing):
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = (f"| {listing.get('year') or ''} | {listing['title'][:40]} | "
           f"{listing['price']} | {listing['km']} | {listing['location'][:24]} | "
           f"{date} | {listing['url']} |\n")
    with open(TRACKER_FILE, "a", encoding="utf-8") as f:
        f.write(row)


def passes_filters(listing, max_price, min_year, max_km):
    """Apply the hard filters. Missing values are kept (don't silently drop),
    except location which must positively match when a filter is set."""
    p = listing.get("price_int")
    if p is not None and p > max_price:
        return False
    y = listing.get("year")
    if y is not None and y < min_year:
        return False
    k = listing.get("km_int")
    if k is not None and k > max_km:
        return False
    if LOCATION_MUST_MATCH:
        loc = (listing.get("location") or "").lower()
        # If AutoTrader didn't surface a location string, keep it (the search is
        # already Calgary-scoped); only drop when a location is present and wrong.
        if loc and LOCATION_MUST_MATCH not in loc:
            return False
    return True


def format_message(listing):
    title = listing["title"] or "Used car"
    if listing.get("year") and str(listing["year"]) not in title:
        title = f"{listing['year']} {title}"

    line_specs = []
    if listing.get("km"):
        line_specs.append(listing["km"])
    if listing.get("year"):
        line_specs.append(str(listing["year"]))
    specs = " · ".join(line_specs)

    msg = (
        f"🚗 {title}\n"
        f"💰 {listing.get('price') or 'Price not listed'}\n"
    )
    if listing.get("location"):
        msg += f"📍 {listing['location']}\n"
    if specs:
        msg += f"🛣️ {specs}\n"
    msg += f"\n🔗 {listing['url']}"
    return msg[:3900]


def main():
    parser = argparse.ArgumentParser(description="Calgary Used-Car Alert Sender")
    parser.add_argument("--max-price", type=int, default=MAX_PRICE)
    parser.add_argument("--max-km",    type=int, default=MAX_KM)
    parser.add_argument("--max-age",   type=int, default=MAX_AGE)
    args = parser.parse_args()

    min_year = datetime.now().year - args.max_age

    print(f"\n{'='*60}")
    print(f"YYC CAR SEARCH — {datetime.now().strftime('%Y-%m-%d %H:%M')} MST")
    print(f"price<= ${args.max_price:,} | year>= {min_year} (<= {args.max_age}y) "
          f"| km<= {args.max_km:,} | loc: {LOCATION_MUST_MATCH or 'any'}")
    print(f"Recipients: {len(CHAT_IDS)}")
    print(f"{'='*60}")

    if not BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN not set — cannot send.")
    if not CHAT_IDS:
        print("[ERROR] No recipients — set TELEGRAM_CHAT_ID_CARS or "
              "TELEGRAM_CHAT_ID. Continuing (dry run).")

    seen = load_seen_urls()
    print(f"Tracker: {len(seen)} listings already seen")

    start_msg = (
        f"🚗 Calgary used-car scan started "
        f"({datetime.now().strftime('%Y-%m-%d %H:%M')} MST)\n"
        f"💰 ≤ ${args.max_price:,} · ≤ {args.max_age} yrs · ≤ {args.max_km:,} km · Calgary\n"
        f"⏳ New matches will land here shortly."
    )
    for cid in CHAT_IDS:
        tg_send(start_msg, cid)

    listings = fetch_listings(args.max_price, min_year, args.max_km)

    sent = 0
    for listing in listings:
        if sent >= MAX_PER_RUN:
            break
        url = listing.get("url")
        if not url or url in seen:
            continue
        if not passes_filters(listing, args.max_price, min_year, args.max_km):
            continue

        msg = format_message(listing)
        print(f"  -> {listing.get('year')} {listing['title']} | "
              f"{listing['price']} | {listing['km']}")

        delivered = False
        for cid in CHAT_IDS:
            if tg_send(msg, cid):
                delivered = True

        seen.add(url)
        append_tracker(listing)
        if delivered or not CHAT_IDS:
            sent += 1

    summary_msg = (
        f"✅ Calgary used-car scan done — "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')} MST\n"
        f"{sent} new match(es) · ≤ ${args.max_price:,} · ≤ {args.max_age}y · "
        f"≤ {args.max_km:,} km\n"
        f"Source: AutoTrader.ca"
    )
    print(f"\n{summary_msg}")
    for cid in CHAT_IDS:
        tg_send(summary_msg, cid)

    print(f"{'='*60}\nDONE — {sent} new listings")


if __name__ == "__main__":
    main()
