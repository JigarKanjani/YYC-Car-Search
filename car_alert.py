#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
car_alert.py — Calgary steal-deal car finder → Telegram.

Aggregates used-car listings for a fixed set of models (Toyota Corolla / Camry /
Yaris, Honda Civic / Accord, Mazda3 / Mazda6) from AutoTrader.ca (reliable) and
Facebook Marketplace (experimental), applies hard filters, scores each 1-10, and
sends only the strong deals (score ≥ 7) to Telegram — deduplicated by listing URL.

Filters:
  • one of the target models
  • price   ≤ $18,000 CAD
  • mileage ≤ 180,000 km
  • regular automatic only — no CVT, no manual, no turbo
  • Calgary
  • newly listed (dedup: only listings that appeared since the last scan)
  • score ≥ 7 / 10

Usage: python car_alert.py [--max-price 18000] [--max-km 180000] [--min-score 7]
"""

import os
import html
import json
import argparse
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import autotrader_client
import kijiji_client
import marketplace_client
from car_models import (WANTED, MODEL_META, model_key_from_title,
                        transmission_ok, engine_ok, is_cvt, is_manual, is_turbo,
                        score_car, CURRENT_YEAR)

WORKSPACE    = Path(__file__).parent
TRACKER_FILE = WORKSPACE / "car-tracker-seen.md"
BOT_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID      = os.environ.get("TELEGRAM_CHAT_ID", "")

MAX_PRICE = int(os.environ.get("CAR_MAX_PRICE", "18000"))
MAX_KM    = int(os.environ.get("CAR_MAX_KM", "180000"))
MAX_AGE   = int(os.environ.get("CAR_MAX_AGE_YEARS", "20"))
MIN_SCORE = float(os.environ.get("CAR_MIN_SCORE", "7"))
# On the first ever run the tracker is empty; seed it silently instead of
# blasting every current listing (honours "only newly listed").
SEED_SILENT = os.environ.get("CAR_SEED_SILENT", "1") not in ("0", "", "false")
MAX_PER_RUN = 40


def parse_ids(raw):
    return [c.strip() for c in (raw or "").split(",") if c.strip()]


CHAT_IDS = parse_ids(os.environ.get("TELEGRAM_CHAT_ID_CARS")) or \
           (parse_ids(CHAT_ID) if CHAT_ID else [])


def tg_send(text, chat_id):
    if len(text) > 4000:
        text = text[:3990] + "..."
    payload = json.dumps({
        "chat_id": str(chat_id), "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data=payload, headers={"Content-Type": "application/json; charset=utf-8"})
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


def load_seen():
    seen = set()
    if not TRACKER_FILE.exists():
        TRACKER_FILE.write_text(
            "| Year | Model | Price | KM | Score | Source | Date | URL |\n"
            "|------|-------|-------|----|-------|--------|------|-----|\n",
            encoding="utf-8")
        return seen
    for line in TRACKER_FILE.read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 9 and parts[8].startswith("http"):
            seen.add(parts[8])
    return seen


def append_tracker(l, score):
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = (f"| {l.get('year') or ''} | {MODEL_META.get(l.get('model_key'),{}).get('display','')[:20]} | "
           f"{l.get('price')} | {l.get('km')} | {score} | {l.get('source')} | "
           f"{date} | {l.get('url')} |\n")
    with open(TRACKER_FILE, "a", encoding="utf-8") as f:
        f.write(row)


def _esc(s):
    return html.escape(str(s or ""))


def evaluate(listing):
    """Apply all filters + scoring. Returns (ok, score, expected, deal_pct, model_key)."""
    title = listing.get("title", "")
    text = " ".join([title, listing.get("desc", ""), listing.get("transmission", "")])

    model_key = listing.get("model") or model_key_from_title(title)
    if not model_key or model_key not in MODEL_META:
        return False, 0, None, None, None
    # Ensure the listing really is this model (guards mis-tagged results).
    if model_key not in title.lower().replace(" ", "") and model_key not in title.lower():
        # AutoTrader per-model search is trustworthy; only enforce on Marketplace.
        if listing.get("source") == "marketplace":
            return False, 0, None, None, model_key

    price = listing.get("price_int")
    if not price or price > MAX_PRICE:
        return False, 0, None, None, model_key

    km = listing.get("km_int")
    if km is None:                       # can't verify the ≤ MAX_KM rule
        return False, 0, None, None, model_key
    if km > MAX_KM:
        return False, 0, None, None, model_key

    year = listing.get("year")
    if year and (CURRENT_YEAR - year) > MAX_AGE:
        return False, 0, None, None, model_key

    # Regular automatic only: no CVT, no manual, no turbo.
    if not transmission_ok(text) or not engine_ok(text):
        return False, 0, None, None, model_key

    score, exp, dp = score_car(model_key, year, km, price)
    if score < MIN_SCORE:
        return False, score, exp, dp, model_key
    return True, score, exp, dp, model_key


def format_message(listing, score, expected, dp):
    meta = MODEL_META.get(listing["model_key"], {})
    title = listing.get("title") or meta.get("display", "Car")
    stars = "⭐" * max(1, int(round(score / 2)))
    year = listing.get("year")
    age = f"{CURRENT_YEAR - year} yrs" if year else ""

    price_disp = listing.get("price") or (f"${listing['price_int']:,}" if listing.get("price_int") else "n/a")
    price_line = f"💰 <b>{_esc(price_disp)}</b>"
    if expected and dp is not None and dp > 0.03:
        price_line += f"  (est. fair ~${expected:,.0f} · {dp*100:.0f}% below)"
    elif expected:
        price_line += f"  (est. fair ~${expected:,.0f})"

    km_disp = listing.get("km") or (f"{listing['km_int']:,} km" if listing.get("km_int") else "")
    specs = " · ".join(x for x in [km_disp, age] if x)
    src = "AutoTrader" if listing.get("source") == "autotrader" else "Marketplace"

    lines = [
        f"🚗 <b>{_esc(title)}</b>  ·  {stars} <b>{score}/10</b>",
        price_line,
    ]
    if specs:
        lines.append(f"🛣️ {_esc(specs)}")
    lines.append(f"📍 {_esc(listing.get('location') or 'Calgary, AB')} · via {src}")
    lines.append(f"🔗 <a href=\"{_esc(listing.get('url'))}\">View listing</a>")
    return "\n".join(lines)[:3900]


def main():
    parser = argparse.ArgumentParser(description="Calgary steal-deal car finder")
    parser.add_argument("--max-price", type=int, default=MAX_PRICE)
    parser.add_argument("--max-km",    type=int, default=MAX_KM)
    parser.add_argument("--min-score", type=float, default=MIN_SCORE)
    args = parser.parse_args()

    year_min = CURRENT_YEAR - MAX_AGE
    print(f"\n{'='*60}")
    print(f"YYC CAR SEARCH — {datetime.now().strftime('%Y-%m-%d %H:%M')} MST")
    print(f"models: {len(WANTED)} | price<= ${args.max_price:,} | km<= {args.max_km:,} "
          f"| no CVT/manual/turbo | score>= {args.min_score} | Recipients: {len(CHAT_IDS)}")
    print(f"{'='*60}")

    if not BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN not set — cannot send.")
    if not CHAT_IDS:
        print("[ERROR] No recipients (TELEGRAM_CHAT_ID_CARS). Dry run.")

    seen = load_seen()
    first_run = len(seen) == 0
    print(f"Tracker: {len(seen)} listings already seen"
          + (" (first run — will seed silently)" if first_run and SEED_SILENT else ""))

    start_msg = (
        f"🚗 Calgary car steal-deal scan started "
        f"({datetime.now().strftime('%Y-%m-%d %H:%M')} MST)\n"
        f"🎯 Corolla/Camry/Yaris · Civic/Accord · Mazda3/6\n"
        f"💰 ≤ ${args.max_price:,} · ≤ {args.max_km:,} km · auto (no CVT/turbo) · score ≥ {args.min_score:g}\n"
        f"⏳ Only fresh deals will land here."
    )
    if not (first_run and SEED_SILENT):
        for cid in CHAT_IDS:
            tg_send(start_msg, cid)

    # Gather from all sources (AutoTrader = reliable; Kijiji + Marketplace best-effort).
    listings = autotrader_client.fetch_listings(WANTED, args.max_price, year_min, args.max_km)
    listings += kijiji_client.fetch_listings(WANTED, args.max_price, year_min, args.max_km)
    listings += marketplace_client.fetch_listings(WANTED, args.max_price, year_min, args.max_km)
    print(f"Combined: {len(listings)} raw listings from all sources")

    sent = 0
    for l in listings:
        if sent >= MAX_PER_RUN:
            break
        url = l.get("url")
        if not url or url in seen:
            continue

        ok, score, exp, dp, model_key = evaluate(l)
        if not ok:
            continue
        l["model_key"] = model_key

        # First-run seeding: record without alerting so we only ever message
        # genuinely newly-listed cars afterwards.
        seen.add(url)
        append_tracker(l, score)
        if first_run and SEED_SILENT:
            continue

        msg = format_message(l, score, exp, dp)
        print(f"  -> {score}/10 | {l.get('price')} | {l.get('km')} | {l.get('title')}")
        delivered = False
        for cid in CHAT_IDS:
            if tg_send(msg, cid):
                delivered = True
        if delivered or not CHAT_IDS:
            sent += 1

    if first_run and SEED_SILENT:
        summary = (f"✅ Car bot ready — seeded {len(seen)} current listings "
                   f"({datetime.now().strftime('%H:%M')} MST). "
                   f"You'll get only NEW deals (score ≥ {args.min_score:g}) from here on.")
    else:
        summary = (f"✅ Car scan done — {datetime.now().strftime('%Y-%m-%d %H:%M')} MST\n"
                   f"{sent} new deal(s) · ≤ ${args.max_price:,} · ≤ {args.max_km:,} km · score ≥ {args.min_score:g}")
    print(f"\n{summary}")
    for cid in CHAT_IDS:
        tg_send(summary, cid)
    print(f"{'='*60}\nDONE — {sent} sent")


if __name__ == "__main__":
    main()
