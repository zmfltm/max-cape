#!/usr/bin/env python3
"""Builds data/potions.json: every potion, with the item ids needed to price it.

Levels, XP and rates come from the wiki's Herblore training table. Prices do
not: the page's numbers go stale, so the site fetches them live from the
official price API instead, which is why we only need the ids here.

    python3 fetch_potions.py
"""

import html
import json
import os
import re
import urllib.parse
import urllib.request

from storage import atomic_json_dump

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "potions.json")
WIKI_API = "https://oldschool.runescape.wiki/api.php"
MAPPING = "https://prices.runescape.wiki/api/v1/osrs/mapping"
UA = "mudkip-osrs-plan/1.0 (personal planning page)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def clean(chunk):
    chunk = re.sub(r"<sup.*?</sup>", "", chunk, flags=re.S)
    chunk = re.sub(r"<[^>]+>", " ", chunk)
    return re.sub(r"\s+", " ", html.unescape(chunk)).strip()


def potion_rows():
    q = urllib.parse.urlencode({
        "action": "parse", "page": "Herblore training", "prop": "text",
        "format": "json", "formatversion": "2", "redirects": "1",
    })
    body = json.loads(get(f"{WIKI_API}?{q}"))["parse"]["text"]

    def is_potion_table(t):
        head = clean(t[:6000])
        return "Profit/XP" in head and "Secondary" in head and "Level" in head

    table = next(t for t in re.findall(r"<table.*?</table>", body, re.S)
                 if is_potion_table(t))

    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", table, re.S):
        cells = [clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        cells = [c for c in cells if c != ""]
        if len(cells) < 6 or not cells[0].isdigit():
            continue
        level, name, base, secondary, xp, rate = cells[:6]
        out.append({
            "level": int(level),
            "name": name,
            "unf": base,
            "secondary": secondary,
            "xp": float(xp.replace(",", "")),
            "rate": int(rate.replace(",", "")) if rate.replace(",", "").isdigit() else None,
        })
    return out


def price_ids():
    return {item["name"]: item["id"] for item in json.loads(get(MAPPING))}


def split_items(text):
    """'Super attack (4) Super strength (4)' -> two items; 'Amylase crystal (x4)'
    -> one item with a quantity."""
    text = text.strip()
    qty = 1
    m = re.search(r"\(x(\d+)\)$", text)
    if m:
        qty = int(m.group(1))
        text = text[:m.start()].strip()

    parts = re.findall(r"[A-Za-z'\- ]+?\s*\(\d\)", text)
    if parts:
        return [(re.sub(r"\s*\((\d)\)", r"(\1)", p).strip(), 1) for p in parts]
    return [(text, qty)]


def find_id(ids, *candidates):
    for c in candidates:
        if c in ids:
            return ids[c]
    return None


def recipe_ids(ids, potion):
    """Ingredient ids with quantities, and the id of what comes out."""
    inputs = []
    for source in (potion["unf"], potion["secondary"]):
        for name, qty in split_items(source):
            item = find_id(ids, name, name.replace(" (", "("),
                           f"{name}(4)", f"{name}(3)")
            if not item:
                return None, None
            inputs.append({"id": item, "qty": qty, "name": name})

    four_dose = any("(4)" in i["name"] for i in inputs)
    order = ((f'{potion["name"]}(4)', f'{potion["name"]}(3)') if four_dose
             else (f'{potion["name"]}(3)', f'{potion["name"]}(4)'))
    made = find_id(ids, *order, potion["name"])
    return inputs, made


def main():
    rows = potion_rows()
    ids = price_ids()
    print(f"{len(rows)} potions from the wiki, {len(ids)} tradeable items")

    priced, skipped = [], []
    for p in rows:
        inputs, made = recipe_ids(ids, p)
        if not inputs or not made:
            skipped.append(p["name"])
            continue
        p["inputs"] = inputs
        p["made"] = made
        priced.append(p)

    atomic_json_dump(OUT, {"potions": priced})

    print(f"{len(priced)} priceable, written to data/potions.json")
    if skipped:
        print("no tradeable match for: " + ", ".join(skipped))


if __name__ == "__main__":
    main()
