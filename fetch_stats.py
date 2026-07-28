#!/usr/bin/env python3
"""Snapshots a player's OSRS Hiscores into data/stats.json.

    python3 fetch_stats.py "Your RSN"
    python3 build.py

The username is remembered, so later refreshes are just:

    python3 fetch_stats.py

The site works fine without this file; it simply shows targets instead of
current levels.
"""

import datetime
import json
import os
import sys
import urllib.error

from hiscores import fetch
from storage import atomic_json_dump

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "stats.json")


def remembered_name():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f).get("name")
    except (OSError, ValueError):
        return None


def main():
    player = " ".join(sys.argv[1:]).strip() or remembered_name()
    if not player:
        print('usage: python3 fetch_stats.py "Your RSN"', file=sys.stderr)
        return 2

    try:
        data = fetch(player)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print(f"'{player}' is not on the Hiscores. Check the spelling, and "
                  "note that unranked accounts do not appear.", file=sys.stderr)
        else:
            print(f"Hiscores error {exc.code}: {exc.reason}", file=sys.stderr)
        return 1
    except Exception as exc:                                      # noqa: BLE001
        print(f"could not reach the Hiscores: {exc}", file=sys.stderr)
        return 1

    data["fetched"] = datetime.datetime.now().astimezone().isoformat(timespec="minutes")

    atomic_json_dump(OUT, data, sort_keys=True)

    lv = data["overall"]["level"]
    n99 = sum(1 for s in data["skills"].values() if s["level"] >= 99)
    print(f"{data['name']}: total {lv}, combat {data['combat']}, {n99} skills at 99")
    print("wrote data/stats.json — now run python3 build.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
