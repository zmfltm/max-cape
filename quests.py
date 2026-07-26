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


def guide_order(known):
    """Quest names in optimal-quest-guide order, filtered to `known` names."""
    q = urllib.parse.urlencode({
        "action": "parse", "page": GUIDE, "prop": "text",
        "format": "json", "formatversion": "2",
    })
    body = json.loads(_get(f"{WIKI_API}?{q}"))["parse"]["text"]

    order, seen = [], set()
    for m in re.finditer(r'title="([^"]+)"', body):
        title = html.unescape(m.group(1))
        if title in known and title not in seen:
            seen.add(title)
            order.append(title)

    # anything WikiSync knows about but the guide never links (miniquests,
    # Recipe for Disaster subquests) goes on the end so nothing is lost
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
    return {
        "name": state["username"],
        "synced": state["synced"],
        "order": order,
        "states": quests,
        "done": len(done),
        "total": len(order),
        "in_progress": started,
        "next": todo[0] if todo else None,
        "remaining": todo,
    }
