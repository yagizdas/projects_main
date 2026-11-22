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
Each offer has stable fields even when Marktguru does not provide a value. An
app/coupon-marked offer is stored in `app_price`; the numeric `unit_price` and its
`unit` are separate fields. Filtering and category heuristics live near the top of
`fetch_deals.py` for easy maintenance.

The GitHub Actions workflow runs at 11:00 UTC each Sunday (12:00 in Berlin during
standard time; GitHub cron cannot automatically follow daylight-saving changes),
can also be run manually, and commits changed data to `main`.
