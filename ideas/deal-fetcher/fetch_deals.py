#!/usr/bin/env python3
"""Fetch this week's Munich grocery offers from Marktguru's public web API."""
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
BERLIN = ZoneInfo("Europe/Berlin")

# Offer objects do not contain Marktguru category IDs (product and brand IDs are unrelated).
ALCOHOL = re.compile(
    r"(?:\balkohol|\bbier(?!stangerl|schinken)|\bweizen(?:bier)?\b|\bpils\b|\bradler\b|"
    r"(?<!sch)wein|\bsekt\b|\bprosecco\b|\bspumante\b|\bchampagner\b|\bspirituose|\bwhisk(?:y|ey)\b|"
    r"\bwodka\b|\bvodka\b|\bgin\b|\brum\b|likör|\baperitif\b|\bcognac\b|\bbrandy\b|%\s*vol)", re.I)
NON_FOOD = re.compile(
    r"\b(?:akku\w*|bohrer|farbrolle|werkzeug|staubsauger|reiniger|waschmittel|spülmittel|"
    r"shampoo|duschgel|deo|parfüm|kosmetik|zahnpasta|toilettenpapier|küchenrolle|windel|"
    r"shirt|shorts|hose|strumpf|leggings|socke|schuh|jacke|kleid|pullover|wäsche|textil|"
    r"\w*bettwäsche|\w*betttuch|handtuch|puma|spielzeug|deko|(?:duft|stumpen)?kerzen?|lampe|kissen|decke|möbel|geschirr|besteck|"
    r"tasse|elektronik|batterie|kabel|kopfhörer|smartphone|fernseher|fahrrad|matratze|"
    r"garten|pflanze|blume|tanne|weihnachtsstern|baumständer|wärmflasche|buch|karte|"
    r"tierfutter|hundefutter|katzenfutter|katzennahrung|felix|whiskas|pedigree|vitamin\s*[a-z0-9]|"
    r"nahrungsergänzung|supplement|magnesium|zink|home creation|gardenline|jes collection)\b", re.I)
PACK = re.compile(
    r"(?<![\d,])(?P<amount>\d+(?:[.,]\d+)?)\s*(?:-\s*)?(?P<unit>kg|g|mg|l|ml|cl)"
    r"(?:\s*[- ]?(?:packung|pack|beutel|flasche|dose|glas|schale|figur))?\b", re.I)
APP_PRICE = re.compile(r"\b(?:mit\s+\w+\s+)?app\b.*?(\d+[.,]\d{2})\s*€", re.I)


def request_json(url: str, headers: dict[str, str], attempts: int = 3) -> dict[str, Any]:
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "deal-fetcher/1.0", **headers})
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt + 1 == attempts:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def api_headers() -> dict[str, str]:
    request = urllib.request.Request(f"{SITE}/r/penny", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
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
        payload = request_json(f"https://api.marktguru.de/api/v1/advertisers/retailer/{retailer}/offers?{query}", headers)
        batch = payload.get("results", [])
        offers.extend(batch)
        offset += len(batch)
        if not batch or offset >= payload.get("totalResults", offset):
            return offers


def local_date(value: str) -> dt.date:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(BERLIN).date()


def parse_pack(raw: dict[str, Any], text: str) -> str | None:
    match = PACK.search(text)
    if match:
        return f"{match.group('amount').replace('.', ',')} {match.group('unit')}"
    volume, quantity, unit = raw.get("volume"), raw.get("quantity"), raw.get("unit") or {}
    if volume and unit.get("shortName"):
        amount = f"{volume:g}".replace(".", ",")
        pack = f"{amount} {unit['shortName']}"
        return f"{quantity:g} × {pack}" if quantity and quantity != 1 else pack
    return None


def normalize(raw: dict[str, Any], today: dt.date) -> dict[str, Any] | None:
    product, brand = raw.get("product") or {}, raw.get("brand") or {}
    name, brand_name = product.get("name") or "", brand.get("name") or ""
    description = raw.get("description") or ""
    text = f"{name} {brand_name} {description}"
    if not name or ALCOHOL.search(text) or NON_FOOD.search(text):
        return None
    start, end = local_date(raw["validFrom"]), local_date(raw["validTo"])
    if end < today or start > today + dt.timedelta(days=6):
        return None
    app_match = APP_PRICE.search(description)
    old_price = raw.get("oldPrice")
    return {
        "store": (raw.get("retailer") or {}).get("name") or "Unbekannt",
        "product": name,
        "brand": None if brand_name == "thisisnobrand123" else brand_name,
        "price": raw.get("price"),
        "app_price": float(app_match.group(1).replace(",", ".")) if app_match else None,
        "normal_price": old_price if old_price and old_price > 0 else None,
        "unit_price": raw.get("referencePrice"),
        "unit": (raw.get("unit") or {}).get("shortName"),
        "pack": parse_pack(raw, description + " " + name),
        "from": start,
        "to": end,
    }


def money(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def date_range(start: dt.date, end: dt.date) -> str:
    return f"{start:%d.%m.}–{end:%d.%m.}"


def offer_line(offer: dict[str, Any]) -> str:
    product = offer["product"]
    if offer.get("brand"):
        product += f" ({offer['brand']})"
    price_parts = []
    if offer.get("price") is not None:
        price_parts.append(f"{money(offer['price'])} €")
    if offer.get("app_price") is not None:
        price_parts.append(f"App {money(offer['app_price'])}")
    parts = [product]
    if price_parts:
        parts.append(" · ".join(price_parts))
    if offer.get("pack"):
        parts.append(offer["pack"])
    if offer.get("unit_price") is not None and offer.get("unit"):
        parts.append(f"{money(offer['unit_price'])}/{offer['unit']}")
    if offer.get("normal_price") is not None:
        parts.append(f"statt {money(offer['normal_price'])}")
    return " | ".join(parts)


def render_markdown(offers: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for offer in offers:
        key = (offer["store"], offer["from"], offer["to"], offer_line(offer))
        if key not in seen:
            seen.add(key)
            unique.append(offer)
    unique.sort(key=lambda item: (item["store"], item["from"], item["to"], item["product"].casefold()))
    lines: list[str] = []
    current = None
    for offer in unique:
        group = (offer["store"], offer["from"], offer["to"])
        if group != current:
            if lines:
                lines.append("")
            lines.append(f"## {offer['store']} · {date_range(offer['from'], offer['to'])}")
            current = group
        lines.append(offer_line(offer))
    return "\n".join(lines) + "\n", unique


def run(output_dir: Path) -> tuple[dict[str, int], list[str], int]:
    today = dt.datetime.now(BERLIN).date()
    headers, offers, errors = api_headers(), [], []
    for retailer in RETAILERS:
        try:
            offers.extend(offer for item in fetch_retailer(retailer, headers) if (offer := normalize(item, today)))
        except Exception as exc:  # Preserve data from the other retailers.
            errors.append(f"{retailer.upper()}: {type(exc).__name__}: {exc}")
    rendered, offers = render_markdown(offers)
    stores = ("PENNY", "REWE", "EDEKA", "Lidl", "ALDI SÜD")
    counts = {name: sum(offer["store"] == name for offer in offers) for name in stores}
    normal_prices = sum(offer["normal_price"] is not None for offer in offers)
    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob("*.json"):
        old.unlink()
    (output_dir / "latest.md").write_text(rendered, encoding="utf-8")
    (output_dir / f"{today.isoformat()}.md").write_text(rendered, encoding="utf-8")
    lines = [f"Generated: {today.isoformat()}", f"Postcode: {POSTCODE}"]
    lines.extend(f"{store}: {count}" for store, count in counts.items())
    lines.extend((f"Offers with normal price: {normal_prices}/{len(offers)}", f"File size: {len(rendered.encode('utf-8'))} bytes"))
    lines.append("Errors: " + ("; ".join(errors) if errors else "none"))
    (output_dir / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts, errors, normal_prices


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("data"))
    args = parser.parse_args()
    counts, errors, normal_prices = run(args.output)
    print(" | ".join(f"{store} {count}" for store, count in counts.items()))
    print(f"Normal prices: {normal_prices}/{sum(counts.values())}")
    if errors:
        print("Errors: " + "; ".join(errors), file=sys.stderr)
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
