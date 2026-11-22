# Deal fetcher

**Goal:** Every Sunday 12:00 Europe/Berlin, fetch ALL current grocery offers for postcode 80804 (Munich) from PENNY and REWE (plus EDEKA, Lidl, ALDI SÜD) and write them to clean JSON that a separate Claude scheduled task reads to pick the best deals.

**Done when:**
- `ideas/deal-fetcher/data/latest.json` (overwritten) and `data/YYYY-MM-DD.json` (archive) exist, one object per offer: store, product, brand, price, app_price, reference_price, unit_price + unit, pack_size, valid_from, valid_to, category, description.
- PENNY returns well over 100 offers (marktguru lists ~300). `data/summary.txt` has counts per store and errors.
- GitHub Actions workflow runs Sundays 11:00 UTC + workflow_dispatch and commits the data back to main.

**Notes:**
- Source: marktguru.de. Its web page only shows ~14 offers per store; find the internal API (api.marktguru.de: base URL, public key headers, offers endpoint with zipCode/retailer/pagination) from the site's JS and fetch every page. If that fails, fall back to an aggregator with full text listings (kaufda.de, meinprospekt.de) and document which works.
- Drop non-food (clothes, gadgets, decor, tools) and alcohol.
- Python, minimal deps, short README.
- Delete this TASK.md in your final commit.
