# YYC Car Search — Telegram Bot

A self-contained bot that scans **AutoTrader.ca** every 6 hours for new
**used-car** listings in Calgary matching your criteria, and pushes each new one
to Telegram. Same mechanism as the job/real-estate bots, for cars.

**Filters (all configurable):**
- **Price:** ≤ $18,000 CAD
- **Age:** ≤ 20 years old (year ≥ current year − 20, computed dynamically)
- **Mileage:** ≤ 250,000 km
- **Location:** Calgary
- **Freshness:** "new" = not seen before, tracked by listing URL in a committed file

---

## How it works

```
GitHub Actions (cron, every 6h)
        │
        ▼
car_alert.py ──► autotrader_client.py ──► AutoTrader.ca Calgary search
        │                                     (price/year/odometer/location filters)
        │
        ├─ load seen URLs   (car-tracker-seen.md)
        ├─ filter: price · age · mileage · location
        ├─ send NEW listings ──► Telegram sendMessage
        └─ append new URLs to tracker, commit back to repo
```

| File | Role |
|---|---|
| `autotrader_client.py` | **Source adapter.** Fetches + parses AutoTrader.ca results. The only source-specific file — swap it for Kijiji / a managed actor and everything downstream is unchanged. |
| `car_alert.py` | **Orchestrator.** Dedup against the tracker, filter, format, send to Telegram. |
| `car-tracker-seen.md` | **Memory.** Committed table of every listing URL ever sent; makes "new" work across stateless runs. |
| `.github/workflows/yyc-car-search.yml` | **Scheduler.** 6-hour cron + manual trigger; commits the tracker back. |

---

## Setup

1. Add Telegram secrets — see [`RECIPIENTS.md`](./RECIPIENTS.md).
   At minimum `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID_CARS`.
2. Add a managed-scraper key (`SCRAPINGBEE_API_KEY` or `SCRAPEDO_TOKEN`) — the
   same keys used by the real-estate bot work here. AutoTrader.ca blocks
   datacenter IPs, so this is required on GitHub Actions.
3. Enable Actions and run the **YYC Car Search** workflow (Actions tab), or wait
   for the 6-hour cron.

## Run locally

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=...        # optional for a dry run
export TELEGRAM_CHAT_ID_CARS=...     # optional for a dry run
python car_alert.py --max-price 18000 --max-km 250000 --max-age 20
```

With no recipients set it does a **dry run** (fetch + print + track, no messages).
Test just the fetch/parse layer: `python autotrader_client.py`.

---

## Tuning

| What | Where |
|---|---|
| Price / mileage / age | `--max-price/--max-km/--max-age`, or `CAR_MAX_PRICE` / `CAR_MAX_KM` / `CAR_MAX_AGE_YEARS` env (set in the workflow) |
| Location match | `CAR_LOCATION` env (default `calgary`; empty = any within search radius) |
| Search radius | `prx` in `autotrader_client._search_url` (km around Calgary) |
| Cron cadence | `.github/workflows/yyc-car-search.yml` |

---

## Data-source note

AutoTrader.ca is Canada's largest used-car marketplace and supports the exact
filters we need (price/year/odometer/location) via URL params. It blocks
datacenter IPs, so requests route through a **managed scraper** (ScrapingBee or
Scrape.do — same keys as the other bots), auto-selected in this order and
printed at run start as `[AutoTrader] fetch mode: ...`:

| Priority | Configure | Mode |
|---|---|---|
| 1 | `SCRAPINGBEE_API_KEY` | ScrapingBee (`premium_proxy`, `country_code=ca`, JS render) |
| 2 | `SCRAPEDO_TOKEN` | Scrape.do (`super`, `geoCode=ca`, render) |
| 3 | `CAR_PROXY` | your own residential proxy |
| 4 | *(nothing)* | direct — only works from a residential IP |

The parser keys on human-readable patterns (`$`, `km`, 4-digit year) so it's
resilient to AutoTrader's HTML class-name changes. If a future markup change
returns 0 listings, the fetch-mode line still prints — check the log and the
selectors in `autotrader_client._parse_listings` may need one tweak.
