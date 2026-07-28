#!/usr/bin/env python3
"""Snapshots quest and achievement diary progress from WikiSync.

Writes data/quests.json and data/diaries.json.

    python3 fetch_quests.py            # uses the linked account
    python3 fetch_quests.py "Your RSN"

Needs the WikiSync RuneLite plugin to have run on the account at least once;
that is what publishes quest state to sync.runescape.wiki. The hiscores do not
carry quest completion.
"""

import datetime
import json
import os
import sys
import urllib.error

from quests import collect, collect_diaries, quest_cape_requirements, sync_state
from storage import atomic_json_dump

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "quests.json")
DIARY_OUT = os.path.join(HERE, "data", "diaries.json")
STATS = os.path.join(HERE, "data", "stats.json")


def linked_name():
    for path in (OUT, STATS):
        try:
            with open(path, encoding="utf-8") as f:
                name = json.load(f).get("name")
            if name:
                return name
        except (OSError, ValueError):
            continue
    return None


def main():
    player = " ".join(sys.argv[1:]).strip() or linked_name()
    if not player:
        print('usage: python3 fetch_quests.py "Your RSN"', file=sys.stderr)
        return 2

    try:
        raw = sync_state(player)
        data = collect(player, raw)
        data["requirements"] = quest_cape_requirements()
        diaries = collect_diaries(raw, player)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print(f"WikiSync has nothing for '{player}'. Install the WikiSync "
                  "plugin in RuneLite, log in once, then try again.", file=sys.stderr)
        else:
            print(f"WikiSync error {exc.code}: {exc.reason}", file=sys.stderr)
        return 1
    except Exception as exc:                                      # noqa: BLE001
        print(f"could not fetch quest data: {exc}", file=sys.stderr)
        return 1

    stamp = datetime.datetime.now().astimezone().isoformat(timespec="minutes")
    data["fetched"] = stamp
    diaries["fetched"] = stamp
    atomic_json_dump(OUT, data)
    atomic_json_dump(DIARY_OUT, diaries)

    print(f"{data['name']}: {data['done']}/{data['total']} quests done, "
          f"{len(data['remaining'])} to go")
    if data["next"]:
        print(f"next up: {data['next']}")
    bt = diaries["by_tier"]
    print(f"diaries: {diaries['done']}/{diaries['total']} tiers "
          f"(hard {bt['Hard']}/{diaries['region_count']}, "
          f"elite {bt['Elite']}/{diaries['region_count']})")
    print("wrote data/quests.json and data/diaries.json — now run python3 build.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
