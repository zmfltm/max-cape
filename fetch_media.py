#!/usr/bin/env python3
"""Downloads OSRS Wiki images for every title in media.py into assets/media/.

Run once, or again after adding entries to media.py:

    python3 fetch_media.py

Writes assets/media/manifest.json (wiki title -> local filename). Titles the
wiki has no image for are reported and simply get no thumbnail on the site.
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

from media import all_titles
from storage import atomic_json_dump

API = "https://oldschool.runescape.wiki/api.php"
UA = "mudkip-osrs-plan/1.0 (personal static site; contact: local)"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "media")
THUMB = 160


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def thumbnails(titles):
    """Batch the pageimages query; returns {title: thumb url}."""
    out = {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        q = urllib.parse.urlencode({
            "action": "query",
            "prop": "pageimages",
            "piprop": "thumbnail",
            "pithumbsize": THUMB,
            "pilimit": "50",
            "format": "json",
            "titles": "|".join(batch),
        })
        data = json.loads(get(f"{API}?{q}"))
        pages = data.get("query", {}).get("pages", {})
        for p in pages.values():
            src = p.get("thumbnail", {}).get("source")
            if src:
                out[p["title"]] = src
        # normalisation can rename a title; map requested -> returned
        for n in data.get("query", {}).get("normalized", []):
            if n["to"] in out:
                out[n["from"]] = out[n["to"]]
        time.sleep(0.2)
    return out


def slug(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def main():
    os.makedirs(OUT, exist_ok=True)
    titles = all_titles()
    print(f"{len(titles)} titles")

    found = thumbnails(titles)
    manifest, missing = {}, []

    for t in titles:
        src = found.get(t)
        if not src:
            missing.append(t)
            continue
        ext = os.path.splitext(urllib.parse.urlparse(src).path)[1].lower() or ".png"
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            ext = ".png"
        name = slug(t) + ext
        path = os.path.join(OUT, name)
        if not os.path.exists(path):
            try:
                data = get(src)
            except Exception as exc:                      # noqa: BLE001
                print(f"  failed {t}: {exc}", file=sys.stderr)
                missing.append(t)
                continue
            with open(path, "wb") as f:
                f.write(data)
            time.sleep(0.15)
        manifest[t] = name

    atomic_json_dump(os.path.join(OUT, "manifest.json"), manifest, sort_keys=True)

    print(f"{len(manifest)} images in assets/media/")
    if missing:
        print("no image for: " + ", ".join(missing))


if __name__ == "__main__":
    main()
