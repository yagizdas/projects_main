# Deal fetcher

Fetches this week's grocery offers for postcode **80804** from PENNY, REWE,
EDEKA, Lidl, and ALDI SÜD. EDEKA offers come from EDEKA's official feed for
local market **034167**; the other stores come from Marktguru. It excludes alcohol, pet food, supplements, and
obvious non-food offers using auditable text rules. Marktguru's offer response
does not expose category IDs, so product, brand, and description text are used.

```bash
python ideas/deal-fetcher/fetch_deals.py
```

The command overwrites the LLM-friendly `data/latest.md`, archives the same
result as `data/YYYY-MM-DD.md`, and writes counts, file size, normal-price
coverage, and errors to `data/summary.txt`. Offers are grouped by store and
validity window; each compact line contains the product description (shortened
to 120 characters), price, pack size, unit price, and normal price. Expired offers and offers beginning
more than six days after the run date are omitted, as are exact duplicates.

Marktguru supplies a separate `oldPrice` field for the normal/strike-through
price, but usually returns zero. The fetcher emits `statt` only when that field
contains a positive value; `referencePrice` is the unit price and is never
treated as a normal price.

The GitHub Actions workflow runs at 11:00 UTC each Sunday, can also be run
manually, and commits changed data to `main`.
