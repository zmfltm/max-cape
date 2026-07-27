#!/usr/bin/env python3
"""Builds data/diary_reqs.json: the skill levels each diary tier asks for.

Every diary page carries one {{DiarySkillStats}} block per tier, in tier order,
with the levels as plain parameters. That is far steadier to read than the
rendered tables.

Skill levels only. Diaries also gate on quests and items, which this does not
cover, so treat a tier as "the levels are there" rather than "doable".

    python3 fetch_diary_reqs.py
"""

import json
import os
import re
import time
import urllib.parse
import urllib.request

from storage import atomic_json_dump

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "diary_reqs.json")
API = "https://oldschool.runescape.wiki/api.php"
UA = "mudkip-osrs-plan/1.0 (personal planning page)"
TIERS = ["Easy", "Medium", "Hard", "Elite"]

# WikiSync's region names against the wiki's page titles
PAGES = {
    "Ardougne": "Ardougne Diary",
    "Desert": "Desert Diary",
    "Falador": "Falador Diary",
    "Fremennik": "Fremennik Diary",
    "Kandarin": "Kandarin Diary",
    "Karamja": "Karamja Diary",
    "Kourend": "Kourend & Kebos Diary",
    "Lumbridge": "Lumbridge & Draynor Diary",
    "Morytania": "Morytania Diary",
    "Varrock": "Varrock Diary",
    "Western": "Western Provinces Diary",
    "Wilderness": "Wilderness Diary",
}

SKIP = {"maxrefs", "boostable", "selectable", "total", "combat", "quests",
        "questpoints", "qp"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def wikitext(page):
    q = urllib.parse.urlencode({
        "action": "parse", "page": page, "prop": "wikitext",
        "format": "json", "formatversion": "2", "redirects": "1",
    })
    return json.loads(get(f"{API}?{q}"))["parse"]["wikitext"]


def blocks(text):
    """The {{DiarySkillStats}} bodies, in the order the page lists the tiers."""
    out, depth, start = [], 0, None
    for m in re.finditer(r"\{\{|\}\}", text):
        if m.group(0) == "{{":
            if depth == 0 and text.startswith("{{DiarySkillStats", m.start()):
                start = m.end()
            if start is not None:
                depth += 1
        elif start is not None:
            depth -= 1
            if depth == 0:
                out.append(text[start:m.start()])
                start = None
    return out


def levels(body):
    """'|Thieving = 72' pairs, ignoring the notes and the layout switches."""
    found = {}
    for line in body.split("\n|"):
        m = re.match(r"\s*([A-Za-z ]+?)\s*=\s*(\d+)\s*(?:<|$)", line)
        if not m:
            continue
        skill = m.group(1).strip()
        if skill.lower() in SKIP or skill.lower().endswith("notes"):
            continue
        found[skill] = max(found.get(skill, 0), int(m.group(2)))
    return found


def main():
    reqs, thin = {}, []
    for region, page in PAGES.items():
        found = blocks(wikitext(page))
        if len(found) < 4:
            thin.append(f"{region} ({len(found)} blocks)")
        reqs[region] = {t: levels(b) for t, b in zip(TIERS, found[:4])}
        print(f"{region:<12} " + "  ".join(
            f"{t[0]}:{len(reqs[region].get(t, {}))}" for t in TIERS))
        time.sleep(0.3)

    if thin:
        print("fewer than four blocks on: " + ", ".join(thin))
        print("keeping the previous data/diary_reqs.json")
        return 1

    atomic_json_dump(OUT, reqs, sort_keys=True)
    tiers = sum(1 for r in reqs.values() for t in r.values() if t)
    print(f"\n{tiers} tiers with skill requirements, written to data/diary_reqs.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
