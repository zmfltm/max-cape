"""Quest progress: WikiSync for what is done, the optimal quest guide for order.

WikiSync (sync.runescape.wiki) is the RuneLite plugin that uploads quest,
diary and level state to the Wiki. It provides the quest-completion data used
here; the Hiscores do not expose quest state. The plugin must have run on the
account at least once.
"""

import html
import json
import re
import urllib.parse
import urllib.request

SYNC = "https://sync.runescape.wiki/runelite/player/{}/STANDARD"
WIKI_API = "https://oldschool.runescape.wiki/api.php"
GUIDE = "Optimal quest guide"
QUEST_CAPE = "Quest point cape"
UA = "mudkip-osrs-plan/1.0 (personal planning page)"

NOT_STARTED, IN_PROGRESS, DONE = 0, 1, 2

SKILLS = {
    "Attack", "Hitpoints", "Mining", "Strength", "Agility", "Smithing",
    "Defence", "Herblore", "Fishing", "Ranged", "Thieving", "Cooking",
    "Prayer", "Crafting", "Firemaking", "Magic", "Fletching", "Woodcutting",
    "Runecraft", "Slayer", "Farming", "Construction", "Hunter", "Sailing",
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def sync_state(player):
    """The raw WikiSync payload for a player."""
    return json.loads(_get(SYNC.format(urllib.parse.quote(player))))


# The guide writes Recipe for Disaster subquests with a slash; WikiSync uses a dash.
RFD_MAP = {
    "Another Cook's Quest": "Another Cook's Quest",
    "Freeing the Mountain Dwarf": "Mountain Dwarf",
    "Freeing the Goblin generals": "Wartface & Bentnoze",
    "Freeing Pirate Pete": "Pirate Pete",
    "Freeing the Lumbridge Guide": "Lumbridge Guide",
    "Freeing Evil Dave": "Evil Dave",
    "Freeing Skrach Uglogwee": "Skrach Uglogwee",
    "Freeing Sir Amik Varze": "Sir Amik Varze",
    "Freeing King Awowogei": "King Awowogei",
    "Defeating the Culinaromancer": "Culinaromancer",
}


def _parse_quest_cape_requirements(wikitext):
    """Read the first (regular QPC) skill table, not the Master QPC table."""
    section = wikitext.split("==Minimum skill levels==", 1)
    if len(section) != 2:
        raise ValueError("Quest point cape page has no minimum-level section")
    start = section[1].find("{{DiarySkillStats")
    if start < 0:
        raise ValueError("Quest point cape minimum-level table was not found")
    end = section[1].find("\n\n", start)
    if end < 0:
        raise ValueError("Quest point cape minimum-level table was not terminated")
    body = section[1][start:end]
    values = {}
    for raw_name, level in re.findall(
            r"^\|([^=\n]+?)\s*=\s*(\d+)\s*$", body, re.MULTILINE):
        name = raw_name.strip()
        if name in SKILLS:
            values[name] = int(level)
    combat = re.search(r"^\|Combat\s*=\s*(\d+)\s*$", body, re.MULTILINE)
    if values.keys() != SKILLS or not combat:
        missing = sorted(SKILLS - values.keys())
        raise ValueError(f"incomplete Quest point cape requirements; missing {missing}")

    boostable = {
        name: int(level)
        for name, level in re.findall(
            r"\|([A-Za-z]+)Notes\s*=\s*\((\d+)\)", body
        )
        if name in SKILLS
    }
    return {"skills": values, "combat": int(combat.group(1)),
            "boostable": boostable}


def quest_cape_requirements():
    """Current minimum QPC levels from the OSRS Wiki."""
    q = urllib.parse.urlencode({
        "action": "parse", "page": QUEST_CAPE, "prop": "wikitext",
        "format": "json", "formatversion": "2",
    })
    body = json.loads(_get(f"{WIKI_API}?{q}"))["parse"]["wikitext"]
    return _parse_quest_cape_requirements(body)


def guide_route():
    """Every step of the optimal quest guide, in order.

    The guide tags each row with data-rowid, which is the cleanest handle on
    the route: it covers quests, achievement diary tiers and non-quest steps
    while preserving their order. Reading link order off the page instead picks up
    the 'Notable quest unlocks' list, which says outright that it is unordered.
    """
    q = urllib.parse.urlencode({
        "action": "parse", "page": GUIDE, "prop": "text",
        "format": "json", "formatversion": "2",
    })
    body = json.loads(_get(f"{WIKI_API}?{q}"))["parse"]["text"]

    seen, order = set(), []
    for m in re.finditer(r'data-rowid="([^"]+)"', body):
        rid = html.unescape(m.group(1))
        if rid not in seen:
            seen.add(rid)
            order.append(rid)
    return order


def normalise(rid):
    """Guide row ID -> (kind, name, extra)."""
    if "Diary#" in rid:
        region, tier = rid.split(" Diary#")
        return "diary", region, tier
    if rid.startswith("Recipe for Disaster/"):
        part = rid.split("/", 1)[1]
        mapped = RFD_MAP.get(part)
        return "quest", (f"Recipe for Disaster - {mapped}" if mapped else rid), None
    return "quest", rid, None


def guide_order(known, route=None):
    """Quest names only, in guide order, for anything that needs a flat list."""
    order, seen = [], set()
    for rid in route if route is not None else guide_route():
        kind, name, _ = normalise(rid)
        if kind == "quest" and name in known and name not in seen:
            seen.add(name)
            order.append(name)
    order += sorted(n for n in known if n not in seen)
    return order


TIERS = ["Easy", "Medium", "Hard", "Elite"]


def collect_diaries(raw, player=None):
    """Per-region, per-tier diary state from a WikiSync payload."""
    regions = []
    tier_done = {t: 0 for t in TIERS}

    for region, tiers in sorted((raw.get("achievement_diaries") or {}).items()):
        row = {"name": region, "tiers": {}}
        for tier in TIERS:
            entry = tiers.get(tier) or {}
            tasks = entry.get("tasks") or []
            done = sum(1 for t in tasks if t)
            complete = bool(entry.get("complete"))
            if complete:
                tier_done[tier] += 1
            row["tiers"][tier] = {
                "complete": complete,
                "done": len(tasks) if complete else done,
                "total": len(tasks),
            }
        regions.append(row)

    total_tiers = len(regions) * len(TIERS)
    return {
        "name": raw.get("username") or player,
        "synced": raw.get("timestamp"),
        "tiers": TIERS,
        "regions": regions,
        "done": sum(tier_done.values()),
        "total": total_tiers,
        "by_tier": tier_done,
        "region_count": len(regions),
    }


def route_steps(quests, diaries, route=None):
    """The guide route with each step marked done, started or outstanding."""
    steps = []
    for rid in route if route is not None else guide_route():
        kind, name, tier = normalise(rid)
        if kind == "diary":
            entry = (diaries.get(name) or {}).get(tier) or {}
            tasks = entry.get("tasks") or []
            steps.append({
                "kind": "diary", "name": f"{name} Diary", "tier": tier,
                "state": 2 if entry.get("complete") else (
                    1 if any(tasks) else 0),
                "done": sum(1 for t in tasks if t), "total": len(tasks),
                "wiki": f"{name.replace(' ', '_')}_Diary#{tier}",
            })
        elif name in quests:
            steps.append({
                "kind": "quest", "name": name, "state": quests[name],
                "wiki": name.replace(" ", "_"),
            })
        else:
            steps.append({
                "kind": "task", "name": name, "state": None,
                "wiki": name.replace(" ", "_"),
            })
    return steps


def collect(player, raw=None):
    raw = raw if raw is not None else sync_state(player)
    state = {
        "quests": {k: v for k, v in (raw.get("quests") or {}).items() if k != "."},
        "synced": raw.get("timestamp"),
        "username": raw.get("username") or player,
    }
    quests = state["quests"]
    route = guide_route()
    order = guide_order(set(quests), route)
    done = [n for n in order if quests.get(n) == DONE]
    started = [n for n in order if quests.get(n) == IN_PROGRESS]
    todo = [n for n in order if quests.get(n) != DONE]
    diaries = raw.get("achievement_diaries") or {}
    steps = route_steps(quests, diaries, route)
    # untracked steps (Tutorial Island, balloon routes) have no state, so they
    # never count as outstanding
    outstanding = [s for s in steps if s["state"] in (0, 1)]

    return {
        "name": state["username"],
        "synced": state["synced"],
        "route": steps,
        "route_next": outstanding[0] if outstanding else None,
        "route_left": len(outstanding),
        "order": order,
        "states": quests,
        "done": len(done),
        "total": len(order),
        "in_progress": started,
        "next": todo[0] if todo else None,
        "remaining": todo,
    }
