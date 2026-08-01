#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
car_models.py — target models, reference prices, and the 1-10 scoring matrix.

Encodes the domain knowledge the car bot needs:
  • which makes/models to hunt for
  • an estimated fair-market ("expected") price per model by age + mileage,
    used to detect underpriced "steal" deals
  • transmission / engine rules (regular automatic only — no CVT, no turbo)
  • a score out of 10 that blends deal size, mileage, age, and model
"""

from datetime import datetime

CURRENT_YEAR = datetime.now().year

# ── Target models ────────────────────────────────────────────────────────────
# (make, model_slug) pairs used to build per-model AutoTrader / Marketplace
# searches. Edit this list to add/remove models.
#
# NOTE: "Toyota Yaris" is included for the "virus" request (phonetic match, and
# it can be had with a regular automatic). The Toyota Prius is intentionally
# NOT here — it is eCVT-only, which fails the "no CVT" rule.
WANTED = [
    ("toyota", "corolla"),
    ("toyota", "camry"),
    ("toyota", "yaris"),
    ("honda",  "civic"),
    ("honda",  "accord"),
    ("mazda",  "mazda3"),
    ("mazda",  "mazda6"),
]

# Per-model metadata: display name, a fair price for a ~5-year-old / ~90k km
# example (CAD, Calgary), and a desirability weight (reliability / resale).
# These are rough, tunable estimates — adjust to taste.
MODEL_META = {
    "corolla": {"make": "Toyota", "display": "Toyota Corolla", "base5yr": 20000, "desir": 1.0},
    "camry":   {"make": "Toyota", "display": "Toyota Camry",   "base5yr": 23000, "desir": 1.0},
    "yaris":   {"make": "Toyota", "display": "Toyota Yaris",   "base5yr": 14000, "desir": 0.8},
    "civic":   {"make": "Honda",  "display": "Honda Civic",    "base5yr": 21000, "desir": 1.0},
    "accord":  {"make": "Honda",  "display": "Honda Accord",   "base5yr": 23000, "desir": 0.9},
    "mazda3":  {"make": "Mazda",  "display": "Mazda3",         "base5yr": 19000, "desir": 0.9},
    "mazda6":  {"make": "Mazda",  "display": "Mazda6",         "base5yr": 20000, "desir": 0.85},
}

# Model-slug aliases so we can match a listing title to a model key.
MODEL_ALIASES = {
    "corolla": ["corolla"],
    "camry":   ["camry"],
    "yaris":   ["yaris"],
    "civic":   ["civic"],
    "accord":  ["accord"],
    "mazda3":  ["mazda3", "mazda 3", "mazda-3", "3 sport", "3 sedan"],
    "mazda6":  ["mazda6", "mazda 6", "mazda-6"],
}

# ── Transmission / engine rules (regular automatic only) ─────────────────────
CVT_MARKERS    = ["cvt", "continuously variable", "e-cvt", "ecvt"]
MANUAL_MARKERS = ["manual", "5-speed manual", "6-speed manual", "5mt", "6mt",
                  "stick shift", "standard transmission"]
TURBO_MARKERS  = ["turbo", "turbocharged", "1.5t", "2.0t", "2.5t", "skyactiv-g 2.5t"]


def model_key_from_title(title):
    """Return the model key whose alias appears in the title, else None."""
    t = (title or "").lower()
    for key, aliases in MODEL_ALIASES.items():
        if any(a in t for a in aliases):
            return key
    return None


def is_cvt(text):
    return any(m in (text or "").lower() for m in CVT_MARKERS)


def is_manual(text):
    return any(m in (text or "").lower() for m in MANUAL_MARKERS)


def is_turbo(text):
    return any(m in (text or "").lower() for m in TURBO_MARKERS)


def transmission_ok(text):
    """True unless the text says CVT or manual (we want a regular automatic).

    Absence of any keyword is treated as OK (assumed regular automatic) — the
    listing simply didn't specify. This is best-effort; a CVT listing that never
    says 'CVT' can slip through.
    """
    t = (text or "").lower()
    return not (is_cvt(t) or is_manual(t))


def engine_ok(text):
    """True unless the text indicates a turbo engine."""
    return not is_turbo(text or "")


def expected_price(model_key, year, km):
    """Estimated fair-market price (CAD) for a model at a given age + mileage."""
    meta = MODEL_META.get(model_key)
    if not meta or not year:
        return None
    base = meta["base5yr"]
    age = max(0, CURRENT_YEAR - year)
    price = base * (0.93 ** (age - 5))          # ~7%/yr around a 5-yr baseline
    if km:
        price -= max(0, (km - 120000)) / 1000 * 25   # high-km penalty (>120k)
        price += max(0, (120000 - km)) / 1000 * 20    # low-km bonus (<120k)
    return max(3000.0, price)


def deal_pct(model_key, year, km, price):
    """(expected - price)/expected. Positive = priced below market (a deal)."""
    exp = expected_price(model_key, year, km)
    if not exp or not price:
        return None
    return (exp - price) / exp


def score_car(model_key, year, km, price):
    """Blend deal size + mileage + age + model into a 1-10 score.

    Components (max): deal 4 · mileage 3 · age 2 · model 1  = 10
    Returns (score, expected_price, deal_pct).
    """
    meta = MODEL_META.get(model_key, {"desir": 0.8})
    exp = expected_price(model_key, year, km)
    dp = deal_pct(model_key, year, km, price)

    # Deal component (0-4): how far below fair market.
    if dp is None:
        deal_pts = 1.5
    elif dp >= 0.30:
        deal_pts = 4
    elif dp >= 0.20:
        deal_pts = 3.5
    elif dp >= 0.12:
        deal_pts = 3
    elif dp >= 0.05:
        deal_pts = 2.5
    elif dp >= -0.05:
        deal_pts = 1.5          # roughly at market
    else:
        deal_pts = 0.5          # above market

    # Mileage component (0-3).
    if km is None:
        km_pts = 1.5
    elif km <= 60000:
        km_pts = 3
    elif km <= 100000:
        km_pts = 2.5
    elif km <= 140000:
        km_pts = 2
    elif km <= 180000:
        km_pts = 1
    else:
        km_pts = 0.5

    # Age component (0-2).
    age = (CURRENT_YEAR - year) if year else None
    if age is None:
        age_pts = 1
    elif age <= 5:
        age_pts = 2
    elif age <= 10:
        age_pts = 1.5
    elif age <= 15:
        age_pts = 1
    else:
        age_pts = 0.5

    # Model desirability (0-1).
    model_pts = meta.get("desir", 0.8)

    score = max(1.0, min(10.0, deal_pts + km_pts + age_pts + model_pts))
    return round(score, 1), exp, dp
