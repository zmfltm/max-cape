"""Quest progress: WikiSync for what is done, the optimal quest guide for order.

WikiSync (sync.runescape.wiki) is the RuneLite plugin that uploads quest,
diary and level state to the wiki. It is the only public source of OSRS quest
completion; the hiscores do not expose it. The plugin has to have run at least
once on the account.
"""

import html
import json
import re
import urllib.parse
import urllib.request

SYNC = "https://sync.runescape.wiki/runelite/player/{}/STANDARD"
WIKI_API = "https://oldschool.runescape.wiki/api.php"
GUIDE = "Optimal quest guide"
UA = "mudkip-osrs-plan/1.0 (personal planning page)"

NOT_STARTED, IN_PROGRESS, DONE = 0, 1, 2


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def sync_state(player):
    """The raw WikiSync payload for a player."""
    return json.loads(_get(SYNC.format(urllib.parse.quote(player))))


# the guide writes Recipe for Disaster subquests with a slash, WikiSync with a dash
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


def guide_route():
    """Every step of the optimal quest guide, in order.

    The guide tags each row with data-rowid, which is the cleanest handle on
    the route: it covers quests, achievement diary tiers and the non-quest
    steps, and it is ordered. Reading link order off the page instead picks up
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
    """Guide row id -> (kind, name, extra)."""
    if "Diary#" in rid:
        region, tier = rid.split(" Diary#")
        return "diary", region, tier
    if rid.startswith("Recipe for Disaster/"):
        part = rid.split("/", 1)[1]
        mapped = RFD_MAP.get(part)
        return "quest", (f"Recipe for Disaster - {mapped}" if mapped else rid), None
    return "quest", rid, None


def guide_order(known):
    """Quest names only, in guide order, for anything that needs a flat list."""
    order, seen = [], set()
    for rid in guide_route():
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


def route_steps(quests, diaries):
    """The guide route with each step marked done, started or outstanding."""
    steps = []
    for rid in guide_route():
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
    order = guide_order(set(quests))
    done = [n for n in order if quests.get(n) == DONE]
    started = [n for n in order if quests.get(n) == IN_PROGRESS]
    todo = [n for n in order if quests.get(n) != DONE]
    diaries = raw.get("achievement_diaries") or {}
    steps = route_steps(quests, diaries)
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
