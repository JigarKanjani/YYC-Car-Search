# Telegram Recipients — YYC Car Search Bot

This bot sends new Calgary used-car alerts to Telegram. Every recipient is a
numeric **chat ID**. Comma-separate to add several.

---

## 1. Bot token

Reuse the **same bot** as your other bots, or make a new one via **@BotFather**
(`/newbot`). Put its token in the repo secret **`TELEGRAM_BOT_TOKEN`**
(Settings → Secrets and variables → Actions).

## 2. Get a chat ID

⚠️ A bot can't message someone who hasn't messaged it first. Each recipient must
open the bot and tap **Start**.

**Easiest:** DM **@userinfobot** in Telegram — it replies with your numeric ID.
**For a group:** add the bot, send a message, then open
`https://api.telegram.org/bot<TOKEN>/getUpdates` and read the negative
`"chat":{"id":-100...}` value.

## 3. Add recipients

| Secret | Who receives what |
|---|---|
| `TELEGRAM_CHAT_ID` | default / fallback recipient |
| `TELEGRAM_CHAT_ID_CARS` | recipients for **car** alerts (comma-separated) |

Example:

```
747174717,123456789,-1001234567890
```

If `TELEGRAM_CHAT_ID_CARS` is unset, the bot falls back to `TELEGRAM_CHAT_ID`.

---

## 4. Required for GitHub Actions — get past AutoTrader.ca bot protection

AutoTrader.ca blocks GitHub's datacenter IPs. Set **one** (same keys as your
real-estate bot work here — reuse them):

- **`SCRAPINGBEE_API_KEY`** — [scrapingbee.com](https://www.scrapingbee.com) (recommended), **or**
- **`SCRAPEDO_TOKEN`** — [scrape.do](https://scrape.do), **or**
- **`CAR_PROXY`** — your own residential proxy (`http://user:pass@host:port`)

Auto-detected in that order. Force one with `SCRAPER_PROVIDER=scrapingbee|scrapedo|direct`.

> **Credits note:** this bot uses JS rendering (AutoTrader is dynamic), which
> costs more scraper credits per request than the real-estate bot. A 6-hour
> cadence with a few pages per run is still modest, but watch your provider
> dashboard. To reduce cost, set `SCRAPER_RENDER_JS=false` and see if listings
> still parse.

---

## 5. Filters

Set in the workflow (`.github/workflows/yyc-car-search.yml`) or as secrets/env:

| Env | Default | Meaning |
|---|---|---|
| `CAR_MAX_PRICE` | `18000` | max price CAD |
| `CAR_MAX_KM` | `250000` | max odometer km |
| `CAR_MAX_AGE_YEARS` | `20` | max age in years (min year computed dynamically) |
| `CAR_LOCATION` | `calgary` | required location substring (empty = any in radius) |

Changes take effect on the next scheduled run or a manual **Run workflow**.
