"""OSRS hiscores helpers: fetch a player, plus the XP and combat formulas."""

import json
import urllib.parse
import urllib.request

ENDPOINT = "https://secure.runescape.com/m=hiscore_oldschool/index_lite.json"
UA = "mudkip-osrs-plan/1.0 (personal planning page)"

# Skills the plan tracks, in hiscores order
SKILL_ORDER = [
    "Attack", "Defence", "Strength", "Hitpoints", "Ranged", "Prayer", "Magic",
    "Cooking", "Woodcutting", "Fletching", "Fishing", "Firemaking", "Crafting",
    "Smithing", "Mining", "Herblore", "Agility", "Thieving", "Slayer",
    "Farming", "Runecraft", "Hunter", "Construction", "Sailing",
]


def xp_for_level(level):
    """Total XP required to reach `level` (level 1 = 0 xp)."""
    if level <= 1:
        return 0
    total = 0
    for i in range(1, level):
        total += int(i + 300 * (2 ** (i / 7.0)))
    return total // 4


XP_TABLE = {lv: xp_for_level(lv) for lv in range(1, 127)}


def combat_level(levels):
    """Standard OSRS combat level from a {skill: level} mapping."""
    g = lambda k: levels.get(k, 1)                                # noqa: E731
    base = 0.25 * (g("Defence") + g("Hitpoints") + (g("Prayer") // 2))
    melee = (13 / 40) * (g("Attack") + g("Strength"))
    ranged = (13 / 40) * ((g("Ranged") * 3) // 2)
    magic = (13 / 40) * ((g("Magic") * 3) // 2)
    return int(base + max(melee, ranged, magic))


def fetch(player):
    """Returns {"name", "skills": {name: {level, xp, rank}}, "overall", "combat"}."""
    url = f"{ENDPOINT}?{urllib.parse.urlencode({'player': player})}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = json.load(r)

    skills, overall = {}, None
    for entry in raw.get("skills", []):
        name, lvl = entry.get("name"), entry.get("level")
        rec = {"level": lvl, "xp": entry.get("xp"), "rank": entry.get("rank")}
        if name == "Overall":
            overall = rec
        elif name in SKILL_ORDER:
            skills[name] = rec

    levels = {k: v["level"] for k, v in skills.items()}
    return {
        "name": raw.get("name") or player,
        "skills": skills,
        "overall": overall or {"level": sum(levels.values()), "xp": 0, "rank": -1},
        "combat": combat_level(levels),
    }
