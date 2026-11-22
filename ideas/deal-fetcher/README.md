# Deal fetcher

Fetches every currently listed Marktguru offer for postcode **80804** from PENNY,
REWE, EDEKA, Lidl, and ALDI SÜD, then removes alcohol and obvious non-food items.
It uses Marktguru's public web API and discovers the current public keys from the
site at runtime, so there are no credentials to configure.

```bash
python ideas/deal-fetcher/fetch_deals.py
```

The command overwrites `data/latest.json`, archives the same result as
`data/YYYY-MM-DD.json`, and records store counts and errors in `data/summary.txt`.
`latest.json` groups stores and encodes offers as compact arrays. Each store's
`fields` array documents the positions; missing values are `null`. App prices and
pack sizes are extracted from offer text, while `normal_price` is Marktguru's
strike-through price. Filtering and category heuristics live near the top of
`fetch_deals.py` for easy maintenance.

The GitHub Actions workflow runs at 11:00 UTC each Sunday (12:00 in Berlin during
standard time; GitHub cron cannot automatically follow daylight-saving changes),
can also be run manually, and commits changed data to `main`.
