#!/usr/bin/env python3
"""Fetch current Munich grocery offers from Marktguru's public web API."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

POSTCODE = "80804"
RETAILERS = ("penny", "rewe", "edeka", "lidl", "aldi-sued")
PAGE_SIZE = 100
SITE = "https://www.marktguru.de"

# Marktguru has no food/non-food flag. Keep the rules conservative and auditable.
ALCOHOL = re.compile(
    r"(?:\balkohol|\bbier(?!stangerl|schinken)|\bweizen(?:bier)?\b|\bpils\b|\bradler\b|"
    r"(?<!sch)wein|\bsekt\b|\bprosecco\b|\bchampagner\b|\bspirituose|\bwhisk(?:y|ey)\b|"
    r"\bwodka\b|\bvodka\b|\bgin\b|\brum\b|likör|\baperitif\b|\bcognac\b|\bbrandy\b|%\s*vol)", re.I
)
NON_FOOD = re.compile(
    r"\b(akku|bohrer|werkzeug|staubsauger|reiniger|waschmittel|spülmittel|shampoo|"
    r"dusche|deo|parfüm|kosmetik|creme|zahnpasta|toilettenpapier|küchenrolle|windel|"
    r"shirt|shorts|hose|strumpfhose|leggings|jogginghose|socken|schuh|jacke|kleid|pullover|wäsche|textil|handtuch|"
    r"spielzeug|deko|dekoration|kerze|lampe|kissen|decke|möbel|topf|pfanne|geschirr|besteck|"
    r"glas|tasse|elektr|gerät|batterie|kabel|kopfhörer|smartphone|fernseher|fahrrad|"
    r"garten|pflanze|blume|tanne|weihnachtsbaum|nordmann|tierfutter|hundefutter|katzenfutter|"
    r"grill|kohle|matratze|kraftstation|weinregal|nahrungsergänzung|supplement|vitamin(?:e)?|"
    r"mineralstoff|magnesium|zink|kapsel|tablette|brausetablette|mivolis|altapharma)\b", re.I
)

APP_PRICE = re.compile(r"\bMIT\b[^\n]{0,40}?\bAPP\b[^\d]{0,12}(\d+[.,]\d{2})\s*€", re.I)
PACK_SIZE = re.compile(
    r"\bje\s+(\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+(?:[.,]\d+)?)?\s*"
    r"(?:kg|g|mg|l|ml|cl|st(?:k|\.)?|stück))\b(?:-packung)?",
    re.I,
)

CATEGORIES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(words, re.I))
    for name, words in (
        ("Obst & Gemüse", r"obst|gemüse|apfel|banane|beere|traube|tomate|gurke|salat|kartoffel"),
        ("Fleisch & Fisch", r"fleisch|wurst|schinken|hähn|pute|rind|schwein|fisch|lachs|garnele"),
        ("Milchprodukte & Eier", r"milch|käse|joghurt|quark|butter|sahne|ei(er)?\b"),
        ("Backwaren", r"brot|brötchen|baguette|toast|kuchen|gebäck|croissant"),
        ("Getränke", r"wasser|saft|limonade|cola|tee|kaffee|drink"),
        ("Süßes & Snacks", r"schokolade|keks|bonbon|chips|snack|nüsse|eis\b"),
        ("Tiefkühlkost", r"tiefkühl|pizza|pommes"),
        ("Vorrat & Kochen", r"nudel|reis|mehl|zucker|öl|sauce|suppe|konserve|gewürz"),
    )
)


def request_json(url: str, headers: dict[str, str], attempts: int = 3) -> dict[str, Any]:
    """Request JSON with a small retry budget for transient API failures."""
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "deal-fetcher/1.0", **headers})
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt + 1 == attempts:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def api_headers() -> dict[str, str]:
    """Read the current public API credentials embedded in Marktguru's HTML."""
    req = urllib.request.Request(f"{SITE}/r/penny", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        page = response.read().decode("utf-8")
    match = re.search(r'<script type="application/json">(.*?)</script>', page, re.S)
    if not match:
        raise RuntimeError("Marktguru configuration was not found")
    config = json.loads(html.unescape(match.group(1)))["config"]
    return {"X-ApiKey": config["apiKey"], "X-ClientKey": config["clientKey"], "Accept": "application/json"}


def fetch_retailer(retailer: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    offers: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode({"as": "mobile", "zipCode": POSTCODE, "limit": PAGE_SIZE, "offset": offset})
        url = f"https://api.marktguru.de/api/v1/advertisers/retailer/{retailer}/offers?{query}"
        payload = request_json(url, headers)
        batch = payload.get("results", [])
        offers.extend(batch)
        offset += len(batch)
        if not batch or offset >= payload.get("totalResults", offset):
            return offers


def category_for(text: str) -> str:
    return next((category for category, pattern in CATEGORIES if pattern.search(text)), "Sonstige Lebensmittel")


def local_date(value: str) -> dt.date:
    """Convert a Marktguru UTC timestamp to its calendar date in Berlin."""
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Berlin")).date()


def normalize(raw: dict[str, Any], run_date: dt.date | None = None) -> dict[str, Any] | None:
    product = raw.get("product") or {}
    brand = raw.get("brand") or {}
    name = product.get("name") or ""
    description = raw.get("description") or ""
    text = f"{name} {brand.get('name', '')} {description}"
    if ALCOHOL.search(text) or NON_FOOD.search(text):
        return None

    run_date = run_date or dt.datetime.now(dt.timezone.utc).astimezone(ZoneInfo("Europe/Berlin")).date()
    valid_from = local_date(raw["validFrom"])
    valid_to = local_date(raw["validTo"])
    if valid_to < run_date or valid_from > run_date + dt.timedelta(days=7):
        return None

    unit = raw.get("unit") or {}
    volume = raw.get("volume")
    quantity = raw.get("quantity")
    pack_match = PACK_SIZE.search(description)
    pack_size = re.sub(r"\s+", " ", pack_match.group(1)).replace(",", ".") if pack_match else None
    if not pack_size and volume and unit.get("shortName"):
        pack_size = f"{volume:g} {unit['shortName']}"
        if quantity and quantity != 1:
            pack_size = f"{quantity:g} × {pack_size}"
    app_match = APP_PRICE.search(description)
    return {
        "product": name,
        "brand": brand.get("name"),
        "price": raw.get("price"),
        "app_price": float(app_match.group(1).replace(",", ".")) if app_match else None,
        "normal_price": raw.get("oldPrice") or None,
        "unit_price": raw.get("referencePrice"),
        "unit": unit.get("shortName"),
        "pack": pack_size,
        "from": valid_from.isoformat(),
        "to": valid_to.isoformat(),
        "category": category_for(text),
    }


def run(output_dir: Path) -> tuple[dict[str, int], list[str]]:
    headers = api_headers()
    fields = [
        "product", "brand", "price", "app_price", "normal_price", "unit_price",
        "unit", "pack", "from", "to", "category",
    ]
    stores: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    errors: list[str] = []
    for retailer in RETAILERS:
        try:
            raw = fetch_retailer(retailer, headers)
            cleaned = [offer for item in raw if (offer := normalize(item)) is not None]
            store = (raw[0].get("retailer") or {}).get("name", retailer.upper()) if raw else retailer.upper()
            compact = [[offer[field] for field in fields] for offer in cleaned]
            stores[store] = {"fields": fields, "offers": compact}
            counts[store] = len(cleaned)
        except Exception as exc:  # Continue so one unavailable retailer does not erase all data.
            errors.append(f"{retailer.upper()}: {type(exc).__name__}: {exc}")
            counts[retailer.upper()] = 0

    output_dir.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.now(dt.timezone.utc).astimezone(ZoneInfo("Europe/Berlin")).date().isoformat()
    rendered = json.dumps({"generated": today, "stores": stores}, ensure_ascii=False, separators=(",", ":")) + "\n"
    (output_dir / "latest.json").write_text(rendered, encoding="utf-8")
    (output_dir / f"{today}.json").write_text(rendered, encoding="utf-8")
    lines = [f"Generated: {today}", f"Postcode: {POSTCODE}"]
    lines.extend(f"{store}: {count}" for store, count in counts.items())
    lines.append("Errors: " + ("; ".join(errors) if errors else "none"))
    (output_dir / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("data"))
    args = parser.parse_args()
    counts, errors = run(args.output)
    print(" | ".join(f"{store} {count}" for store, count in counts.items()))
    if errors:
        print("Errors: " + "; ".join(errors), file=sys.stderr)
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
