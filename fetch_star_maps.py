#!/usr/bin/env python3
"""Builds local map thumbnails for every shooting star crash site.

The wiki's Shooting Stars page renders each location with a Kartographer map:
the cell carries the rendered tile URLs, their offsets, and the game
coordinates. This stitches those tiles into one small PNG per location so the
site can show a map preview without calling out to anyone at view time.

    python3 fetch_star_maps.py

Writes assets/media/starmaps/*.png and assets/media/starmaps/manifest.json.
"""

import json
import os
import re
import time
import urllib.request

from PIL import Image
import io

from storage import atomic_binary_dump, atomic_json_dump

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets", "media", "starmaps")
API = "https://oldschool.runescape.wiki/api.php"
UA = "mudkip-osrs-plan/1.0 (personal planning page)"
SIZE = 200


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read() if binary else r.read().decode("utf-8", "replace")


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def strip_tags(html_text):
    text = re.sub(r"<sup.*?</sup>", "", html_text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).replace("&#160;", " ").strip()


def locations():
    """(name, lat, lon, [(tile_url, x_offset, y_offset)]) per crash site."""
    body = json.loads(get(f"{API}?action=parse&page=Shooting_Stars&prop=text"
                          "&format=json&formatversion=2&redirects=1"))["parse"]["text"]

    found = []
    for table in re.findall(r"<table.*?</table>", body, re.S):
        if "mw-kartographer-map" not in table:
            continue
        for row in re.findall(r"<tr>(.*?)</tr>", table, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if len(cells) < 3 or "kartographer" not in cells[-1]:
                continue
            name = strip_tags(cells[0])
            cell = cells[-1]

            lat = re.search(r'data-lat="(-?\d+)"', cell)
            lon = re.search(r'data-lon="(-?\d+)"', cell)
            urls = re.findall(r"url\((https://[^)]+?\.png)\)", cell)
            offsets = re.findall(r"(-?\d+)px\s+(-?\d+)px", cell)
            if not name or not urls:
                continue
            tiles = [(u, int(offsets[i][0]), int(offsets[i][1]))
                     for i, u in enumerate(urls) if i < len(offsets)]
            found.append({
                "name": name,
                "lat": int(lat.group(1)) if lat else None,
                "lon": int(lon.group(1)) if lon else None,
                "tiles": tiles,
            })
    return found


def compose(entry):
    """Stitch the wiki's tiles into one SIZE x SIZE image."""
    canvas = Image.new("RGB", (SIZE, SIZE), (18, 18, 20))
    drew = False
    for url, dx, dy in entry["tiles"]:
        try:
            tile = Image.open(io.BytesIO(get(url, binary=True))).convert("RGB")
        except Exception:                                         # noqa: BLE001
            continue
        canvas.paste(tile, (dx, dy))
        drew = True
        time.sleep(0.05)
    return canvas if drew else None


def main():
    os.makedirs(OUT, exist_ok=True)
    entries = locations()
    print(f"{len(entries)} crash sites on the wiki")

    manifest, missed = {}, []
    for entry in entries:
        name = entry["name"]
        fname = slug(name) + ".png"
        path = os.path.join(OUT, fname)

        if not os.path.exists(path):
            img = compose(entry)
            if img is None:
                missed.append(name)
                continue
            data = io.BytesIO()
            img.save(data, format="PNG", optimize=True)
            atomic_binary_dump(path, data.getvalue())

        manifest[name] = {"file": fname, "lat": entry["lat"], "lon": entry["lon"]}

    atomic_json_dump(os.path.join(OUT, "manifest.json"), manifest, sort_keys=True)

    total = sum(os.path.getsize(os.path.join(OUT, m["file"])) for m in manifest.values())
    print(f"{len(manifest)} maps, {total // 1024} KB")
    if missed:
        print("no tiles for: " + ", ".join(missed))


if __name__ == "__main__":
    main()
