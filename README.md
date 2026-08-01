# YYC Car Search — Steal-Deal Telegram Bot

Scans **AutoTrader.ca** (reliable) and **Facebook Marketplace** (experimental)
every 6 hours for **underpriced** used cars of a fixed set of models in Calgary,
scores each **1–10**, and Telegrams only the strong deals (**score ≥ 7**).
Same mechanism as the job / real-estate bots.

## What it looks for

**Models:** Toyota Corolla · Toyota Camry · Toyota Yaris · Honda Civic ·
Honda Accord · Mazda3 · Mazda6

**Hard filters:**
- Price **≤ $18,000 CAD**
- Mileage **≤ 180,000 km**
- **Regular automatic only** — no CVT, no manual, no turbo
- Calgary
- **Newly listed** — only cars that appeared since the last scan (first run seeds
  silently, so you only ever get genuinely new deals)
- **Score ≥ 7 / 10**

## The 1–10 scoring matrix

Every candidate is scored on four axes (your three — model, km, age — plus the
deal size that makes it a "steal"):

| Component | Max | Basis |
|---|---|---|
| **Deal** | 4 | how far the price is below the model's estimated fair value |
| **Mileage** | 3 | lower km scores higher |
| **Age** | 2 | newer scores higher |
| **Model** | 1 | reliability / resale desirability |

Fair value comes from a per-model reference table (`car_models.py`) that
estimates price by age + mileage — so a car priced well below its expected value
scores high. Only **≥ 7** is sent. Tune the table and weights to taste.

## Message

```
🚗 2016 Honda Civic LX  ·  ⭐⭐⭐⭐ 8.0/10
💰 $11,500  (est. fair ~$14,600 · 21% below)
🛣️ 120,000 km · 10 yrs
📍 Calgary, AB · via AutoTrader
🔗 View listing
```

Make/model, price (+ how far below fair value), mileage, age, location, source,
and a clickable listing link.

## Files

| File | Role |
|---|---|
| `car_models.py` | Target models, reference prices, transmission/engine rules, the 1–10 scoring matrix |
| `scraper.py` | Shared managed-scraper fetch layer (ScrapingBee / Scrape.do / ScraperAPI / proxy / direct) |
| `autotrader_client.py` | AutoTrader.ca per-model source adapter |
| `kijiji_client.py` | Kijiji (Cars & Trucks, Calgary) adapter — parses `__NEXT_DATA__` |
| `marketplace_client.py` | Facebook Marketplace adapter (experimental — see below) |
| `car_alert.py` | Orchestrator: aggregate → filter → score → dedup → Telegram |
| `car-tracker-seen.md` | Committed "already seen" state |
| `.github/workflows/yyc-car-search.yml` | 6-hour cron + manual trigger |

## Setup

1. Add Telegram secrets — `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID_CARS`
   (see `RECIPIENTS.md`).
2. Add **any one** managed-scraper key (all have free tiers) — required, since
   the sites block datacenter IPs:
   - `SCRAPINGBEE_API_KEY` — [scrapingbee.com](https://www.scrapingbee.com)
   - `SCRAPEDO_TOKEN` — [scrape.do](https://scrape.do) (1,000/mo free)
   - `SCRAPERAPI_KEY` — [scraperapi.com](https://www.scraperapi.com) (1,000/mo free)
   - or `CAR_PROXY` — your own residential proxy

   Auto-selected in that order. If one runs out of credits, set
   `SCRAPER_PROVIDER` (e.g. `scrapedo`) to force another, or just remove the
   exhausted key. Sources: AutoTrader (reliable) + Kijiji + Facebook Marketplace.
3. Run the **YYC Car Search** workflow (Actions tab) or wait for the cron.

> **Credit budgeting:** every fetch is one scraper request. 7 models × 3 sources
> × ~1 page × 4 runs/day ≈ hundreds/month. If you're on a 1,000/mo free tier,
> either run less often (change the cron to every 12h) or trim models/sources.

## Tuning

| What | Where |
|---|---|
| Models | `WANTED` in `car_models.py` |
| Reference prices / desirability | `MODEL_META` in `car_models.py` |
| Score threshold | `CAR_MIN_SCORE` env (default `7`) |
| Price / mileage / age | `CAR_MAX_PRICE` / `CAR_MAX_KM` / `CAR_MAX_AGE_YEARS` env |
| Scoring weights | `score_car()` in `car_models.py` |

## Facebook Marketplace (experimental)

Marketplace is **disabled by default** and is a best-effort bonus source.
Facebook aggressively blocks bots and usually shows a **login wall** to
unauthenticated requests, so without a logged-in session you'll typically get 0
results (logged clearly, not a crash).

To try it: set `FB_MARKETPLACE_ENABLED=1`, and for it to actually return data set
`FB_COOKIE` to a logged-in Facebook session cookie (forwarded to the scraper).
Even then it's fragile and may break when Facebook changes their markup.
**AutoTrader is the reliable backbone; treat Marketplace as extra.**

## Notes on limitations (honest)

- **CVT / turbo detection** is keyword-based on the listing text. A CVT or turbo
  car whose listing never says so can slip through; the gate reliably drops ones
  that *do* say "CVT"/"turbo"/"manual".
- **Freshness** relies on "new since last scan" (dedup) because AutoTrader's
  search cards don't carry a precise list time. With a 6-hour cron that keeps
  alerts well within your 12-hour intent.
- **Reference prices** are rough estimates — calibrate `MODEL_META` against what
  you see in the market.
