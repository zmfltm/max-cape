#!/usr/bin/env python3
"""Generates the static OSRS max-plan site: index.html + skills/*.html.

Edit SKILLS / PLAN below and re-run:  python3 build.py
"""

import base64
import datetime
import html
import json
import os
import re
import sys
import urllib.parse

from hiscores import XP_TABLE, xp_for_level
from media import METHOD_MEDIA, PROSE_ENTITIES
from slayer import TASKS as SLAYER_TASKS
from storage import atomic_text_dump

OUT = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# The plan
# --------------------------------------------------------------------------

# Current minimum base levels from the OSRS Wiki's Quest point cape page when
# the two permitted temporary boosts are used.
# fetch_quests.py snapshots the same table into data/quests.json; these values
# are the offline fallback and the single source for the plan's early targets.
QUEST_CAPE_REQUIREMENTS = {
    "Attack": 50, "Hitpoints": 50, "Mining": 70, "Strength": 60,
    "Agility": 70, "Smithing": 72, "Defence": 65, "Herblore": 70,
    "Fishing": 60, "Ranged": 62, "Thieving": 72, "Cooking": 72,
    "Prayer": 50, "Crafting": 70, "Firemaking": 75, "Magic": 75,
    "Fletching": 70, "Woodcutting": 74, "Runecraft": 60, "Slayer": 74,
    "Farming": 70, "Construction": 70, "Hunter": 70, "Sailing": 62,
}
QUEST_CAPE_COMBAT = 85
QUEST_CAPE_BOOSTABLE = {"Mining": 72, "Fishing": 62}
QUEST_CAPE_COMPOSITE = "While Guthix Sleeps wants Attack + Strength 130, or 99 in either."

# The account already meets the omitted minimums. Keeping only live blockers
# makes the overview useful without presenting the hard-diary targets as QPC
# requirements (the source of the old 100-combat/70-Ranged error).
QUEST_CAPE_BLOCKERS = [
    "Ranged", "Magic", "Smithing", "Firemaking", "Runecraft", "Hunter",
    "Agility", "Thieving", "Slayer", "Woodcutting", "Cooking", "Sailing",
]

PLAN_PHASES = [
    dict(title="Clear the quest blockers",
         reqs=[(name, QUEST_CAPE_REQUIREMENTS[name])
               for name in QUEST_CAPE_BLOCKERS],
         combat=QUEST_CAPE_COMBAT,
         subs=["Follow the quest route. Train only enough to unblock the next quests.",
               "Train combat on Slayer. Cannon and burst tasks carry Ranged and Magic with it.",
               QUEST_CAPE_COMPOSITE]),
    dict(title="Quest Cape", track="quests", subs=[]),
    dict(title="All Hard Diaries", track="diary_hard", diary_tier="Hard",
         subs=[]),
    dict(title="Slayer to 95", track="slayer", subs=[]),
    dict(title="Elite diary levels",
         track="diary_elite", diary_tier="Elite", subs=[]),
    dict(title="Max Cape", track="max", subs=[]),
]

COMBAT_APPROACH = [
    "Nieve or Steve for now.",
    "Konar for milestone points.",
    "Duradel at 100 combat, 50 Slayer and Shilo Village.",
    "Cannon multi tasks for Ranged.",
    "Burst stacked tasks for Magic.",
    "Melee order: Strength, Attack, Defence. 75 each, then 80 each, then Strength to 85.",
    "Dedicated styles reach each milestone sooner. A hasta on Controlled is the low-maintenance option, best on stab-weak tasks.",
    "The 80s pass puts you at 100 combat. Switch to Duradel there.",
    "Let Slayer carry combat XP. Do not grind it on its own.",
    "Attack 75 wields Hallowfell. After Slayer 99, the melee 99s happen at the maniacal monkeys, not on tasks.",
]


# --------------------------------------------------------------------------
# Skills.  Each entry:
#   target  - short label shown on the index card
#   goals   - optional numeric milestones when explanatory numbers in target
#             (such as a boostable quest check) are not training goals
#   done    - already 99
#   phase   - where it sits in the plan
#   pick    - the method chosen in the plan (name must match a methods row to
#             flag it, or be None if the plan left it open)
#   summary - one line for the index card
#   notes   - list of paragraphs / bullets under "Notes"
#   methods - (name, level req, approx xp/hr, notes)
# --------------------------------------------------------------------------

COMBAT = "Combat"
GATHER = "Gathering"
ARTISAN = "Artisan"
SUPPORT = "Support"

SKILLS = [
    # ---------------- combat ----------------
    dict(
        name="Attack", group=COMBAT, target="80 → 99", pick="Slayer tasks",
        phase="75 after Strength 75, then 80 after Strength 80; finish 99 in the combat block after the Diary Cape.",
        summary="Follow Strength to 75, then repeat that order for level 80.",
        methods=[
            ("Slayer tasks", "—", "30–60k", "Your default. XP depends entirely on the task and gear; Duradel tasks with a good weapon are the top end."),
            ("Hallowfell on maniacal monkeys", "75 Attack, MM2", "200–300k",
             "The fastest melee XP in the game since Wyrmscraig. Hallowfell hits two extra monkeys for half damage; 200k+ with stacking and halberd specs, still well over 150k on auto-retaliate with a bonecrusher necklace keeping Piety up."),
            ("Sulphur Nagua", "55 Attack, Perilous Moons", "75–130k", "Negative armour plus double-hit weapons. About 75k with Strength in the low 60s, up to 130k at 75 with full blood moon and Piety. The bridge from here to Hallowfell."),
            ("Nightmare Zone", "Quest reqs", "100k", "Absorptions and a rock cake in a normal rumble: 20 minutes between clicks, about 100k with decent gear. Also prints the points for imbues."),
            ("Gemstone Crab", "1", "30–60k",
             "Shared-health crab in Varlamore. Ten minutes per burrow, two clicks to re-engage. The idle option when you cannot get to NMZ."),
            ("Scurrius", "40 Prayer", "70–100k", "The rat boss under Varrock. Faster than the crab at 55–75 with a bone mace, but it takes actual attention."),
            ("Ammonite / sand crabs", "—", "20–40k", "Free, safe, extremely AFK. Fine for early levels, poor once you have Slayer flowing."),
            ("Bossing", "Varies", "40–80k", "Vorkath, Muspah, ToA. Slower than pure XP methods but pays for the rest of the account."),
        ],
        notes=[
            "Strength leads each milestone because max hits improve later training. Bring Attack to 75 after Strength 75, then bring it to 80 after Strength 80 so accuracy and weapon unlocks do not fall far behind.",
            "Attack 75 now matters for its own sake: it wields Hallowfell, the Mad Angel drop that turns maniacal monkeys into 200k+ melee XP an hour. Fallen From Grace unlocks the boss.",
            "Train Attack on Slayer rather than stopping the quest route for a separate combat grind. Use an abyssal whip with a dragon defender for general Attack training until Hallowfell.",
        ],
    ),
    dict(
        name="Strength", group=COMBAT, target="80 → 85 → 99", pick="Slayer tasks",
        phase="75 first, then Attack and Defence to 75; lead the level-80 pass the same way, then resume toward ~85 after balanced 80s.",
        summary="Lead each balanced pass with Strength; return for 85 after balanced 80s.",
        methods=[
            ("Slayer tasks", "—", "30–60k", "Your default. Use Aggressive for dedicated Strength XP on tasks where the melee kill is fastest."),
            ("Hallowfell on maniacal monkeys", "75 Attack, MM2", "200–300k",
             "The fastest melee XP there is. Bring super strength rather than super combat; the monkeys have no defence to speak of. Low-intensity on auto-retaliate still beats everything below."),
            ("Sulphur Nagua", "55 Attack, Perilous Moons", "75–130k", "Strong low-effort rates; moonlight potions made on site cover prayer and boosts."),
            ("Nightmare Zone", "Quest reqs", "100k", "The AFK 99 Strength. Absorptions, rock cake, 20 minutes a click; about 100k with an obsidian set or better."),
            ("Scurrius", "40 Prayer", "70–100k",
             "The rat boss under Varrock. Solid XP for the level band, and bones plus the spine for the Prayer stockpile."),
            ("Gemstone Crab", "1", "30–60k", "Shared-health crab in Varlamore. The modern replacement for sand crabs when you want to do nothing."),
            ("Barbarian Fishing", "—", "passive", "Leaping fish give a trickle of Strength and Agility while you train Fishing."),
            ("Ammonite / sand crabs", "—", "20–40k", "Free and AFK; overtaken by anything else once you have gear."),
        ],
        notes=[
            "Train Strength to 75 before bringing Attack and Defence to 75, then repeat the order to 80. Five-level milestones capture most of the Strength-first damage advantage without leaving the other stats behind.",
            "For general Strength training, use an abyssal dagger with a dragon defender. A Saradomin sword is the cheap option; an abyssal bludgeon is only a small upgrade for its price. Save the abyssal whip for Attack or Defence because it cannot train Strength directly.",
            "Once Attack is 75, Hallowfell replaces all of that: one two-handed sword, one spot, and the best rate in the skill.",
        ],
    ),
    dict(
        name="Defence", group=COMBAT, target="80 → 99", pick="Slayer tasks",
        phase="The quest-cape minimum and level-70 armour breakpoint are already met. Train to 75 after Strength and Attack, then finish the balanced level-80 pass the same way.",
        summary="Finish each balanced melee pass with Defence.",
        methods=[
            ("Slayer tasks", "—", "30–60k", "Defensive or Controlled style on tasks you would be doing anyway."),
            ("Hallowfell on maniacal monkeys", "75 Attack, MM2", "200–300k", "Defensive style at the monkeys. The wiki notes long-fuse chins and defensive Ancients edge it at the very top; for a single grind this is simpler."),
            ("Sulphur Nagua", "55 Attack, Perilous Moons", "75–130k", "Same as melee. Just swap to Defensive."),
            ("Nightmare Zone", "Quest reqs", "100k", "Defensive style; the standard AFK route."),
            ("Gemstone Crab", "1", "30–60k",
             "Shared-health crab in Varlamore. Defensive style, near-zero attention."),
            ("Bossing", "Varies", "30–60k", "Defensive style on long boss trips."),
        ],
        notes=[
            "Defence 70 already unlocks most of the armour that matters (Bandos, Barrows, Karil's), so Defence stays last at both the level-75 and level-80 milestones.",
            "This account should reach combat 100 around Defence 76 after Strength and Attack 80. Switch from Nieve to Duradel then, and finish Defence 80 on the better task list.",
        ],
    ),
    dict(
        name="Hitpoints", group=COMBAT, target="99 (passive)", pick=None,
        phase="Arrives on its own. Listed in the post-Diary combat block but rarely needs dedicated training.",
        summary="Passive from all combat XP.",
        methods=[
            ("Any combat", "—", "≈ 1/3 of combat XP", "Every point of melee/ranged/magic damage gives Hitpoints XP alongside it."),
            ("Nightmare Zone (all styles)", "Quest reqs", "—", "If Hitpoints ends up lagging, NMZ is the usual catch-up."),
            ("Tempoross / Wintertodt", "—", "small", "Minor Hitpoints XP as a side effect."),
        ],
        notes=[
            "If you follow the plan (Slayer as default, then combat 99s), Hitpoints will likely hit 99 before or around the same time as your last combat stat.",
        ],
    ),
    dict(
        name="Ranged", group=COMBAT, target="62 → 70 → 99", pick="Cannon on Slayer tasks",
        phase="62 is the quest-cape requirement. Let cannoned Slayer tasks carry it there, continue to 70 as an early combat breakpoint, then finish 99 after the Diary Cape.",
        summary="Cannon on Slayer tasks; chins or a Venator bow later.",
        methods=[
            ("Cannon on Slayer tasks", "—", "passive", "Your pick. Cannon the multi-friendly tasks (dust devils, jellies, nechryael, greater demons) and it trains Ranged while the task still counts. The wiki puts 99 Slayer at 2–4M Ranged XP from the cannon alone."),
            ("Red chinchompas on maniacal monkeys", "45 (MM2)", "400–600k", "The fastest Ranged in the game. Solo with active stacking is roughly 450k at 70 and 600k by 85; the wiki's 670–840k figures assume two dancing alts. Costs a few million an hour."),
            ("Black chinchompas on maniacal monkeys", "65 (MM2)", "550–800k", "Same spot, bigger hits. Solo rates sit around 650k at 85. The chins are the expensive part."),
            ("Venator bow on maniacal monkeys", "80", "140–230k", "The cheap camp. Amethyst arrows, prayer potion drops, endless monkeys; the wiki calls 240k a realistic ceiling near 99. Far less involved than chinning."),
            ("Nightmare Zone", "Quest reqs", "70–150k", "Normal rumble with absorptions: 20 minutes AFK. Venator bow 145–150k, blowpipe 90–95k, magic shortbow (i) about 70k."),
            ("Pest Control", "70 combat", "80–150k",
             "Veteran boat plus combat-achievement point bonuses. The table runs 77k at 70 to 157k at 98 with hard CAs. Free, low intensity, team-dependent."),
            ("Gemstone Crab", "1", "30–60k",
             "Shared-health crab in Varlamore. Nearly zero attention, scales with your gear, and ruby bolts (e) carry it at 46–65."),
            ("Vorkath / bossing", "Quest reqs", "60–100k", "Decent XP plus serious GP; a good way to fund chinning."),
        ],
        notes=[
            "The cannon is the right early call: it also speeds up Slayer tasks while your Ranged is too low for chinning to be efficient.",
            "Bank chins as you get them from Hunter. They feed straight into the 99 Ranged grind.",
            "Chinning at 300k+ costs real money; the Venator bow at 200k is what to fall back on once the wallet argues.",
        ],
    ),
    dict(
        name="Magic", group=COMBAT, target="75 → 99", pick="Bursting/barraging Slayer tasks",
        phase="75 for the quest cape block; 99 in the combat block after the Diary Cape.",
        summary="Burst/barrage Slayer tasks.",
        methods=[
            ("Bursting/barraging Slayer tasks", "Desert Treasure I", "100–250k", "Your pick. Nechryael and dust devils in the Catacombs, smoke devils, jellies. Best XP-plus-Slayer combination in the game, but rune-hungry."),
            ("Bursting maniacal monkeys", "MM2, 70 Magic", "250–400k",
             "The fastest viable Magic in real time. Ice Burst is about 310k active and 250k on auto-retaliate; Ice Barrage 400k and 320k. The same spot as chinning."),
            ("Bandit Camp lodge, blood spells", "68 (Zamorak item)", "150–230k", "Stand two tiles inside the Big Heist Lodge door and every bandit comes to you. Blood Burst 150k, Blood Barrage 230k, life leech keeps you alive: the 20-minute AFK Magic method. Costs the runes with no drops back."),
            ("Cure Me at the Araxytes", "71 (Lunars)", "~414k", "Click once a tick while venomed spiders keep you cursed. The fastest raw number in the skill and the most exhausting; roughly 29 hours to 99 if you can keep it up."),
            ("High Alchemy", "55", "65k", "Up to roughly 78k XP per hour standing still; 20–50k while doing something else. The classic buyable Magic method."),
            ("Stun-alching", "80", "184–256k", "Stun plus High Alch, optionally with an Ardougne teleport in the rotation. Fast, fully click-bound and expensive."),
            ("Tele-alch", "55", "~145k",
             "Alternate a teleport with High Alchemy for a faster loop than alching alone. Camelot is the cheap version."),
            ("Plank Make", "86 (Dream Mentor)", "90–180k", "Auto-cast on mahogany logs for 90k and a quiet profit, or cast manually for 166k. About 90 seconds per inventory when idle."),
            ("Splashing", "—", "10–30k", "Near-zero attention, near-zero rate. Only worth it if you genuinely cannot play actively."),
            ("Guardians of the Rift", "27 RC", "moderate", "Side Magic XP while training Runecraft."),
            ("Superheat / Enchant bolts", "43+", "varies", "Doubles up with Smithing / Crafting when you're doing those anyway."),
        ],
        notes=[
            "Barrage tasks are the single best overlap in your plan. Magic XP, Slayer XP and Slayer points from the same hour.",
            "Budget for runes. If the cost gets uncomfortable, fall back to trident tasks and take Magic to 99 later in the combat block.",
            "The wiki's advice for Slayer is to reach 82 passively (alchs, Bake Pie, Plank Make) and boost to 94 with a saturated heart so barrage tasks start earlier.",
        ],
    ),
    dict(
        name="Prayer", group=COMBAT, target="82–85 → 99", pick=None,
        phase="82–85 as an early quality-of-life target (Rigour/Augury tier prayers and Piety), 99 in the post-Diary combat block.",
        summary="Gilded altar bones; ensouled heads as an alternative.",
        methods=[
            ("Gilded altar – dragon bones", "Construction 75", "~640k", "The standard. Two burners lit = 350% XP; use each bone on the altar by hand for 2,550 bones an hour. Use a friend's house or the POH portal hubs."),
            ("Gilded altar – superior dragon bones", "Construction 75", "~1.3M", "Fastest sane method; roughly double the cost of dragon bones."),
            ("Blessed bone shards", "30", "0.9–1.4M",
             "Libation bowl at the Teomat. About 1.05M between levels 62 and 86 with blessed wine, 1.3M+ with sunfire wine at 88+, and the shards give more XP per bone than any altar. Making your own shards roughly halves the rate."),
            ("Wilderness Chaos altar", "—", "500k–1.8M", "Same 350% multiplier with no house needed and a 50% chance not to consume the bone. 500k with dragon bones if you suicide each inventory, 860k bringing noted bones. PKer risk is real; bring nothing you mind losing."),
            ("Ensouled heads", "Arceuus spellbook", "~340k", "Reanimate and kill near the Dark Altar. 220 heads an hour with good stats; slower than the altars but cheap and no Wilderness."),
            ("Cremating urium remains", "Shades of Mort'ton", "35–57k",
             "Slow, but the fastest way to the zealot's robes, which save 5% of every bone you ever offer."),
            ("Bonecrusher and ash sanctifier", "Passive", "passive", "Half the bone or ash XP (full with the elite diaries) from everything you kill, for no clicks. Around 40k an hour at the monkeys."),
            ("Ectofuntus", "—", "~50k", "Cheapest XP per GP in the game, and painfully slow."),
        ],
        notes=[
            "Your plan didn't fix a method here. Chaos altar is the cost-efficient pick; gilded altar is the safe pick. Both are fine, and the libation bowl now sits between them on cost with better XP per bone.",
            "Prayer is a pure buyable. Don't spend early hours on it. Bank bones from Slayer and burn them in one go.",
        ],
    ),
    dict(
        name="Slayer", group=COMBAT, target="74 → 95 → 99", pick="Duradel",
        pick_note="Start on Nieve/Steve, use Konar when you want milestone points, and move to Duradel once you have 100 combat, 50 Slayer and Shilo Village. Combat 100 unlocks Duradel; it is not a Quest Cape requirement.",
        phase="74 for The Blood Moon Rises and the quest cape, 95 before the Diary Cape, then 99 first in the post-Diary maxing order.",
        summary="The spine of the whole plan.",
        methods=[
            ("Nieve / Steve", "85 combat", "—", "Your starting master. Good task variety, reachable now. Level 99 Slayer bypasses the combat requirement."),
            ("Konar quo Maten", "75 combat", "—", "Location-locked tasks. Worth using for milestone points and for Hydra access later."),
            ("Duradel", "100 combat, 50 Slayer", "—", "Your main master after Shilo Village once you have 100 combat and 50 Slayer; 99 Slayer bypasses those two levels. Generally best for fast Slayer XP, though task weighting still matters."),
            ("Mortimer", "70 Slayer, 100 combat", "—", "Unlocked partway through Fallen From Grace; 99 Slayer bypasses the combat requirement. Choose from two superior-capable tasks, or three after 50 Mortimer tasks. He is built for superior drops and choice, not cheap skipping."),
            ("Krystilia (Wilderness)", "—", "—", "Wilderness-only tasks. Fast points and good drops, but risky. Optional."),
            ("Turael/Spria skipping", "—", "—", "Turael-skip trick to reroll bad tasks without spending points. Useful when point-starved."),
        ],
        notes=[
            "Block list is the highest-leverage decision in this plan. Block the tasks that are slow and unprofitable for your gear (typically the low-XP-per-hour, high-count ones) rather than the merely boring ones.",
            "Extend the tasks you'll want to farm later (nechryael, abyssal demons, gargoyles) once points allow.",
            "Superior Slayer monsters (unlocked by Bigger and Badder) are worth the point cost. They can drop the imbued heart and eternal gem.",
            "The wiki's current top rates: smoke devils 150k barraged, nechryael and TzHaar 100k, araxytes 100k with a cannon and Venator bow, dagannoth 85k cannoned. Those are the tasks to extend.",
            "A Venator bow is the low-effort Slayer weapon: its ricochet pulls in the same stacks you would barrage, for less XP an hour and far fewer clicks.",
            "Fallen From Grace also unlocks the repeatable Mad Angel. Its Hallowfell drop needs 75 Attack and cleaves up to two nearby targets, so it is a specialised multi-target weapon rather than a universal single-target upgrade.",
            "Everything else in the plan is downstream of Slayer: it carries Attack, Strength, Defence and Hitpoints; via cannon and barrage, it also carries Ranged and Magic.",
            "The Along the Way table uses a neutral average split across melee styles. In play, train Strength to 75, Attack to 75 and Defence to 75; repeat that order to 80, then return to Strength 85. Controlled hasta training is the convenient alternative, especially on stab-weak tasks.",
            "The task verdict table uses Duradel's weights. Nieve has different weights and extra assignments, and block lists do not carry between masters; revisit blocks when you switch.",
        ],
    ),
    # ---------------- gathering ----------------
    dict(
        name="Fishing", group=GATHER, target="60 → 99 (62 quest step boostable)", goals=[60, 99], pick="Tempoross",
        phase="The quest-cape minimum is 60 unboosted, with 62 needed only for a boostable step; both are already in range. Train it later in the slow-skills block.",
        summary="Quest requirement met; drift nets or Tempoross, harpoons if you want speed.",
        methods=[
            ("Drift Net Fishing", "47 Fish / 44 Hunt", "53–88k Fishing", "Trains Fishing and Hunter at once on Fossil Island: about 70k Fishing and 95k Hunter from your levels, 88k and 117k once both are 70. The best-value method in the skill when Hunter still needs training, which here it does."),
            ("Barbarian Fishing", "48 (+ quest)", "23–57k (55–108k with 3-ticking)", "3-tick cut-eat is the fastest thing below 71: 90k Fishing at 70, 97k at 80, plus Strength and Agility. Plain clicking is far slower."),
            ("2-tick harpooning", "71", "78–133k",
             "Swordfish and tuna at Piscarilius with tick manipulation. 91k at 71 with a dragon harpoon, 117k at 85 with a crystal one, 133k at 99. The genuine fastest Fishing and the most demanding."),
            ("Leechfin fishing", "78 (+ Blood Moon Rises)", "109–130k",
             "Vampyrium. Click every tick to angle the net; sits between barbarian 3-tick and 2-tick harpooning, and needs nothing but a big net."),
            ("Tempoross", "35", "62–102k", "62k at 70 on a mass world, 68k at 90; 77–95k with a crystal harpoon and 102k solo near 99. Free food and permits. Sociable, low risk."),
            ("Minnows", "82", "40–56k", "Converts to sharks for Tempoross-adjacent profit. Fairly click-heavy."),
            ("Karambwans", "65", "29–42k", "One click a minute with the fish barrel; feeds 1-tick Cooking later."),
            ("Monkfish", "62", "36–42k",
             "Piscatoris, or from a raft just north of the beach where the spot never moves: three to four minutes per inventory. Steady, and the fish are worth banking for Slayer trips."),
            ("Aerial fishing", "43 (+ 35 Hunter)", "35–50k",
             "Trains Fishing and Hunter together at Lake Molch, and pays in molch pearls."),
            ("Dark crabs", "85 (+ Wilderness)", "~40k",
             "The longest single stretch without clicking in the skill, at the cost of being in the deep Wilderness with a lobster pot."),
            ("Anglerfish", "82", "15–39k", "Slow but good money and the best non-boss food. From a boat off Piscarilius it is six to seven minutes per inventory; diabolic worms double the rate."),
        ],
        notes=[
            "Do not train Fishing to 70 just for the quest cape: 60 unboosted is enough and the level-62 step is boostable. Drift Net is the maxing overlap with Hunter, not a QPC gate.",
            "If you'd rather not tick-manipulate for hours, drift nets or Tempoross to 99 are slower but far more pleasant, and drift nets pay most of a Hunter 99 on the side.",
        ],
    ),
    dict(
        name="Hunter", group=GATHER, target="70 → 99", pick="Hunters' Rumours",
        phase="70 for the quest cape. Razor-backed kebbits are the shortest direct route from 65; Drift Net is the optional Fishing overlap.",
        summary="Kebbits to 72, then Hunters' Rumours.",
        methods=[
            ("Drift Net Fishing", "44 Hunt / 47 Fish", "60–117k Hunter", "Trains Hunter and Fishing together. About 95k Hunter from your levels, 117k at 70/70. Efficient when both skills matter, which they do here."),
            ("Hunters' Rumours", "72 / 91", "160–250k", "Varlamore contract system: 160k at 72, 195k at 91, 250k at 99 with a block list and back-to-back rumours. The modern default and the fastest safe Hunter there is."),
            ("Black chinchompas", "73", "145–225k", "Solo with tick manipulation and the odd PKer. Matches rumours at 90+ and pays better, but it is deep Wilderness and the rumours are safer for the same XP."),
            ("Red chinchompas", "63", "72–155k", "The Tlati Rainforest spot: 72k at 70 without tick manipulation, 115k at 80, 155k at 99, and it stockpiles the chins you'll want for 99 Ranged."),
            ("Razor-backed kebbits", "49", "~130k",
             "Deadfall trapping in the Piscatoris hunter area. The standard bridge from here to rumours at 72; no tick manipulation."),
            ("Maniacal monkey deadfalls", "60 (+ MM2)", "51–110k",
             "Ride a stunted gorilla and bait a boulder with bananas. One click every 25–30 seconds and a 50-minute trip on a basket of bananas: the AFK Hunter method. 59k at 65, 82k at 80, 110k at 99."),
            ("Herbiboar", "80 (+ 31 Herb)", "137–171k", "Low-effort tracking on Fossil Island that pays out herbs continuously. Requires Bone Voyage."),
            ("Goat hunting", "60 + Sheep Herder", "~192k with Tele Grab",
             "Herd Wyrmscraig goats into a spike pit with a cattle prod, Telekinetic Grab or Dark Lure. Fast but active; goat horns feed combat potions and the furs feed Golem Crafting."),
            ("Letvek and stymphikes", "76 / 82 (+ Blood Moon Rises)", "~145k",
             "Vampyrium. Box-trap letvek at 76 as bait, then hunt stymphikes at 82. With 3-tick manipulation this is among the fastest Hunter in the game."),
            ("Falconry", "43", "60–70k",
             "Spotted and dark kebbits at Piscatoris. No traps, just clicking, and it is the fastest option in its band."),
            ("Birdhouse runs", "5+", "passive", "Two minutes every 50 minutes. Free XP forever. Start doing these now regardless of method."),
        ],
        notes=[
            "Set birdhouse runs as a habit from today; over a max grind they are worth several levels for almost no time.",
            "Chinchompa hunting doubles as Ranged ammunition. It's the natural bridge between your Hunter and Ranged goals.",
            "Rumours beat every chinchompa method on XP at 91+, without the Wilderness. Hunt chins for the ammo, not the XP.",
        ],
    ),
    dict(
        name="Agility", group=GATHER, target="70 → 99", pick=None,
        phase="70 for the quest cape, then 99 in the slow-skills block.",
        summary="Rooftops, then Hallowed Sepulchre.",
        methods=[
            ("Hallowed Sepulchre", "52 (62/72/77/87)", "45–98k", "The main 99 route. 56k with floors 1–2, 69k with three, 80k with four, 98k with all five looting the grand coffin. Profitable."),
            ("Rooftop courses", "10–90", "20–70k", "Seers' 60 (50–56k), Pollnivneach 70 (53–58k), Rellekka 80 (59–63k), Ardougne 90 (66–70k). Marks of grace fund graceful."),
            ("Prifddinas rooftop", "75 (+ Song of the Elves)", "60–65k", "Highest rooftop rate below 90; also drops crystal shards."),
            ("Wilderness Agility Course", "47", "50–60k",
             "Faster than rooftops in its band, with the pile at the end and medium clues, but you are in the Wilderness."),
            ("Colossal Wyrm course", "50 (62 advanced)", "31–42k",
             "Six clicks per 60-second lap on the advanced route, with two 20-second stretches where you do nothing. The least demanding Agility, and it pays amylase and blessed bone shards."),
            ("Brimhaven Agility Arena", "20+", "36–50k", "Floor spikes on a single tile for 36k with almost no focus; 45–50k tagging pillars at 40+."),
            ("Rockslide shortcut", "78 (+ Blood Moon Rises)", "+3.5–4k", "550 XP every seven and a half minutes through the Vampyrium rockslide. Not a method, a habit to layer on anything else."),
        ],
        notes=[
            "Your plan doesn't name a method. Hallowed Sepulchre from level 62 onward is the standard and pays for itself.",
            "Agility is one of the true slow skills. The plan correctly puts 99 late. Do the 70 quest requirement, then leave it.",
            "Get full graceful early; the run-energy restore compounds across every other skill you train.",
        ],
    ),
    dict(
        name="Thieving", group=GATHER, target="72 → 99", pick=None,
        phase="72 for the quest cape. Slot the eventual 99 in with the faster skills.",
        summary="Stealing artefacts, then blackjacking or Pyramid Plunder.",
        methods=[
            ("Stealing artefacts", "49", "150–261k",
             "Port Piscarilius artefact runs with staminas and guard lures. 163k at 55, 197k at 70, 230k at 85, 261k at 99. Safe, steady, no tick manipulation, and it now beats blackjacking below 65."),
            ("Blackjacking", "The Feud, 45/65", "99–265k", "Menaphite thugs at 65: 230k at 65 rising to 265k at 99 with brews. The fastest Thieving until Rogues' Castle and the most tick-intensive."),
            ("Rogues' Castle chests", "84", "260–300k",
             "Deep Wilderness chests. The fastest Thieving from 84, and about 2.5M an hour in loot, if you accept the PKer risk."),
            ("Pyramid Plunder", "21 (91 for the rate)", "125–270k", "125k at 71–80, 190k at 81–90, 270k in the final room at 91+. Good artefact money and no tick manipulation."),
            ("Ardougne knights", "55 + Ardy medium", "86–240k", "Bank-adjacent, decent GP, and one trapped knight means zero mouse movement. 124k at 70, 182k at 85, 240k at 95."),
            ("Stealing valuables", "50", "72–105k",
             "Civitas illa Fortis house burglary: about one click a minute while the loot rolls in on its own. 80k at 60, 93k at 70, 100k at 90. The AFK Thieving method."),
            ("Vyres", "82 (Sins of the Father)", "120–180k", "Blood shards make it the best GP in the skill."),
            ("Master farmers", "38", "low", "Seed money rather than XP."),
        ],
        notes=[
            "Rogue's outfit (Rogues' Den) gives double loot and is worth grabbing before any long stint.",
            "Ardougne medium diary is the single biggest quality-of-life unlock here: knights become far more reliable.",
            "The quest cape needs 72, which stealing artefacts reaches comfortably without tick manipulation.",
        ],
    ),
    dict(
        name="Mining", group=GATHER, target="99 (slow-skills block)", pick=None,
        phase="Slow-skills block, after Runecraft and Agility.",
        summary="Volcanic Mine, or granite if you can 3-tick.",
        methods=[
            ("Motherlode Mine", "30", "30–62k", "The AFK standard. Prospector kit, upper level at 72, pay-dirt sack upgrades. About 62k at 90 with everything unlocked."),
            ("Shooting Stars", "10 (60+ useful)", "24–31k",
             "Crashed stars, a Distraction and Diversion. One click every 7 minutes, so it is the most AFK Mining there is, and stardust buys the celestial ring (+4 invisible Mining boost). Star tier scales with your level."),
            ("Volcanic Mine", "70 (+ Bone Voyage)", "68–94k", "68k at 70 with a dragon pickaxe, 84k at 99, 94k with a crystal one. The fastest Mining without tick manipulation, in a 3–5 player team."),
            ("3-tick iron / granite", "15 / 45", "87–126k", "Granite at the Quarry: 109k at 75, 114k at 85, 126k at 99 with a celestial ring and Varrock 4. The top rate if you're willing to tick-manipulate."),
            ("Blast Mine", "75", "65–101k", "65–76k at 75, 87–101k at 99. Solo, profitable, high click intensity."),
            ("Rubium rocks", "48 Mining, 60 Sailing", "39–64k",
             "Charred Dungeon, reached by docking at Charred Island. Low attention, stackable splinters and a profit; the deposits at 68 are the AFK version."),
            ("Calcified rocks", "41 (+ Perilous Moons)", "25–50k",
             "Underwater at Fossil Island style, but Varlamore: low attention, no competition, and 15–18k Prayer XP an hour in bone shards on top."),
            ("Sunstone mining", "53 + Fallen From Grace", "verify",
             "Mine active rocks on Wyrmscraig to build momentum for extra ore and XP; level 80 guarantees the momentum successes. The sunstone feeds Golem Crafting."),
            ("Zalcano", "70 (+ Song of the Elves)", "varies",
             "Group skilling boss that pays in crystal shards. Rates depend on team and reward mode; the wiki no longer quotes a single figure."),
            ("Infernal shale", "78", "67–80k (tick)",
             "Chasm of Fire. Only worth it with Jim's wet cloth tick manipulation, and then the value is the crushed shale, not the XP."),
            ("Amethyst", "92", "~20k", "Very AFK and profitable; used mainly for the last stretch or while doing something else."),
        ],
        notes=[
            "Check whether Mining shows up in your remaining elite diary requirements before deciding how far to push it early.",
            "Golden nuggets buy the prospector kit and the sack upgrades. Buy those first; they permanently improve the rate.",
        ],
    ),
    dict(
        name="Woodcutting", group=GATHER, target="74 → 99", pick="Forestry teaks",
        phase="74 for the quest cape, then 99 in the slow-skills block.",
        summary="Tick-manipulated teaks, or bloodwood if you would rather not.",
        methods=[
            ("Forestry teaks", "35", "150–235k", "Your pick. 1.5-tick teaks are 194k at 71, 208k at 80, 235k at 99 with a crystal felling axe; 2-tick is about 10% behind. Without tick manipulation the same trees are 74–93k, so this pick is the manipulation, not the tree."),
            ("Bloodwood trees", "77 (+ Blood Moon Rises)", "130–210k",
             "Vampyrium. Three trees at a time with a felling axe, filling buckets of sap rather than cutting logs. The fastest Woodcutting without tick manipulation; the engorged tree nearby is a 70k low-click version."),
            ("Sulliuscep", "65 (+ Fossil Island)", "83–105k", "86k at 71, 95k at 80, 105k at 99 with a crystal axe. Low effort, no tick manipulation, drops fossils for the museum."),
            ("Ironwood / rosewood trees", "80 (72 Sailing) / 92 (79 Sailing)", "80–110k / 85–90k",
             "Ironwood on Sunbleak island is 80–110k; rosewood on Drumstick Isle stands for four and a half minutes per tree, the most idle tree in the game, and its logs build the rosewood hull."),
            ("Blisterwood tree", "62 (+ Sins of the Father)", "69–86k",
             "Never depletes, a sound cue when you stop, and Darkmeyer's bank next door. 69k to 90, 86k with a crystal felling axe and rations. The AFK tree you can use today."),
            ("Redwoods", "90", "55–75k", "The classic AFK 99. 65k with a dragon axe, 70–75k with crystal, almost no attention."),
            ("Forestry events", "—", "80–90k", "Yews plus every event that spawns; the anima-infused bark buys the outfit and rations."),
            ("Woodcutting Guild", "60", "—", "Invisible +7 boost and a bank; use it wherever it applies."),
        ],
        notes=[
            "Teaks are correct if you tick-manipulate. If you will not, bloodwood at 77 is the honest second: double the rate of anything else that only asks for normal clicking.",
            "If 2-ticking wears you out, alternate with Sulliuscep trips or the blisterwood tree.",
        ],
    ),
    dict(
        name="Runecraft", group=GATHER, target="60 → 77 → 99", pick="Guardians of the Rift",
        pick_note="ZMI with daeyalt essence is the named alternative once Lunar Diplomacy and Sins of the Father are done; it is faster than the minigame and still relaxed.",
        phase="60 for the quest cape, ~77 relatively early for blood runes, then 99 first in the slow-skills block.",
        summary="GOTR, then ZMI or lavas; blood runes for income.",
        methods=[
            ("Guardians of the Rift", "27", "25–70k", "Your pick. 40k at 50–75, 50k to 85, 65k to 98 in coordinated teams. The rewards include pouches, the Abyssal needle, Raiments of the Eye and eventually the pet. The robes give up to 60% more runes but no bonus XP."),
            ("ZMI altar", "50 (+ Lunar Diplomacy)", "42–60k (63–90k daeyalt)", "Consistent, solo, no minigame timer, and a random rune assortment that pays. Daeyalt essence is a flat 50% more XP: about 85k at 75+."),
            ("Lava runes (binding necklace)", "23", "56–102k", "Fire altar via the Abyss. 66k at 50, 80k at 75, 100k at 85 with Magic Imbue and a colossal pouch; a little less with talismans. The fastest solo Runecraft below 90."),
            ("Aether runes", "90", "99–102k",
             "The Aether altar with a colossal pouch. Same speed as lavas at the top end, and the runes are worth a great deal more."),
            ("Blood runes (Arceuus)", "77", "~36k", "Low attention, strong profit, and passive Mining and Crafting. This is why the plan wants 77 early: it turns Runecraft into income."),
            ("Soul runes (Arceuus)", "90", "~44k", "Same loop as blood runes, a little more XP, still profitable and idle."),
            ("Lava runes with runners", "23", "160–320k",
             "Duo 162k, four runners 280k. Only if you are paying people; the wiki prices a runner at 12M an hour."),
            ("Mud runes", "23 (+ Lunars)", "60–100k",
             "Binding necklace runs like lavas but with the Magic Imbue spell instead of an earth talisman staff. Similar rate; take whichever is cheaper."),
            ("Wrath runes", "95", "~45k", "Best money at the very top end, and slow."),
            ("Daeyalt essence", "Sins of the Father", "+50%", "Straight multiplier on any essence-based method. Get it before long Runecraft sessions."),
        ],
        notes=[
            "Reaching 77 early is the highest-value part of this skill's plan: blood runes then run in the background for the rest of the account.",
            "The QPC step from 57 to 60 is only about an hour at GOTR and will not produce a full outfit. Raiments cost 1,350 pearls (roughly 180 games on average) and increase rune output, not XP; treat them as a long-term maxing/profit goal.",
            "Lunar Diplomacy is the gate on both fast solo options: Magic Imbue for lavas and the Ourania teleport for ZMI. It is in the quest route already.",
        ],
    ),
    dict(
        name="Farming", group=GATHER, target="99", done=True, pick=None,
        phase="Already complete. Excluded from the remaining max order.",
        summary="Done.",
        methods=[
            ("Tree / fruit tree runs", "—", "—", "The route that got you here; keep doing them for the herbs and hardwood."),
            ("Herb runs", "—", "—", "Still worth it. They feed Herblore, which is still on the list."),
        ],
        notes=[
            "Keep running herbs even though the skill is capped: Herblore is one of the last skills in your max order and it wants a stockpile.",
        ],
    ),
    dict(
        name="Sailing", group=GATHER, target="62 → 99", pick=None,
        phase="62 for Fallen From Grace and the quest cape, then last in the slow-skills block. Pandemonium must be completed before any Sailing XP is possible.",
        summary="62 for Wyrmscraig; Jubbly Jive, then Gwenith Glide or the Lunar Isle route.",
        methods=[
            ("Barracuda Trials", "30 / 55 / 72", "24–200k", "The fastest Sailing from 55 onwards. Tempor Tantrum at 30 is only 19–25k an hour; Jubbly Jive at 55 is 65–89k by rank, Gwenith Glide at 72 is 114–184k, and 200k+ at Marlin rank with a rosewood hull and a crystal extractor running."),
            ("Courier tasks", "1 (46+ useful)", "20–160k", "Cargo runs between ports. Summer Shore 46–55 gives ~20k, Rellekka 62 gives 66k and 99k once Etceteria is unlocked at 65, Prifddinas 70 gives 71–77k, and Lunar Isle round trips from 76 give 130–160k once you can hold five tasks at 84. Far less intense than trials."),
            ("Sea charting", "1", "~10k", "The starting method and the best XP before 30. One-off task rewards tracked in the captain's log, with bonuses for clearing a region. Charting everything needs 78 Sailing and unlocks horizon's lure, a permanent 2.5% Sailing XP boost."),
            ("Bounty tasks", "30", "middle", "Kill an assigned sea monster for its bounty drop, structured like Hunter Rumours. The tasks were lengthened and rebalanced, so they are for the drops rather than the rate; at 80+ every task is available."),
            ("Shipwreck salvaging", "15 (42 better)", "8–110k", "Two hooks, a salvaging station and crewmates on a sloop. Jagex's own tests: 35–40k an hour at 97 with two crew on dragon hooks and you only sorting, 85k active while multitasking, 105–110k fully active with rune hooks. The idle option."),
            ("Deep sea trawling", "Fishing hybrid", "20–45k", "Trawling nets over fish shoals. 26k Sailing plus 43k Fishing at giant krill with cotton nets, 37–43k plus 57–60k at bluefin. Trains both, so it doubles up with your Fishing goal."),
            ("Crystal extractor", "73 (+ 67 Con)", "+10–15k", "Not a method, a passive top-up. 250 XP per harvest roughly every 63 seconds, stacking on top of whatever else you are doing. Build it as soon as you hit 73."),
            ("Wyrmscraig", "62", "12.5k quest XP",
             "Sail to the island after Pandemonium with 60 Crafting, 47 Runecraft and 53 Mining, then speak to Cormac in the middle of Auchrie village to start Fallen From Grace. It unlocks Mortimer during the quest, then the repeatable Mad Angel and Golem Crafting on completion."),
            ("Ocean encounters", "1", "passive", "Glows, strong winds and castaways while sailing. No requirement; trim your sails every time for the free XP."),
        ],
        notes=[
            "Pandemonium is mandatory before any training, and several quests give Sailing XP. From 50 the honest options to 55 are all slow: finish charting and courier tasks, then Jubbly Jive changes everything.",
            "The plan puts Sailing in the slow block, which fits: it is the newest skill and its rates are still being balanced. Re-check the wiki guide before the long grind.",
            "Two permanent multipliers are worth detouring for: horizon's lure from full charting (78 Sailing, 2.5% bonus to everything) and the crystal extractor at 73 Sailing plus 67 Construction.",
            "Boat speed is XP rate. A rosewood hull at 93 Sailing and 84 Construction is about 20% faster, which is roughly 15% more XP per hour on trials.",
            "If you want the least attention-heavy route, salvaging with crewmates and courier runs get there without any tick manipulation, but more slowly.",
            "Deep sea trawling overlaps with Fishing, so it is the natural pick on days you want both skills moving.",
            "The Sailing Skillcape now includes Teleport to Boat, provided the boat has a Greater Teleport Focus.",
        ],
    ),
    # ---------------- artisan ----------------
    dict(
        name="Smithing", group=ARTISAN, target="72 → 99", pick=None,
        phase="72 for the quest cape, then the buyables block at the end.",
        summary="Blast Furnace or Giants' Foundry.",
        methods=[
            ("Blast Furnace – gold bars", "40 (60 for best rate)", "~380k", "With goldsmith gauntlets, the fastest Smithing XP in the game: 380k, 410k with the cape. Loses GP; you're buying levels."),
            ("Giants' Foundry", "15", "165–253k", "Steel-mithril swords 165k at 50, mithril-adamant 198k at 70, adamant-rune 253k at 85. Good XP with no real loss, plus moulds and the Smiths' uniform. The best all-round option."),
            ("Anvil smithing (plates/darts)", "varies", "140–300k", "Adamant platebodies 200k at 68–88, rune 240k at 88+ and 300k with the uniform at the Prifddinas anvil. Costs unless you alch."),
            ("Cannonballs", "35", "14–28k", "Extremely AFK and profitable; 28k with the double ammo mould, four times that at the ancient furnace with 87 Sailing. Terrible XP rate. Only for background training."),
            ("Blast Furnace – other bars", "varies", "100–250k", "Runite bars at 85 are profitable rather than costly."),
            ("Rune items (3-bar)", "95", "~120k",
             "Profitable at the very top end, unlike gold bars."),
        ],
        notes=[
            "Buy the useful moulds before the Smiths' uniform. The full 15,000-reputation set cuts anvil actions from 5 ticks to 4 and averages about 20% more XP per hour inside the Foundry.",
            "The 63→72 quest-cape stretch is only about 520k XP, so it will not fund the full uniform after moulds. Giants' Foundry is still the cheapest sane route; finish the set during the later 99 grind.",
        ],
    ),
    dict(
        name="Crafting", group=ARTISAN, target="90 → 99", pick=None,
        phase="90 as an interim target, 99 in the buyables block.",
        summary="D'hide bodies or battlestaves; amethyst if you want it quiet.",
        methods=[
            ("Dragonhide bodies", "63/71/77/84", "315–435k", "Green 63 (315k), blue 71 (355k), red 77 (395k), black 84 (435k) at 1,685 bodies an hour with a needle and thread. Simple, scalable, moderately expensive."),
            ("Battlestaves", "54–66", "245–337k", "Water 54, earth 58, fire 62, air 66 (337k). Buy orbs, attach to staves. Often the cheapest GP per XP."),
            ("Gem cutting", "varies", "100–380k", "Dragonstones are 380k at 2,780 gems an hour; usually a loss. A jeweller's chisel adds another 10%."),
            ("Cutting amethyst", "83", "~165k", "One click per inventory and it cuts on its own. Small loss or small profit, and the only Crafting that deserves the word AFK."),
            ("Golem Crafting", "60 + Fallen From Grace", "100–180k+",
             "Mine sunstone, shape each side of a golem, then add a sunstone core and one Hunter fur. Lower intensity is about 100k Crafting XP/hr; better furs and active shaping push past 180k. The Jeweller's chisel reward improves semiprecious gem cutting and has a 10% chance to cut any gem twice."),
            ("Glassblowing / Superglass Make", "1 (77 Magic for the spell)", "90–153k", "Molten glass into lenses or light orbs, an inventory per click. 108–153k Crafting plus 47–66k Magic if you cast Superglass Make yourself."),
            ("Crafting drift nets", "26", "~60k",
             "Worth knowing because you will be running Drift Net Fishing anyway; make your own nets instead of buying them."),
        ],
        notes=[
            "Your plan sets 90 as an interim target. Check which elite diary or quest wants it and stop exactly there before moving on.",
            "Battlestaves vs d'hide is a pure GP question; price-check both before committing; they swap places regularly.",
        ],
    ),
    dict(
        name="Fletching", group=ARTISAN, target="99", done=True, pick=None,
        phase="Already complete. Excluded from the remaining max order.",
        summary="Done.",
        methods=[
            ("Darts", "—", "—", "The usual fastest route; presumably how you got here."),
            ("Broad bolts / bow stringing", "—", "—", "Cheaper alternatives."),
        ],
        notes=[
            "Nothing left to do. Broad bolts remain worth fletching for cannon-free Slayer tasks if you go that route.",
        ],
    ),
    dict(
        name="Construction", group=ARTISAN, target="80 → 83 → 99", pick=None,
        phase="The level-70 quest requirement is already met. Reach 80 for immediate questing conveniences, then 83 when you want to boost for the practical max-house upgrades.",
        summary="Mahogany Homes, then oak doors or the shipwrights' workbench.",
        methods=[
            ("Mahogany Homes", "20+", "185–280k", "Contracts. Expert tier at 70 is 185–210k, or 240–280k with the plank sack. By far the cheapest GP per XP, plus the carpenter's outfit and the sack itself."),
            ("Oak dungeon doors", "74", "~550k", "Ten oak planks a door, hold the build key down. The cheapest fast method and the least click-intensive traditional one."),
            ("Shipwrights' workbench", "1 (Deepfin Point)", "250–440k", "Hull parts at 77 are 437 XP each and about a thousand an hour, with up to 29 seconds of nothing per inventory. The planks are worth half their normal XP, but the parts resell, so it is cheap for the rate."),
            ("Mahogany tables", "52", "~900k", "Fast and very expensive; gnome benches at 77 push it to 1.1M."),
            ("Teak garden benches", "66", "500–700k", "Similar rate to mahogany tables, usually cheaper per XP."),
            ("Mounted mythical capes", "50 (+ Dragon Slayer II)", "~430k",
             "Teak-based and cheaper per XP than mahogany furniture, with a butler doing the running."),
            ("Oak larders", "33", "~500k", "Classic butler-based training; cheap planks, high clicks."),
        ],
        notes=[
            "At 77 Construction, build a portal nexus and spirit tree. Boost to 80 for a fairy ring, rejuvenation pool and achievement gallery/spellbook altars, or train to 80 to avoid repeated stew boosts.",
            "Level 83 is the famous practical max-house target: a crystal saw plus a +5 spicy-stew boost lets you reach the ornate pool, occult altar and ornate jewellery box requirements where the saw applies.",
            "Do Mahogany Homes for the outfit and plank sack before the long 99 grind, but do not delay questing solely to finish the set.",
            "Unlock the demon butler before any bulk-building session.",
        ],
    ),
    dict(
        name="Herblore", group=ARTISAN, target="99 (buyables block)", pick=None,
        phase="Buyables block, after Construction.",
        summary="Potions. Cheapest available tier.",
        methods=[
            ("Super restores", "63", "~356k", "The long mid-game staple; near break-even and 2,500 potions an hour."),
            ("Super combat potions", "90", "~325k", "The standard 99 finisher; you'll drink plenty anyway."),
            ("Brews", "78 / 81 / 85 / 89", "437–564k", "Zamorak 437k at 78, Saradomin 450k at 81, ancient 522k at 85, Armadyl 564k at 89. The fastest potions there are, at whatever the secondaries cost this week."),
            ("Stamina potions", "77", "~200k (467k 1-tick)", "Amylase from Marks of Grace makes these cheap, and the stackable secondary means tick manipulation doubles the rate."),
            ("Mastering Mixology", "60 (81 better)", "~105k",
             "The Aldarin minigame. Far more XP per herb than any potion and the only source of the alchemist's amulet, prescription goggles and potion storage."),
            ("Prayer potions", "38", "~219k", "Reliable, usually near break-even."),
            ("Cleaning herbs", "any", "up to ~300k", "Fast raw XP if you click each herb; auto-clean is a third of that and free of attention."),
            ("Extended super antifires", "98", "~450k", "Only relevant for the last level."),
        ],
        notes=[
            "Herblore is a pure buyable. The plan is right to leave it late. Bank every herb you get from Slayer, Herbiboar and farm runs in the meantime.",
            "Clean herbs and make unfinished potions during any AFK activity; it costs almost nothing to bank a stockpile over months.",
            "Prescription goggles save 10% of secondaries on most potions. Over a 99 that is real money; do enough Mixology to get them first.",
        ],
    ),
    dict(
        name="Cooking", group=ARTISAN, target="72 → 99", pick=None,
        phase="72 for the quest cape, then finish this fast buyable near the end.",
        summary="Wines or 1-tick karambwans.",
        methods=[
            ("Jugs of wine", "35 (68 to stop failing)", "470–490k", "A fast and cheap route to 99 Cooking. Fourteen wines an inventory, so it wants more attention than fish. Mind-numbing but short."),
            ("1-tick karambwans", "30", "740–950k", "740k at 70, 813k at 80, 883k at 90 at the Rogues' Den fire. The fastest Cooking method in the game by a wide margin, and it needs perfect tick timing."),
            ("Karambwans, one click per inventory", "30", "218–273k", "The same fish at the Hosidius kitchen without the tick timing: 218k at 70, 251k at 80, 263k at 90. Sixty-seven seconds per inventory of doing nothing."),
            ("Bake Pie", "10 (+ 65 Magic)", "~150k",
             "The Lunar spell. Trains Cooking and Magic at once, which is why it shows up in both guides."),
            ("Fish at Hosidius / Myths' Guild", "varies", "165–285k", "Range next to a bank; no burning at Hosidius. Sharks and anglerfish at 80+ are 275–285k."),
            ("Sharks / Anglerfish", "80/84", "—", "Cook what you catch if you fished it yourself."),
        ],
        notes=[
            "One of the fastest 99s remaining. Wines are the low-effort answer; karambwans if you want it over in a couple of days.",
        ],
    ),
    dict(
        name="Firemaking", group=ARTISAN, target="75 → 99", pick="Wintertodt",
        phase="75 for the quest cape block, then last in the grinds block.",
        summary="Wintertodt.",
        methods=[
            ("Wintertodt", "50", "160–320k", "Your effective pick. 226k at 70, 258k at 80, 290k at 90 on the fast official worlds. Profitable, sociable, gives the pyromancer outfit, herbs, seeds and gems. Almost everyone does 50–99 here."),
            ("Burning logs at a bank", "varies", "300–520k", "Yews 300k, magic logs 451k at 75, redwoods 520k at 90. Faster raw XP but pure GP loss and zero rewards."),
            ("Bonfires", "1+", "135–233k", "A forester's campfire next to a bank: add the whole inventory and walk away for 150 seconds. Maples 135k, magic 202k at 75, redwood 233k at 90 on automatic; 40% more if you feed it by hand."),
            ("Forestry bonfires", "—", "bonus", "Group bonfires during Forestry events add XP while you cut teaks."),
        ],
        notes=[
            "Wintertodt for the 75 requirement and then again for 99 is the obvious call; the supply drops effectively pay you to train.",
            "The full pyromancer outfit gives 2.5% bonus Firemaking XP, but its pieces are random. Collect what drops on the 70→75 stretch; do not assume the short QPC grind will complete the set.",
        ],
    ),
]

DIARY = dict(
    name="Diaries", group=SUPPORT, target="Hard → Elite", pick=None,
    phase="All Hard diaries after the Quest Cape; elite skill requirements cleared during the Slayer 74→95 stretch.",
    summary="Hard diaries, then elite skill walls.",
    methods=[
        ("Hard diaries", "—", "—", "Do these as a block after the Quest Cape. Most requirements will already be met by then."),
        ("Elite diaries", "—", "—", "The remaining walls are skill levels, not content. Clear them opportunistically while training Slayer to 95."),
    ],
    notes=[
        "Diary rewards compound: Ardougne cloak teleports, Karamja gloves for Slayer, Morytania legs for Barrows, Fremennik boots for run energy, Varrock armour for Mining.",
        "Track which elite diaries are blocked by a single skill. Those are the ones worth a short dedicated grind rather than waiting for them to arrive naturally.",
    ],
)

SKILLS.append(DIARY)

GROUP_ORDER = [COMBAT, GATHER, ARTISAN, SUPPORT]


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

# (video id, short title, channel name, channel handle, avatar file, extra url)
VIDEOS = [
    ("EgerHcjR0VI", "How to max in 2026", "Patyfatycake",
     "patyfatycake_OSRS", "ch-patyfatycake.jpg", "&t=934s"),
    ("LZRbhpS5J3c", "What order to max", "Local OSRS",
     "LocalOSRS", "ch-localosrs.jpg", ""),
    ("LqMvToAkWkQ", "Maxing in 2026", "Gissoia",
     "Gissoia", "ch-gissoia.jpg", ""),
    ("AI_d03Xj_LE", "Best AFK methods", "Gissoia",
     "Gissoia", "ch-gissoia.jpg", ""),
]


PLAN_LINKS = [
    ("progression", "Progression", "assets/media/site/combat-achievements.png"),
    ("quests", "Quests", "assets/media/site/quests.png"),
    ("diaries", "Diaries", "assets/icons/Diaries.png"),
    ("approach", "Slayer", "assets/icons/Slayer.png"),
    ("max-order", "Max Order", "assets/media/max-cape.png"),
    ("feeders", "Feeders", "assets/media/site/skills-icon.png"),
    ("gear.html", "Gear", "assets/media/site/gear-icon.png"),
    ("maxguide.html", "Time to Max", "assets/media/max-cape.png"),
]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def e(s):
    return html.escape(str(s))


# --------------------------------------------------------------------------
# Wiki media: skill icons, NPC/location/item thumbnails, inline mentions
# --------------------------------------------------------------------------

MANIFEST_PATH = os.path.join(OUT, "assets", "media", "manifest.json")
try:
    with open(MANIFEST_PATH, encoding="utf-8") as _f:
        MANIFEST = json.load(_f)
    if not isinstance(MANIFEST, dict):
        raise ValueError("media manifest must be an object")
except (OSError, ValueError):
    MANIFEST = {}
    print("warning: no valid assets/media/manifest.json, run fetch_media.py", file=sys.stderr)

SKILL_NAMES = {s["name"] for s in SKILLS if s["group"] != SUPPORT}

# alias -> (kind, path-fragment); skills use their pixel icon, everything else
# the downloaded wiki thumbnail
_ALIASES = {}
for _n in SKILL_NAMES:
    _ALIASES[_n] = ("skill", f"assets/icons/{_n}.png")
for _d in ("Diary", "Diaries", "diary", "diaries", "Achievement Diary",
           "Achievement Diaries"):
    _ALIASES[_d] = ("skill", "assets/icons/Diaries.png")
for _alias, _title in PROSE_ENTITIES.items():
    _file = MANIFEST.get(_title)
    if _file and _alias not in _ALIASES:
        _ALIASES[_alias] = ("wiki", f"assets/media/{_file}")

_ALIAS_RE = re.compile(
    r"(?<![\w'-])(" +
    "|".join(re.escape(a) for a in sorted(_ALIASES, key=len, reverse=True)) +
    r")(?![\w-])"
)


def media_path(title, depth=0):
    """Local path for a wiki page's downloaded image, or None."""
    f = MANIFEST.get(title)
    return f"{'../' if depth else ''}assets/media/{f}" if f else None


_REQ_NUM_FIRST = None
_REQ_NAME_FIRST = None


def _build_req_patterns():
    """'100 combat', '50 Slayer', 'Defence 70' — the shapes the plan writes
    requirements in."""
    global _REQ_NUM_FIRST, _REQ_NAME_FIRST
    names = "|".join(sorted(SKILL_NAMES, key=len, reverse=True))
    _REQ_NUM_FIRST = re.compile(r"\b(\d{1,3})\s+(combat|" + names + r")\b")
    _REQ_NAME_FIRST = re.compile(r"\b(" + names + r")\s+(\d{1,3})\b")


def _met(skill, level):
    if not STATS:
        return False
    if skill.lower() == "combat":
        return (STATS.get("combat") or 0) >= level
    st = stat_of(skill)
    return bool(st and st["level"] >= level)


def strike_met(text):
    """Cross out requirements the account already meets."""
    if not STATS:
        return text
    if _REQ_NUM_FIRST is None:
        _build_req_patterns()

    def num_first(m):
        lvl, skill = int(m.group(1)), m.group(2)
        if 2 <= lvl <= 126 and _met(skill, lvl):
            return f'<s class="metreq" title="done">{m.group(0)}</s>'
        return m.group(0)

    def name_first(m):
        skill, lvl = m.group(1), int(m.group(2))
        if 2 <= lvl <= 99 and _met(skill, lvl):
            return f'<s class="metreq" title="done">{m.group(0)}</s>'
        return m.group(0)

    return _REQ_NAME_FIRST.sub(name_first, _REQ_NUM_FIRST.sub(num_first, text))


def annotate(text, depth=0, skip=()):
    """Escape prose and give the first mention of a known skill, NPC, location
    or unlock its picture."""
    root = "../" if depth else ""
    esc = strike_met(html.escape(str(text), quote=False))

    def repl(m):
        word = m.group(1)
        if word in skip:
            return word
        kind, frag = _ALIASES[word]
        cls = "mi pixel" if kind == "skill" else "mi"
        return (f'<span class="ment"><img class="{cls}" src="{root}{frag}" '
                f'alt="" loading="lazy">{word}</span>')

    return _ALIAS_RE.sub(repl, esc)


# --------------------------------------------------------------------------
# Live stats (data/stats.json, written by fetch_stats.py)
# --------------------------------------------------------------------------

def load_object(path, default=None):
    """Read a JSON object, rejecting valid JSON with the wrong top-level type."""
    try:
        with open(path, encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else default
    except (OSError, ValueError):
        return default


QUESTS_PATH = os.path.join(OUT, "data", "quests.json")
QUESTS = load_object(QUESTS_PATH)
if QUESTS is not None and not isinstance(QUESTS.get("states"), dict):
    QUESTS = None

# The quest refresh snapshots the Wiki's current minimum-level table. Use it
# for the overview so a newly released quest cannot silently leave the block
# stale; the constants above remain the offline fallback for old snapshots.
if QUESTS and isinstance(QUESTS.get("requirements"), dict):
    _qpc = QUESTS["requirements"]
    _qpc_skills = _qpc.get("skills")
    if (isinstance(_qpc_skills, dict)
            and all(isinstance(_qpc_skills.get(n), int)
                    for n in QUEST_CAPE_REQUIREMENTS)
            and isinstance(_qpc.get("combat"), int)):
        QUEST_CAPE_REQUIREMENTS.update(_qpc_skills)
        QUEST_CAPE_COMBAT = _qpc["combat"]
        QUEST_CAPE_BOOSTABLE = _qpc.get("boostable") or QUEST_CAPE_BOOSTABLE
        PLAN_PHASES[0]["reqs"] = [
            (name, QUEST_CAPE_REQUIREMENTS[name]) for name in QUEST_CAPE_BLOCKERS
        ]
        PLAN_PHASES[0]["combat"] = QUEST_CAPE_COMBAT

DIARIES_PATH = os.path.join(OUT, "data", "diaries.json")
DIARIES = load_object(DIARIES_PATH)
if DIARIES is not None and not isinstance(DIARIES.get("regions"), list):
    DIARIES = None
if (QUESTS and DIARIES and QUESTS.get("fetched") and DIARIES.get("fetched")
        and QUESTS["fetched"] != DIARIES["fetched"]):
    print("warning: quest and diary snapshots are from different refreshes", file=sys.stderr)
    QUESTS = DIARIES = None

FOCUS_PATH = os.path.join(OUT, "data", "focus.json")
_focus_data = load_object(FOCUS_PATH, {})
FOCUS = _focus_data.get("skill") if isinstance(_focus_data.get("skill"), str) else None

PICKS_PATH = os.path.join(OUT, "data", "picks.json")
PICKS = load_object(PICKS_PATH, {})

for _s in SKILLS:
    _chosen = PICKS.get(_s["name"])
    if _chosen and any(m[0] == _chosen for m in _s["methods"]):
        _s["pick"] = _chosen
        _s.pop("pick_note", None)

STATS_PATH = os.path.join(OUT, "data", "stats.json")
STATS = load_object(STATS_PATH)
if STATS is not None and (not isinstance(STATS.get("skills"), dict)
                          or not isinstance(STATS.get("overall"), dict)):
    STATS = None

# Show every current QPC requirement the account has not met. This also makes a
# future quest requirement appear automatically after fetch_quests.py refreshes
# the Wiki table, even if that skill was not a blocker when this plan was made.
if STATS:
    _qpc_order = QUEST_CAPE_BLOCKERS + [
        name for name in QUEST_CAPE_REQUIREMENTS if name not in QUEST_CAPE_BLOCKERS
    ]
    PLAN_PHASES[0]["reqs"] = [
        (name, QUEST_CAPE_REQUIREMENTS[name]) for name in _qpc_order
        if ((STATS.get("skills", {}).get(name) or {}).get("level", 0)
            < QUEST_CAPE_REQUIREMENTS[name])
    ]


def stat_of(skill_name):
    if not STATS:
        return None
    return STATS.get("skills", {}).get(skill_name)


def milestones(skill):
    """Numeric training targets, excluding explanatory numbers when supplied."""
    if skill.get("goals"):
        return skill["goals"]
    return [int(n) for n in re.findall(r"\b(\d{1,2})\b", skill["target"])
            if 2 <= int(n) <= 99]


def progress(skill):
    """(current, next_target, percent_of_xp_to_next, done) or None without stats."""
    st = stat_of(skill["name"])
    if not st:
        return None
    cur = max(1, st.get("level") or 1)
    xp = max(0, st.get("xp") or 0)
    goals = milestones(skill)
    nxt = next((g for g in goals if g > cur), None)
    if nxt is None:
        return (cur, None, 100, True)
    prev_goal = max([g for g in goals if g <= cur] or [1])
    lo, hi = XP_TABLE.get(prev_goal, 0), xp_for_level(nxt)
    pct = 0 if hi <= lo else round(100 * (xp - lo) / (hi - lo))
    return (cur, nxt, max(0, min(100, pct)), False)


def level_badge(skill):
    """Rail level tag: current level once linked, otherwise the plan target."""
    pr = progress(skill)
    if not pr:
        return short_target(skill), skill.get("done", False)
    cur, nxt, _pct, done = pr
    return (str(cur), done)


# --------------------------------------------------------------------------
# Level colour scale: ember at low levels, amber through the middle, green at
# 99. Hue is interpolated on the level axis (not XP) because that is what the
# numbers on screen say. 99 lands exactly on the --done green.
# --------------------------------------------------------------------------

_HUE_STOPS = [(1, 12), (40, 28), (60, 44), (75, 62), (88, 96), (95, 120), (99, 142)]


def level_color(level):
    level = max(1, min(99, int(level or 1)))
    hue = _HUE_STOPS[-1][1]
    for (l0, h0), (l1, h1) in zip(_HUE_STOPS, _HUE_STOPS[1:]):
        if level <= l1:
            t = 0 if l1 == l0 else (level - l0) / (l1 - l0)
            hue = h0 + (h1 - h0) * t
            break
    sat = 70 + 8 * (level / 99)
    light = 58 + 7 * (level / 99)
    return f"hsl({hue:.0f} {sat:.0f}% {light:.0f}%)"


def level_style(level):
    return f' style="--lc:{level_color(level)}"'


def bar_colours(from_level, level):
    """Both ends of a progress bar, so the fill sweeps the level scale rather
    than sitting on one flat colour."""
    return f"--lc0:{level_color(from_level)};--lc:{level_color(level)}"


def short_target(skill):
    """Compact level tag for the right-hand index."""
    if skill.get("done"):
        return "99"
    t = skill["target"]
    return t.split(" ")[0].rstrip("→").strip()


_ICON_CACHE = {}


def icon_data(skill_name):
    """Skill icons are tiny pixel art, so they ride inline instead of costing a
    request each. The wiki thumbnails stay as files."""
    if skill_name not in _ICON_CACHE:
        path = os.path.join(OUT, "assets", "icons", f"{skill_name}.png")
        try:
            with open(path, "rb") as f:
                _ICON_CACHE[skill_name] = ("data:image/png;base64,"
                                           + base64.b64encode(f.read()).decode())
        except OSError:
            _ICON_CACHE[skill_name] = ""
    return _ICON_CACHE[skill_name]


def icon(skill_name, depth=0, cls=""):
    """OSRS skill icon, inlined from assets/icons."""
    src = icon_data(skill_name)
    if not src:
        root = "../" if depth else ""
        src = f"{root}assets/icons/{e(skill_name)}.png"
    c = f"icon {cls}".strip()
    return f'<img class="{c}" src="{src}" alt="" width="22" height="22">'


COMET_SVG = ('<svg class="comet" viewBox="0 0 16 16" width="14" height="14" '
             'aria-hidden="true">'
             '<circle cx="10.5" cy="5.5" r="3.2" fill="currentColor"/>'
             '<path d="M7.4 8.6 2 14M6.2 6.1 3.1 7M9.9 9.8 9 12.9" fill="none" '
             'stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'
             "</svg>")

# The sidebar sync control: a circular arrow that turns while the request is in
# flight. The ticked badge is hidden until a sync has actually landed.
SYNC_SVG = ('<svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">'
            '<path d="M12.3 4.2A5.2 5.2 0 1 0 13.2 7.3" fill="none" '
            'stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
            '<path d="M9.5 4.3h3.3V1" fill="none" stroke="currentColor" '
            'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
            '<g class="ccdone">'
            '<circle cx="11.5" cy="11.5" r="4.1" fill="currentColor"/>'
            '<path d="M9.7 11.6 11 12.9l2.3-2.7" fill="none" stroke="var(--bg)" '
            'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
            "</g></svg>")


WIKI = "https://oldschool.runescape.wiki/w/"
OQG_URL = WIKI + "Optimal_quest_guide"


def quest_panel():
    """Where you are in the optimal quest guide, and what is left."""
    if not QUESTS:
        return ('<div class="panel"><div class="k">Quest Cape</div>'
                '<h3>Not Linked Yet</h3><p>Run <code>fetch_quests.py</code> once the '
                'WikiSync plugin has uploaded your account. It reads quest completion '
                'from RuneLite, which the Hiscores do not carry.</p>'
                f'<p class="gap"><a class="btn ghost sm" href="{OQG_URL}" '
                'rel="noopener">Optimal quest guide</a></p></div>')

    done, total = QUESTS["done"], QUESTS["total"]
    pct = round(100 * done / total) if total else 0
    route = QUESTS.get("route") or []
    nxt_step = QUESTS.get("route_next") or {}
    rows = []
    n = 0
    for step in route:
        if step["state"] == 2 or step["state"] is None:
            continue
        n += 1
        is_next = step is not None and step.get("name") == nxt_step.get("name") \
            and step.get("tier") == nxt_step.get("tier")
        kind = step["kind"]
        label = e(step["name"]) + (f' &middot; {e(step["tier"])}'
                                   if step.get("tier") else "")
        wiki = urllib.parse.quote(str(step.get("wiki", "")), safe="/#")
        tag = ""
        if is_next:
            tag = '<span class="qtag">on deck</span>'
        elif kind == "diary":
            tag = (f'<span class="qtag wip">{step["done"]}/{step["total"]}</span>'
                   if step["done"] else '<span class="qtag dim">diary</span>')
        elif step["state"] == 1:
            tag = '<span class="qtag wip">started</span>'
        cls = " now" if is_next else (" wip" if step["state"] == 1 else "")
        rows.append(f'<li class="q{cls}"><span class="qn">{n}</span>'
                    f'<a href="{WIKI}{wiki}" rel="noopener" target="_blank">'
                    f'{label}</a>{tag}</li>')

    quest_left = max(0, total - done)
    nxt = (nxt_step.get("name", "") +
           (f' ({nxt_step["tier"]})' if nxt_step.get("tier") else ""))
    started = [s for s in route if s["state"] == 1]
    unreported = [str(name) for name in (QUESTS.get("unreported") or [])]
    source_note = (
        '<p class="qnow">WikiSync has not reported the newly released '
        + ", ".join(f"<b>{e(name)}</b>" for name in unreported)
        + ' yet; it is counted as outstanding with unknown completion state.</p>'
        if unreported else ""
    )

    release_panels = []
    released = QUESTS.get("quest_requirements") or {}
    states = QUESTS.get("states") or {}
    if isinstance(released, dict) and isinstance(states, dict):
        for name, details in released.items():
            if states.get(name) == 2 or not isinstance(details, dict):
                continue
            skills = details.get("skills") or {}
            chips = "".join(
                req_chip(skill, target)
                for skill, target in skills.items()
                if skill in SKILL_NAMES and isinstance(target, int)
            ) if isinstance(skills, dict) else ""
            prerequisites = details.get("quests") or []
            prerequisite_note = (
                "Requires " + ", ".join(
                    f"<b>{e(str(quest))}</b>" for quest in prerequisites
                    if isinstance(quest, str)
                ) + ". "
            ) if isinstance(prerequisites, list) and prerequisites else ""
            start = details.get("start")
            wiki = urllib.parse.quote(str(name).replace(" ", "_"), safe="/#")
            release_panels.append(
                '<div class="subpanel"><div class="k">New quest requirements</div>'
                f'<h3><a href="{WIKI}{wiki}" rel="noopener" target="_blank">'
                f'{e(str(name))}</a></h3><div class="reqgrid">{chips}</div>'
                f'<p class="qnow">{prerequisite_note}'
                f'{e(start) if isinstance(start, str) else ""}</p></div>'
            )
    release_note = "".join(release_panels)

    synced = str(QUESTS.get("synced") or "")[:10]
    next_wiki = urllib.parse.quote(str(nxt_step.get("wiki", "")), safe="/#")
    return (
        '<div class="questbox">'
        '<div class="qhead">'
        f'<div><div class="k">Quest Cape</div>'
        f'<div class="qcount"><b class="num">{done}</b>'
        f'<span>of {total} done</span></div></div>'
        f'<div class="qright"><b class="num">{quest_left}</b>'
        '<span>quests to go</span></div>'
        "</div>"
        f'<span class="prog wide"><span class="fill" style="width:{pct}%"></span></span>'
        + (f'<p class="qnow">Next in the guide: '
           f'<a href="{WIKI}{next_wiki}" rel="noopener" '
           f'target="_blank"><b>{e(nxt)}</b></a>'
           + (f' &middot; {len(started)} part-finished' if started else "")
           + "</p>" if nxt else
           '<p class="qnow">Every step in the guide is done.</p>')
        + source_note
        + release_note
        + f'<ol class="qlist">{"".join(rows)}</ol>'
        f'<div class="qfoot"><a href="{OQG_URL}" rel="noopener">Optimal quest guide</a>'
        f'<span>WikiSync: {e(QUESTS.get("name", ""))}'
        + (f", {synced}" if synced else "") + "</span></div>"
        "</div>"
    )


def diary_link(region):
    slug_map = {"Kourend & Kebos": "Kourend_%26_Kebos_Diary",
                "Lumbridge & Draynor": "Lumbridge_%26_Draynor_Diary",
                "Western Provinces": "Western_Provinces_Diary"}
    if region in slug_map:
        return WIKI + slug_map[region]
    return WIKI + urllib.parse.quote(region.replace(" ", "_")) + "_Diary"


def diary_panel():
    """Every diary tier by region, with the plan's two milestones on top."""
    if not DIARIES:
        return ('<div class="panel"><div class="k">Diaries</div>'
                '<h3>Not Linked Yet</h3><p>Run <code>fetch_quests.py</code>; the same '
                'WikiSync upload carries achievement diary progress.</p></div>')

    done, total = DIARIES["done"], DIARIES["total"]
    pct = round(100 * done / total) if total else 0
    tiers = DIARIES["tiers"]
    regions = DIARIES["regions"]
    n = DIARIES["region_count"]
    bt = DIARIES["by_tier"]

    head = []
    for row in regions:
        cells = []
        for tier in tiers:
            t = row["tiers"][tier]
            href = f'{diary_link(row["name"])}#{tier}'
            title = f'{row["name"]} {tier} diary on the wiki'
            if t["complete"]:
                inner = "done"
                cls = "done"
            elif t["done"]:
                inner = f'{t["done"]}<i>/{t["total"]}</i>'
                cls = "part"
            else:
                inner = f'0<i>/{t["total"]}</i>'
                cls = "none"
            cells.append(f'<td class="dt {cls}"><a href="{href}" rel="noopener" '
                         f'title="{e(title)}">{inner}</a></td>')
        head.append(f'<tr><td class="dr"><a href="{diary_link(row["name"])}" '
                    f'rel="noopener">{e(row["name"])}</a></td>{"".join(cells)}</tr>')

    synced = (DIARIES.get("synced") or "")[:10]
    return (
        '<div class="questbox">'
        '<div class="qhead">'
        f'<div><div class="k">Achievement Diaries</div>'
        f'<div class="qcount"><b class="num">{done}</b>'
        f'<span>of {total} tiers done</span></div></div>'
        f'<div class="qright"><b class="num">{total - done}</b><span>to go</span></div>'
        "</div>"
        f'<span class="prog wide"><span class="fill" style="width:{pct}%"></span></span>'
        '<div class="dmiles">'
        f'<a class="dmile" href="{WIKI}Achievement_Diary#Hard" rel="noopener" '
        f'target="_blank"><i>Phase 3</i><span>Hard</span>'
        f'<b>{bt["Hard"]}</b><em>/{n}</em></a>'
        f'<a class="dmile" href="{WIKI}Achievement_Diary#Elite" rel="noopener" '
        f'target="_blank"><i>Phase 5</i><span>Elite</span>'
        f'<b>{bt["Elite"]}</b><em>/{n}</em></a>'
        "</div>"
        '<div class="tablescroll"><table class="dtable"><thead><tr><th></th>'
        + "".join(f'<th><a href="{WIKI}Achievement_Diary#{t}" rel="noopener">{e(t)}</a></th>'
                  for t in tiers)
        + f'</tr></thead><tbody>{"".join(head)}</tbody></table></div>'
        f'<div class="qfoot"><span>Counts are tasks completed per tier</span>'
        f'<span>WikiSync: {e(DIARIES.get("name", ""))}'
        + (f", {synced}" if synced else "") + "</span></div>"
        "</div>"
    )


def mini_bar(pct, colour=None, from_level=1, level=None):
    style = f"width:{max(0, min(100, pct))}%"
    if colour:
        style += f";--lc:{colour}"
    elif level:
        style += ";" + bar_colours(from_level, level)
    return f'<span class="prog mini"><span class="fill lit" style="{style}"></span></span>'


def short_xp(xp):
    """1_240_000 -> 1.2M. Requirement rows have no room for full figures."""
    if xp >= 1_000_000:
        return f"{xp / 1_000_000:.1f}M".replace(".0M", "M")
    if xp >= 1_000:
        return f"{round(xp / 1_000)}k"
    return str(int(xp))


def final_goal(skill_name):
    """The last level the plan wants from a skill, read off its target label."""
    sk = next((x for x in SKILLS if x["name"] == skill_name), None)
    nums = re.findall(r"\d+", sk.get("target", "")) if sk else []
    return max(int(n) for n in nums) if nums else None


def req_gap(skill_name, target, xp_now):
    """XP left to this section's requirement, roughly how long that takes, and
    the gap to the skill's end goal. Rates are planning estimates."""
    left = max(0, xp_for_level(target) - (xp_now or 0))
    if not left:
        return ""
    rate = SKILL_RATE.get(skill_name, (0, ""))[0]
    parts = [f"{short_xp(left)} to {target}"]
    if rate:
        hours = left / rate
        parts.append("under 1h" if hours < 1 else f"~{round(hours)}h")
    end = final_goal(skill_name)
    if end and end > target:
        parts.append(f"{short_xp(max(0, xp_for_level(end) - (xp_now or 0)))} to {end}")
    return '<span class="rgap">' + " &middot; ".join(parts) + "</span>"


def req_chip(skill_name, target):
    """One skill requirement: links to the skill page, with a focus dot."""
    st = stat_of(skill_name)
    href = f"skills/{slug(skill_name)}.html"
    dot = (f'<button class="focusbtn" type="button" data-skill="{e(skill_name)}" '
           f'title="Set as the skill you are levelling" '
           f'aria-label="Focus {e(skill_name)}">{DOT_SVG}</button>')

    if not st:
        return (f'<span class="req-chip"><a class="rc" href="{href}">{icon(skill_name)}'
                f'<span class="rq">{e(skill_name)}</span>'
                f'<b class="rl">{target}</b></a>{dot}</span>')

    cur = st["level"]
    met = cur >= target
    hi = xp_for_level(target)
    pct = 100 if met else (round(100 * st["xp"] / hi) if hi else 0)
    focused = " focused" if skill_name == default_focus() else ""
    return (f'<span class="req-chip{" met" if met else ""}{focused}">'
            f'<a class="rc" href="{href}">{icon(skill_name)}'
            f'<span class="rq">{e(skill_name)}</span>'
            f'<b class="rl" style="--lc:{level_color(cur)}">{cur}</b>'
            f'<span class="rt">/{target}</span></a>{dot}'
            f'{"" if met else req_gap(skill_name, target, st["xp"])}'
            f'{chip_bar(pct)}</span>')


def chip_bar(pct):
    """A requirement bar is measuring progress to the target, not the level
    itself, so it colours by how close it is rather than by how high. Sitting
    on 77 of 78 should look nearly done, which the absolute scale reads as
    mid-orange. The sweep starts partway up so the fill is not mostly red."""
    at = max(1, min(99, round(1 + pct * 98 / 100)))
    return mini_bar(pct, colour=None, from_level=max(1, at - 30), level=at)


def combat_chip(target):
    cb = STATS.get("combat") if STATS else None
    if cb is None:
        return f'<span class="req-chip"><span class="rq">Combat</span><b class="rl">{target}</b></span>'
    met = cb >= target
    pct = round(100 * cb / target)
    return (f'<span class="req-chip{" met" if met else ""}">'
            f'<span class="rq">Combat</span>'
            f'<b class="rl" style="--lc:{level_color(min(99, cb))}">{cb}</b>'
            f'<span class="rt">/{target}</span>'
            f'{mini_bar(pct, level=min(99, cb))}</span>')


def phase_meter(kind):
    """The live counter under a phase title."""
    if kind == "quests" and QUESTS:
        done, total = QUESTS["done"], QUESTS["total"]
        nxt = QUESTS.get("next")
        pct = round(100 * done / total) if total else 0
        note = (f'<a href="#quests">next: {e(nxt)}</a>' if nxt else "complete")
        return (f'<div class="pmeter"><b>{done}</b><span>of {total} quests</span>'
                f'{mini_bar(pct)}<span class="pn">{note}</span></div>')

    if kind in ("diary_hard", "diary_elite") and DIARIES:
        tier = "Hard" if kind == "diary_hard" else "Elite"
        done = DIARIES["by_tier"][tier]
        total = DIARIES["region_count"]
        pct = round(100 * done / total) if total else 0
        return (f'<div class="pmeter"><b>{done}</b>'
                f'<span>of {total} {tier.lower()} diaries</span>{mini_bar(pct)}'
                f'<span class="pn"><a href="#diaries">breakdown</a></span></div>')

    if kind == "slayer":
        st = stat_of("Slayer")
        if not st:
            return ""
        cur, goal = st["level"], 95
        pct = 100 if cur >= goal else round(100 * st["xp"] / xp_for_level(goal))
        return (f'<div class="pmeter"><b style="--lc:{level_color(cur)}" class="lit">{cur}</b>'
                f'<span>of {goal} Slayer</span>{mini_bar(pct, level=cur)}</div>')

    return ""


def phase_tag(kind):
    """A count that belongs beside the title rather than under it."""
    if kind != "max" or not STATS:
        return ""
    skills_only = [x for x in SKILLS if x["group"] != SUPPORT]
    done = sum(1 for x in skills_only
               if (stat_of(x["name"]) or {}).get("level", 1) >= 99)
    return f'<span class="ptag">{done}/{len(skills_only)}</span>'


# Methods that hand out XP in more than one skill. Only genuine dual-XP
# methods belong here, not "it also gives you herbs".
TRAINS = {
    "Drift Net Fishing": ["Fishing", "Hunter"],
    "Aerial fishing": ["Fishing", "Hunter"],
    "Barbarian Fishing": ["Fishing", "Strength", "Agility"],
    "Deep sea trawling": ["Sailing", "Fishing"],
    "Bake Pie": ["Cooking", "Magic"],
    "Glassblowing / Superglass Make": ["Crafting", "Magic"],
    "Superheat / Enchant bolts": ["Magic", "Smithing"],
    "Guardians of the Rift": ["Runecraft", "Magic"],
    "Cannon on Slayer tasks": ["Slayer", "Ranged"],
    "Bursting/barraging Slayer tasks": ["Slayer", "Magic"],
    "Powered staff on Slayer": ["Slayer", "Magic"],
    "Zalcano": ["Mining", "Smithing"],
    "Blowpipe on crabs / Nagua": ["Ranged", "Hitpoints"],
    "Slayer tasks": ["Slayer", "Hitpoints"],
    "Sulphur Nagua": ["Strength", "Hitpoints"],
}


def skill_facts(sk):
    """Everything the focus card needs for one skill."""
    pr = progress(sk)
    st = stat_of(sk["name"])
    goals = milestones(sk)
    if pr:
        cur, nxt, pct, done = pr
        goal = nxt or 99
        togo = max(0, xp_for_level(goal) - (st["xp"] or 0))
    else:
        cur, pct, done = None, 0, False
        goal = goals[0] if goals else 99
        togo = None

    also = []
    for other in TRAINS.get(sk.get("pick") or "", []):
        if other == sk["name"]:
            continue
        od = next((x for x in SKILLS if x["name"] == other), None)
        if not od:
            continue
        ost = stat_of(other)
        opr = progress(od)
        also.append({
            "name": other,
            "icon": icon_data(other) or f"assets/icons/{other}.png",
            "href": f"skills/{slug(other)}.html",
            "level": (ost or {}).get("level"),
            "goal": (opr[1] if opr and opr[1] else 99),
            "pct": opr[2] if opr else 0,
            "colour": level_color((ost or {}).get("level") or 1),
        })

    return {
        "name": sk["name"],
        "also": also,
        "icon": icon_data(sk["name"]) or f'assets/icons/{sk["name"]}.png',
        "href": f'skills/{slug(sk["name"])}.html',
        "level": cur,
        "xp": (st or {}).get("xp"),
        "rank": (st or {}).get("rank"),
        "goal": goal,
        "pct": pct,
        "done": done,
        "togo": togo,
        "method": sk.get("pick") or "not chosen yet",
        "methodHref": (f'skills/{slug(sk["name"])}.html#m-{slug(sk["pick"])}'
                       if sk.get("pick") else f'skills/{slug(sk["name"])}.html#methods'),
        "colour": level_color(cur or 1),
        "summary": sk["summary"],
    }


def default_focus():
    if FOCUS and any(x["name"] == FOCUS for x in SKILLS):
        return FOCUS
    if STATS:
        live = [x for x in SKILLS if x["group"] != SUPPORT and stat_of(x["name"])]
        unfinished = [x for x in live if stat_of(x["name"])["level"] < 99]
        if unfinished:
            return min(unfinished, key=lambda x: stat_of(x["name"])["level"])["name"]
    return "Slayer"


def focus_data_script():
    data = {x["name"]: skill_facts(x) for x in SKILLS}
    return ("<script>window.FOCUSDATA=" + json.dumps(data, separators=(",", ":"))
            + ";window.FOCUSNOW=" + json.dumps(default_focus()) + ";</script>")


MAX_TOTAL = sum(1 for x in SKILLS if x["group"] != SUPPORT) * 99
MAX_COMBAT = 126
HISCORES_WORKER = "https://mudkip-hiscores.mudkip-max-cape.workers.dev/"


REFRESH_SVG = (
    '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">'
    '<path d="M13.6 8a5.6 5.6 0 1 1-1.7-4" fill="none" stroke="currentColor" '
    'stroke-width="1.7" stroke-linecap="round"/>'
    '<path d="M13.4 1.4v3h-3" fill="none" stroke="currentColor" '
    'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def snapshot_day(stamp):
    """The date a snapshot was taken, as the sidebar prints it. Source time,
    not build time: a rebuild does not make the numbers newer."""
    if not isinstance(stamp, str) or len(stamp) < 10:
        return "unknown"
    try:
        return datetime.date.fromisoformat(stamp[:10]).strftime("%-d %b %Y")
    except ValueError:
        return stamp[:10]


def rail_meter(coach=False):
    """Account line at the top of the site index, with the local-server sync
    and next-action controls when the page carries the coach script."""
    if STATS:
        rows = (f'<span class="mrow"><span>Total Level</span>'
                '<button class="refresh stat-refresh" id="statrefresh" type="button" '
                'title="Refresh gxexe from OSRS Hiscores" '
                'aria-label="Refresh gxexe from OSRS Hiscores">'
                f'{REFRESH_SVG}</button>'
                f'<b class="num" data-stat="total">{STATS.get("overall", {}).get("level")}</b>'
                f'<span class="mmax">/{MAX_TOTAL}</span></span>'
                f'<span class="mrow"><span>Combat</span>'
                f'<b class="num" data-stat="combat">{STATS.get("combat")}</b>'
                f'<span class="mmax">/{MAX_COMBAT}</span></span>'
                f'<span class="mrow snap" id="statsnap">{e(STATS.get("name") or "")}'
                f' · Hiscores {e(snapshot_day(STATS.get("fetched")))}</span>'
                '<span class="sr" id="statrefresh-status" role="status" '
                'aria-live="polite"></span>')
    else:
        rows = ('<span class="mrow"><span>Not linked</span></span>'
                '<span class="mrow hint"><code>fetch_stats.py "RSN"</code></span>')

    controls = (
        '<div class="cctl">'
        f'<button class="ccsync" id="sync-character" type="button" '
        f'title="Sync Hiscores, quests and diaries" '
        f'aria-label="Sync character">{SYNC_SVG}</button>'
        '<button class="ccask" id="ask-character" type="button" '
        'title="What should I do now?">WSID?</button>'
        "</div>"
    ) if coach else ""

    return f'  <div class="meter">{rows}{controls}</div>'


def rail(active=None, depth=0, coach=False):
    """Left-hand index: the account line on top, then every skill by group."""
    root = "../" if depth else ""
    p = ['<aside class="rail" aria-label="Site index">',
         rail_meter(coach=coach),
         '  <nav class="rail-body">',
         '  <div class="rail-kick">Reference</div>']
    for anchor, label, ico in PLAN_LINKS:
        mark = f'<img class="refico" src="{root}{ico}" alt="" width="15" height="15">'
        href = (f"{root}{anchor}" if anchor.endswith(".html")
                else f"{root}index.html#{anchor}")
        p.append(f'  <a href="{href}">{mark}'
                 f'<span class="t">{e(label)}</span></a>')

    p.append('  <div class="rail-kick">Links</div>')
    for label_, href in SITE_LINKS:
        p.append(f'  <a class="slink" href="{href}" target="_blank" rel="noopener">'
                 f'<span class="t">{e(label_)}</span>'
                 f'<span class="ext">&#8599;</span></a>')

    from hiscores import SKILL_ORDER

    ordered = [x for x in SKILLS if x["group"] == SUPPORT]          # diaries first
    for name in SKILL_ORDER:
        match = next((x for x in SKILLS if x["name"] == name), None)
        if match:
            ordered.append(match)
    ordered += [x for x in SKILLS if x not in ordered]

    p.append(f'  <div class="rail-kick"><img class="kickico" '
             f'src="{root}assets/media/site/skills-icon.png" alt="" width="13" height="13">'
             'Skills</div>')
    for sk in ordered:
        sl = slug(sk["name"])
        here = " here" if sl == active else ""
        tag, is_done = level_badge(sk)
        st = stat_of(sk["name"])
        style = level_style(st["level"]) if st else ""
        cls = " lit" if st else (" done" if is_done else "")
        focused = " focused" if sk["name"] == default_focus() else ""
        p.append(
            f'  <span class="rrow{focused}">'
            f'<a class="r{here}" href="{root}skills/{sl}.html">'
            f'{icon(sk["name"], depth, "sm")}'
            f'<span class="t">{e(sk["name"])}</span>'
            f'<span class="r-lvl{cls}" data-live-skill="{e(sk["name"])}"'
            f'{style}>{e(tag)}</span></a>'
            f'<button class="focusbtn" type="button" data-skill="{e(sk["name"])}" '
            f'title="Set as the skill you are levelling" '
            f'aria-label="Focus {e(sk["name"])}">{DOT_SVG}</button></span>'
        )

    p.append('  <div class="rail-kick spaced">Videos</div>')
    for vid, title, channel, handle, avatar, extra in VIDEOS:
        p.append(
            f'  <span class="vidrow">'
            f'<a class="vch" href="https://www.youtube.com/@{handle}" target="_blank" '
            f'rel="noopener" title="{e(channel)} on YouTube">'
            f'<img src="{root}assets/media/yt/{avatar}" alt="{e(channel)}" loading="lazy">'
            f'</a>'
            f'<a class="vid" href="{e(f"https://www.youtube.com/watch?v={vid}{extra}")}" '
            f'target="_blank" rel="noopener">'
            f'<span class="vt">{e(title)}</span>'
            f'<span class="vc">{e(channel)}</span></a></span>')

    p.append("  </nav>")
    p.append("</aside>")
    return "\n".join(p)


PICK_JS = """
<script>
/* Choose the method you are actually using. Saved to data/picks.json through
   serve.py when it is running, and to localStorage either way, so a rebuild
   keeps the choice. */
(function () {
  var skill = window.SKILL;
  if (!skill) return;
  var rows = Array.prototype.slice.call(document.querySelectorAll('tr.m'));
  if (!rows.length) return;
  var note = document.getElementById('savednote');
  var panel = document.getElementById('pickpanel');
  var nopick = document.getElementById('nopick');
  var pname = document.getElementById('pickname');
  var pdetail = document.getElementById('pickdetail');
  var pimg = document.getElementById('pickimg');
  var KEY = 'osrsplan.pick.' + skill;

  function say(msg, cls) {
    if (!note) return;
    note.textContent = msg;
    note.className = 'savednote' + (cls ? ' ' + cls : '');
  }

  function show(row, announce) {
    var method = row.getAttribute('data-method');
    rows.forEach(function (r) {
      var active = r === row;
      r.classList.toggle('chosen', active);
      var button = r.querySelector('.pickbtn');
      if (button) button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    if (pname) pname.textContent = method;
    if (pdetail) {
      var cell = row.querySelector('td.notes');
      pdetail.innerHTML = cell ? '<p>' + cell.innerHTML + '</p>' : '';
    }
    if (pimg) {
      var thumb = row.querySelector('img.thumb');
      if (thumb) { pimg.src = thumb.getAttribute('src'); pimg.hidden = false; }
      else { pimg.hidden = true; }
    }
    if (panel) panel.hidden = false;
    if (nopick) nopick.hidden = true;
    if (announce) say('Saved: ' + method + ' is your method for ' + skill + '.', 'ok');
  }

  try {
    var saved = localStorage.getItem(KEY);
    if (saved) {
      var match = rows.filter(function (r) { return r.getAttribute('data-method') === saved; })[0];
      if (match && !match.classList.contains('chosen')) show(match, false);
    }
  } catch (err) { /* private mode */ }

  rows.forEach(function (row) {
    var btn = row.querySelector('.pickbtn');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var method = row.getAttribute('data-method');
      show(row, true);
      try { localStorage.setItem(KEY, method); } catch (err) { /* ignore */ }
      if (!/^https?:$/.test(location.protocol)) return;
      fetch('/api/pick', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill: skill, method: method })
      }).then(function (r) {
        if (!r.ok) throw new Error('not saved to disk');
        say('Saved: ' + method + '. Run build.py to bake it in.', 'ok');
      }).catch(function () {
        say('Saved in this browser only. Start serve.py to write it to picks.json.', 'warnc');
      });
    });
  });
})();
</script>
"""

OWN_JS = """
<script>
/* Owned gear, a piece at a time. A completed set switches on that skill's rate
   toggle, which lives under the key the skill page reads. */
(function () {
  var sets = Array.prototype.slice.call(document.querySelectorAll('.outfit'));
  if (!sets.length) return;
  var KEY = 'osrsplan.pieces';

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}'); }
    catch (err) { return {}; }
  }
  var owned = load();

  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(owned)); } catch (err) { /* ignore */ }
  }

  function setBonus(skill, idx, on) {
    if (!skill || isNaN(idx)) return;
    var k = 'osrsplan.bonus.' + skill, list = [];
    try { list = JSON.parse(localStorage.getItem(k) || '[]'); } catch (err) { list = []; }
    var at = list.indexOf(idx);
    if (on && at === -1) list.push(idx);
    if (!on && at !== -1) list.splice(at, 1);
    try { localStorage.setItem(k, JSON.stringify(list)); } catch (err) { /* ignore */ }
  }

  sets.forEach(function (row) {
    var name = row.getAttribute('data-set');
    var total = parseInt(row.getAttribute('data-total'), 10) || 0;
    var boxes = Array.prototype.slice.call(row.querySelectorAll('.piecebox'));
    var count = row.querySelector('.ocount');
    var mine = owned[name] || {};

    function refresh(write) {
      var have = boxes.filter(function (b) { return b.checked; }).length;
      count.textContent = have + '/' + total;
      row.classList.toggle('have', have === total);
      row.classList.toggle('part', have > 0 && have < total);
      if (write) {
        (row.getAttribute('data-bonuses') || '').split('|').forEach(function (raw) {
          if (raw !== '') setBonus(row.getAttribute('data-skill'), parseInt(raw, 10),
                                   have === total);
        });
      }
    }

    boxes.forEach(function (b) {
      b.checked = !!mine[b.getAttribute('data-piece')];
      b.addEventListener('change', function () {
        if (!owned[name]) owned[name] = {};
        owned[name][b.getAttribute('data-piece')] = b.checked;
        save();
        refresh(true);
      });
    });
    refresh(true);
  });
})();
</script>
"""

PATH_JS = """
<script>
/* One route at a time; the panels are the switch. */
(function () {
  var picks = Array.prototype.slice.call(document.querySelectorAll('.stat.pick'));
  var cards = Array.prototype.slice.call(document.querySelectorAll('.pathcard'));
  if (!picks.length || !cards.length) return;
  var KEY = 'osrsplan.path';

  function show(key) {
    picks.forEach(function (b) {
      var active = b.getAttribute('data-path') === key;
      b.classList.toggle('on', active);
      b.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    cards.forEach(function (c) { c.hidden = c.getAttribute('data-path') !== key; });
    try { localStorage.setItem(KEY, key); } catch (err) { /* ignore */ }
  }

  var hash = location.hash.replace(/^#(?:path-)?/, '');
  if (hash && cards.some(function (c) { return c.getAttribute('data-path') === hash; })) {
    show(hash);
  } else {
    try {
      var saved = localStorage.getItem(KEY);
      if (saved && cards.some(function (c) { return c.getAttribute('data-path') === saved; })) {
        show(saved);
      }
    } catch (err) { /* private mode */ }
  }

  picks.forEach(function (b) {
    b.addEventListener('click', function () { show(b.getAttribute('data-path')); });
  });
})();
</script>
"""

POTION_JS = """
<script>
/* Potion costs, priced from the OSRS Wiki real-time price API. It allows
   cross-origin reads, so this works on the published copy as well as locally. */
(function () {
  var table = document.getElementById('pottable');
  if (!table) return;
  var rows = Array.prototype.slice.call(table.querySelectorAll('tr.pot'));
  var status = document.getElementById('potstatus');
  var btn = document.getElementById('potrefresh');
  var pick = document.getElementById('potpick');
  var priced = null;

  /* Read the level off the live panel every time, so a refresh that moves it
     moves this too. The build-time value is only the fallback. */
  function level() {
    var el = document.querySelector('[data-skill-level="'
      + table.getAttribute('data-skill') + '"]');
    return parseInt(el && el.textContent, 10)
      || parseInt(table.getAttribute('data-level'), 10) || 0;
  }

  function gp(n) {
    if (n == null || !isFinite(n)) return '-';
    var sign = n < 0 ? '-' : '';
    var v = Math.abs(Math.round(n));
    return sign + v.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',');
  }

  function apply(prices) {
    var best = null, lvl = level();
    priced = prices;
    rows.forEach(function (row) {
      var inputs = JSON.parse(row.getAttribute('data-inputs'));
      var made = prices[row.getAttribute('data-made')];
      var xp = parseFloat(row.getAttribute('data-xp'));
      var cost = 0, ok = made != null;
      inputs.forEach(function (i) {
        var p = prices[i.id];
        if (p == null) { ok = false; return; }
        cost += p * i.qty;
      });
      var gpxp = ok ? (cost - made) / xp : null;
      var profit = ok ? made - cost : null;
      row.querySelector('.gpxp').textContent = ok ? gp(gpxp) : '-';
      row.querySelector('.profit').textContent = ok ? gp(profit) : '-';
      row.querySelector('.profit').classList.toggle('good', ok && profit > 0);
      row.querySelector('.gpxp').classList.toggle('good', ok && gpxp <= 0);
      row.dataset.gpxp = ok ? gpxp : '';
      var usable = parseInt(row.getAttribute('data-level'), 10) <= lvl;
      if (ok && usable && (best === null || gpxp < best.gpxp)) {
        best = { gpxp: gpxp, name: row.querySelector('.tn').textContent.trim(),
                 xp: xp, profit: profit, level: row.getAttribute('data-level') };
      }
    });

    if (best && pick) {
      var verdict = best.gpxp <= 0
        ? 'It turns a profit while you train, so the only cost is your time.'
        : 'The cheapest experience open to you right now.';
      pick.replaceChildren();
      var heading = document.createElement('span');
      heading.className = 'k';
      heading.textContent = 'Best at your level';
      var name = document.createElement('b');
      name.textContent = best.name;
      var detail = document.createElement('span');
      detail.className = 'pdet';
      detail.textContent = gp(best.gpxp) + ' GP per XP \u00b7 ' + best.xp
        + ' XP each \u00b7 ' + gp(best.profit) + ' GP profit each';
      var why = document.createElement('span');
      why.className = 'pwhy';
      why.textContent = verdict;
      pick.append(heading, name, detail, why);
      pick.hidden = false;
    }
    filter();
  }

  function filter() {
    var lvl = level();
    rows.forEach(function (row) {
      row.hidden = parseInt(row.getAttribute('data-level'), 10) > lvl;
    });
  }

  function load() {
    if (btn.classList.contains('busy')) return;
    btn.classList.add('busy');
    btn.classList.remove('ok', 'bad');
    var started = Date.now();
    var settle = function (fn, bad) {
      setTimeout(function () {
        btn.classList.remove('busy');
        btn.classList.add(bad ? 'bad' : 'ok');
        setTimeout(function () { btn.classList.remove('ok', 'bad'); }, 2500);
        fn();
      }, Math.max(0, 900 - (Date.now() - started)));
    };

    fetch('https://prices.runescape.wiki/api/v1/osrs/latest', { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var prices = {};
        Object.keys(d.data || {}).forEach(function (id) {
          var p = d.data[id];
          prices[id] = p.high || p.low;
        });
        settle(function () {
          apply(prices);
          status.textContent = 'priced just now';
        });
      })
      .catch(function () {
        settle(function () { status.textContent = 'prices unavailable'; }, true);
      });
  }

  document.addEventListener('osrsplan:stats', function () {
    if (priced) apply(priced); else filter();
  });
  btn.addEventListener('click', load);
  load();

  /* Re-render from what is already loaded: drops anything that has run out,
     re-sorts, and moves the countdowns on. No network. */
  setInterval(function () {
    if (latest.length && !draw(latest, latestAt)) {
      empty('Every star on the last list has burned out.');
    }
  }, TICK);

  /* Only worth polling when something is actually serving live stars. The
     committed snapshot does not change between page loads. */
  setInterval(function () {
    if (fromServer && !document.hidden) load();
  }, POLL);
})();
</script>
"""

BONUS_JS = """
<script>
/* XP gear toggles: rescale the rate column by whatever is ticked. Rates are
   the base numbers, so the toggles only ever multiply up. */
(function () {
  var bar = document.getElementById('bonusbar');
  if (!bar) return;
  var skill = bar.getAttribute('data-skill');
  var boxes = Array.prototype.slice.call(bar.querySelectorAll('input[type=checkbox]'));
  var cells = Array.prototype.slice.call(document.querySelectorAll('td.rate[data-base]'));
  var KEY = 'osrsplan.bonus.' + skill;

  function scale(text, mult) {
    if (mult === 1) return text;
    return text.replace(/(\\d[\\d,]*(?:\\.\\d+)?)(\\s*k)?/gi, function (all, num, k) {
      var v = parseFloat(num.replace(/,/g, ''));
      if (!isFinite(v)) return all;
      var out = v * mult;
      if (k) return (out >= 100 ? Math.round(out) : Math.round(out * 10) / 10) + k;
      if (out >= 1000) return Math.round(out).toLocaleString();
      return Math.round(out * 10) / 10 + '';
    });
  }

  function apply() {
    var active = boxes.filter(function (b) { return b.checked; });
    bar.classList.toggle('on', active.length > 0);
    cells.forEach(function (cell) {
      var base = cell.getAttribute('data-base');
      var row = cell.closest('tr');
      var method = row ? row.getAttribute('data-method') : '';
      var mult = 1;
      active.forEach(function (b) {
        var applies = b.getAttribute('data-applies');
        if (applies && applies.split('|').indexOf(method) === -1) return;
        mult *= 1 + (parseFloat(b.getAttribute('data-pct')) || 0) / 100;
      });
      cell.textContent = scale(base, mult);
      cell.classList.toggle('boosted', mult !== 1);
    });
  }

  try {
    var saved = JSON.parse(localStorage.getItem(KEY) || '[]');
    boxes.forEach(function (b, i) { b.checked = saved.indexOf(i) !== -1; });
  } catch (err) { /* private mode */ }

  boxes.forEach(function (b) {
    b.addEventListener('change', function () {
      apply();
      try {
        localStorage.setItem(KEY, JSON.stringify(
          boxes.map(function (x, i) { return x.checked ? i : -1; })
               .filter(function (i) { return i >= 0; })));
      } catch (err) { /* ignore */ }
    });
  });

  apply();
})();
</script>
"""

STARS_JS = """
<script>
/* Shooting Stars. Tries the local server first, then the snapshot committed to
   the repo, and falls back to 07.gg's own tracker in a frame so the panel
   always shows something. */
(function () {
  var box = document.getElementById('stars');
  if (!box) return;
  var list = document.getElementById('starlist');
  var status = document.getElementById('starstatus');
  var btn = document.getElementById('starrefresh');
  var limit = parseInt(list.getAttribute('data-limit'), 10) || 12;
  var root = box.getAttribute('data-root') || '';
  var pickMin = document.getElementById('tiermin');
  var pickMax = document.getElementById('tiermax');
  var mining = parseInt(box.getAttribute('data-mining'), 10) || 0;
  var latest = [];
  var latestAt = 0;
  var fromServer = false;

  /* Two different clocks. The countdowns only need arithmetic on data we
     already hold, so they tick locally and cost nothing. Actually re-fetching
     is worth doing about once a minute: a new star lands somewhere every half
     a minute or so, but you are picking from ninety-odd live ones, so the list
     does not go stale nearly as fast as it grows. */
  var TICK = 20000;
  var POLL = 60000;

  if (pickMin) pickMin.value = '1';
  if (pickMax) pickMax.value = '9';

  function lo() { return pickMin ? (parseInt(pickMin.value, 10) || 1) : 1; }
  function hi() { return pickMax ? (parseInt(pickMax.value, 10) || 9) : 9; }

  function mins(ms) {
    var m = Math.round((ms - Date.now()) / 60000);
    return m <= 0 ? 'ending' : m + 'm';
  }

  /* Star fields are crowd-sourced on 07.gg, so treat them as untrusted. This
     encodes quotes as well as angle brackets, so it is safe in both text and
     quoted-attribute context; serve.py also strips these characters on the way
     in. */
  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function int(v) { return Math.max(0, parseInt(v, 10) || 0); }

  function draw(stars, at) {
    latest = stars; latestAt = at;
    var min = lo(), max = hi();
    var live = stars.filter(function (s) {
      var t = int(s.tier);
      return s.endsAt > Date.now() && t >= min && t <= max;
    });
    if (!live.length) return false;
    /* Soonest to fall first: a star with eight minutes left is the one worth
       reading, not the one at the top of whatever order 07.gg returned. */
    live.sort(function (a, b) { return a.endsAt - b.endsAt; });
    list.innerHTML = live.slice(0, limit).map(function (s) {
      var left = Math.round((s.endsAt - Date.now()) / 60000);
      var tier = int(s.tier), world = int(s.world);
      var req = tier * 10;
      var can = !mining || mining >= req;
      var hit = findMap(s.location);
      var loc = esc(tidy(hit && hit.n ? hit.n : s.location));
      var map = 'https://oldschool.runescape.wiki/w/Special:Search?go=Go&search='
        + encodeURIComponent(hit && hit.n ? hit.n : s.location);
      return '<div class="star' + (can ? '' : ' locked')
        + (left <= 5 ? ' soon' : '') + '">'
        + '<span class="stier' + (tier >= 7 ? ' hot' : '') + '" title="Tier ' + tier
        + ', needs ' + req + ' Mining">T' + tier + '</span>'
        + '<span class="sworld" title="Hop to world ' + world + '">'
        + world + '</span>'
        + '<a class="sloc" href="' + map + '" target="_blank" rel="noopener" '
        + 'title="Find ' + loc + ' on the wiki">' + loc + '</a>'
        + '<button class="sview" type="button" data-loc="' + loc + '" '
        + 'title="Show a map of this area">view</button>'
        + '<span class="sreq" title="Mining level for this tier">' + req + '</span>'
        + '<span class="sends">' + esc(mins(s.endsAt)) + '</span></div>';
    }).join('');
    var age = at ? Math.round((Date.now() - at) / 60000) : 0;
    var ranged = (min > 1 || max < 9);
    var shown = live.length + (ranged ? ' in T' + min + '-T' + max : ' active');
    status.textContent = shown + (age > 1 ? ' \u00b7 ' + age + 'm ago' : '');
    return true;
  }

  function empty(msg) {
    list.innerHTML = '<p class="starnone">' + msg + ' '
      + '<a href="https://07.gg/trackers/shooting-star" target="_blank" rel="noopener">'
      + 'Check the tracker directly &#8599;</a></p>';
    status.textContent = 'no live data';
  }

  function get(url) {
    return fetch(url, { cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
  }

  function load() {
    if (btn.classList.contains('busy')) return;
    btn.classList.add('busy');
    btn.classList.remove('ok', 'bad');
    var started = Date.now();
    var done = function (fn, bad) {
      setTimeout(function () {
        btn.classList.remove('busy');
        btn.classList.add(bad ? 'bad' : 'ok');
        setTimeout(function () { btn.classList.remove('ok', 'bad'); }, bad ? 3000 : 2500);
        fn();
      }, Math.max(0, 1400 - (Date.now() - started)));
    };

    get('/api/stars')
      .then(function (d) {
        if (d.error || !d.stars) throw new Error('no data');
        fromServer = true;
        done(function () {
          if (!draw(d.stars, d.at)) empty('No stars are active right now.');
        });
      })
      .catch(function () {
        get(root + 'data/stars.json')
          .then(function (d) {
            done(function () {
              if (!draw(d.stars || [], d.at)) {
                empty('The saved list has expired. Run <code>serve.py</code> for live stars.');
              }
            });
          })
          .catch(function () {
            done(function () {
              empty('Live stars need <code>serve.py</code> running.');
            }, true);
          });
      });
  }

  [pickMin, pickMax].forEach(function (sel) {
    if (!sel) return;
    sel.addEventListener('change', function () {
      if (lo() > hi()) {
        if (sel === pickMin) pickMax.value = pickMin.value;
        else pickMin.value = pickMax.value;
      }
      if (latest.length && !draw(latest, latestAt)) {
        list.innerHTML = '<p class="starnone">Nothing in that tier range right now.</p>';
        status.textContent = '0 in T' + lo() + '-T' + hi();
      }
    });
  });

  /* 07.gg types its own location names, so match them loosely against the
     wiki's crash-site list. */
  var mapIndex = (function () {
    var out = {};
    var src = window.STARMAPS || {};
    Object.keys(src).forEach(function (k) {
      out[norm(k)] = { f: src[k].f, n: k };
    });
    return out;
  })();

  /* 07.gg's callers type these by hand, so tidy up what we cannot match to a
     wiki name: sentence case, and directions in caps. */
  var SMALL = ['of', 'the', 'in', 'on', 'at', 'to', 'and', 'a', 'an', 'for', 'by'];

  function tidy(loc) {
    return String(loc).trim().split(/\\s+/).map(function (w, i) {
      var bare = w.replace(/[^a-z]/gi, '').toLowerCase();
      if (/^(nw|ne|sw|se)$/.test(bare)) return w.toUpperCase();
      if (i > 0 && SMALL.indexOf(bare) !== -1) return w.toLowerCase();
      if (/^[A-Z0-9'-]{2,}$/.test(w)) return w;
      return w.charAt(0).toUpperCase() + w.slice(1);
    }).join(' ');
  }

  function norm(t) {
    return String(t).toLowerCase().replace(/\\(.*?\\)/g, ' ')
      .replace(/[^a-z0-9 ]/g, ' ').replace(/\\s+/g, ' ').trim();
  }

  /* names 07.gg uses that the wiki files under something else */
  var ALIAS = {
    'prifddinas zalcano entrance': 'trahaearn mine entrance',
    'ardougne monastery': 'south east ardougne mine monastery',
    'mine northwest of hunter guild': 'mistrock mine',
    'theatre of blood bank': 'ver sinhaza bank',
    'varlamore colosseum entrance bank': 'civitas illa fortis east bank',
    'south of mount quidamortem': 'mount quidamortem bank',
    'lava maze runite mine': 'lava maze runite mine'
  };

  function findMap(loc) {
    var n = norm(loc);
    if (ALIAS[n]) n = ALIAS[n];
    if (mapIndex[n]) return mapIndex[n];
    var keys = Object.keys(mapIndex), best = null, score = 0;
    var words = n.split(' ');
    keys.forEach(function (k) {
      if (k.indexOf(n) !== -1 || n.indexOf(k) !== -1) {
        var s2 = Math.min(k.length, n.length) / Math.max(k.length, n.length) + 1;
        if (s2 > score) { score = s2; best = mapIndex[k]; }
        return;
      }
      var kw = k.split(' ');
      var hits = words.filter(function (w) { return w.length > 2 && kw.indexOf(w) !== -1; }).length;
      var s3 = hits / Math.max(words.length, kw.length);
      if (hits >= 2 && s3 > score) { score = s3; best = mapIndex[k]; }
    });
    return score >= 0.5 ? best : null;
  }

  var pop = document.createElement('div');
  pop.className = 'starpop';
  pop.hidden = true;
  document.body.appendChild(pop);

  function showPop(btn2) {
    var loc = btn2.getAttribute('data-loc');
    var hit = findMap(loc);
    pop.innerHTML = (hit
      ? '<img src="' + (window.STARMAPROOT || '') + hit.f + '" alt="">'
      : '<div class="nomap">no map for this spot</div>')
      + '<span class="ploc"></span>';
    pop.querySelector('.ploc').textContent = tidy(hit && hit.n ? hit.n : loc);
    pop.hidden = false;
    var r = btn2.getBoundingClientRect();
    var top = r.bottom + window.scrollY + 8;
    var left = Math.min(r.left + window.scrollX - 90,
                        window.scrollX + document.documentElement.clientWidth - 230);
    pop.style.top = top + 'px';
    pop.style.left = Math.max(window.scrollX + 8, left) + 'px';
  }

  list.addEventListener('mouseover', function (ev) {
    var b = ev.target.closest('.sview');
    if (b) showPop(b);
  });
  list.addEventListener('mouseout', function (ev) {
    if (ev.target.closest('.sview')) pop.hidden = true;
  });
  list.addEventListener('focusin', function (ev) {
    var b = ev.target.closest('.sview');
    if (b) showPop(b);
  });
  list.addEventListener('focusout', function () { pop.hidden = true; });
  list.addEventListener('click', function (ev) {
    var view = ev.target.closest('.sview');
    if (!view) return;
    if (window.matchMedia('(hover: none)').matches) {
      ev.preventDefault();
      showPop(view);
      return;
    }
    window.open('https://07.gg/trackers/shooting-star', '_blank', 'noopener');
  });

  btn.addEventListener('click', load);
  load();

  /* Re-render from what is already loaded: drops anything that has run out,
     re-sorts, and moves the countdowns on. No network. */
  setInterval(function () {
    if (latest.length && !draw(latest, latestAt)) {
      empty('Every star on the last list has burned out.');
    }
  }, TICK);

  /* Only worth polling when something is actually serving live stars. The
     committed snapshot does not change between page loads. */
  setInterval(function () {
    if (fromServer && !document.hidden) load();
  }, POLL);
})();
</script>
"""

TASKS_JS = """
<script>
/* Filter and sort the Slayer task table. */
(function () {
  var table = document.getElementById('tasktable');
  if (!table) return;
  var body = table.tBodies[0];
  var rows = Array.prototype.slice.call(body.rows);
  var filters = Array.prototype.slice.call(document.querySelectorAll('.tf'));
  var sorts = Array.prototype.slice.call(document.querySelectorAll('.ts'));

  function num(row, key) { return parseInt(row.getAttribute('data-' + key), 10) || 0; }

  filters.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var want = btn.getAttribute('data-f');
      filters.forEach(function (b) {
        var active = b === btn;
        b.classList.toggle('on', active);
        b.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      rows.forEach(function (r) {
        r.hidden = want !== 'all' && r.getAttribute('data-tag') !== want;
      });
    });
  });

  sorts.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var key = btn.getAttribute('data-s');
      sorts.forEach(function (b) {
        var active = b === btn;
        b.classList.toggle('on', active);
        b.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      var sorted = rows.slice().sort(function (a, b) {
        if (key === 'verdict') {
          return num(a, 'order') - num(b, 'order') || num(b, 'weight') - num(a, 'weight');
        }
        if (key === 'level') return num(a, 'level') - num(b, 'level');
        return num(b, key) - num(a, key);
      });
      sorted.forEach(function (r) { body.appendChild(r); });
    });
  });
})();
</script>
"""

FOCUS_JS = """
<script>
/* Choose the skill you are currently levelling. Rendered from FOCUSDATA so the
   card updates without a rebuild; persisted to data/focus.json via serve.py and
   to localStorage either way. */
(function () {
  var data = window.FOCUSDATA;
  var buttons = Array.prototype.slice.call(document.querySelectorAll('.focusbtn'));
  if (!data || !buttons.length) return;
  var KEY = 'osrsplan.focus';
  var panel = document.getElementById('focus');

  function fmt(n) {
    return n == null ? '--' : String(n).replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',');
  }

  function set(id, val) {
    var el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function paint(name) {
    var f = data[name];
    if (!f) return;
    buttons.forEach(function (b) {
      b.parentNode.classList.toggle('focused', b.getAttribute('data-skill') === name);
    });
    if (!panel) return;

    var ic = document.getElementById('fic');
    if (ic) ic.src = f.icon;
    set('fname', f.name);
    set('flvl', f.level == null ? '--' : f.level);
    set('fgoal', f.goal);
    set('fxp', fmt(f.xp) + ' XP');
    set('fmethod', f.method);
    var ml = document.getElementById('fmethodlink');
    if (ml) ml.href = f.methodHref;

    var lvl = document.getElementById('flvl');
    if (lvl) lvl.style.setProperty('--lc', f.colour);
    var bar = document.getElementById('fbar');
    if (bar) { bar.style.width = f.pct + '%'; bar.style.setProperty('--lc', f.colour); }
    var link = document.getElementById('flink');
    if (link) { link.href = f.href; link.textContent = 'Open ' + f.name + ' \u203a'; }

    var also = document.getElementById('falso');
    if (also) {
      var list = f.also || [];
      also.hidden = list.length === 0;
      also.innerHTML = '<i>Also Trains</i>' + list.map(function (a) {
        return '<a class="fa" href="' + a.href + '">'
          + '<img class="icon sm" src="' + a.icon + '" alt="">'
          + '<span class="fan">' + a.name + '</span>'
          + '<b class="fal" style="--lc:' + a.colour + '">' + (a.level || '--') + '</b>'
          + '<span class="fag">/' + a.goal + '</span></a>';
      }).join('');
    }
  }

  try {
    var saved = localStorage.getItem(KEY);
    if (saved && data[saved] && saved !== window.FOCUSNOW) paint(saved);
  } catch (err) { /* private mode */ }

  buttons.forEach(function (btn) {
    btn.addEventListener('click', function (ev) {
      ev.preventDefault();
      var name = btn.getAttribute('data-skill');
      paint(name);
      try { localStorage.setItem(KEY, name); } catch (err) { /* ignore */ }
      if (!/^https?:$/.test(location.protocol)) return;
      fetch('/api/focus', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill: name })
      }).catch(function () { /* localStorage still has it */ });
    });
  });
})();
</script>
"""

COACH_JS = """
<script>
/* Character refresh and deterministic next-step guidance for serve.py. */
(function () {
  var coach = document.querySelector('.coach');
  var sync = document.getElementById('sync-character');
  var ask = document.getElementById('ask-character');
  var status = document.getElementById('coach-status');
  var output = document.getElementById('coach-output');
  var controls = document.querySelector('.cctl');
  if (!coach || !sync || !ask || !status || !output) return;
  if (window.location.hostname.endsWith('.github.io')) {
    coach.hidden = true;
    if (controls) controls.hidden = true;
    return;
  }

  /* The tick on the sync icon means "this page is showing freshly synced
     data", so it survives the reload a sync triggers but not a new tab. */
  var SYNCED = 'osrsplan.synced';
  try {
    if (sessionStorage.getItem(SYNCED)) sync.classList.add('ok');
  } catch (err) { /* private mode */ }

  function marksynced() {
    sync.classList.add('ok');
    try { sessionStorage.setItem(SYNCED, '1'); } catch (err) { /* private mode */ }
  }

  function busy(on) {
    sync.disabled = on;
    ask.disabled = on;
    sync.classList.toggle('busy', on);
    ask.classList.toggle('busy', on);
    if (on) sync.classList.remove('ok');
  }

  function request(path) {
    return fetch(path, {
      method: 'POST',
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok || !data || data.error) {
          throw new Error(data.error || 'This action needs python3 serve.py.');
        }
        return data;
      });
    });
  }

  function add(tag, className, text) {
    var element = document.createElement(tag);
    element.className = className;
    element.textContent = text;
    output.appendChild(element);
    return element;
  }

  function render(data) {
    var advice = data.advice || {};
    output.textContent = '';
    add('span', 'k', 'Synced recommendation');
    add('h3', 'coach-title', advice.headline || 'No recommendation available');
    if (advice.summary) add('p', 'coach-summary', advice.summary);
    if (Array.isArray(advice.actions) && advice.actions.length) {
      var list = document.createElement('ol');
      list.className = 'coach-steps';
      advice.actions.forEach(function (text) {
        var item = document.createElement('li');
        item.textContent = text;
        list.appendChild(item);
      });
      output.appendChild(list);
    }
    if (advice.checkpoint) add('p', 'coach-note', 'Next checkpoint: ' + advice.checkpoint + '.');
    if (advice.next_quest) add('p', 'coach-note', 'Then resume with ' + advice.next_quest + '.');
    if (advice.reward_note) add('p', 'coach-reward', advice.reward_note);
    output.hidden = false;
    var motion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      ? 'auto' : 'smooth';
    output.scrollIntoView({ behavior: motion, block: 'nearest' });
  }

  sync.addEventListener('click', function () {
    busy(true);
    output.hidden = true;
    status.classList.remove('bad');
    status.textContent = 'Syncing Hiscores, quests and diaries…';
    request('/api/sync').then(function () {
      marksynced();
      status.textContent = 'Synced. Reloading the updated site…';
      location.reload();
    }).catch(function (error) {
      status.textContent = String(error.message || error);
      status.classList.add('bad');
      busy(false);
    });
  });

  ask.addEventListener('click', function () {
    busy(true);
    output.hidden = true;
    status.classList.remove('bad');
    status.textContent = 'Syncing before choosing your next action…';
    request('/api/advice').then(function (data) {
      render(data);
      marksynced();
      status.textContent = 'Character synced just now.';
      busy(false);
    }).catch(function (error) {
      status.textContent = String(error.message || error);
      status.classList.add('bad');
      busy(false);
    });
  });
})();
</script>
"""

RAIL_JS = """
<script>
(function () {
  var rail = document.querySelector('.rail-body');
  if (!rail) return;
  var here = rail.querySelector('a.here');
  if (here && rail.scrollHeight > rail.clientHeight + 1) {
    rail.scrollTop = Math.max(0, here.offsetTop - rail.clientHeight / 2);
  }
})();
</script>
"""

LIVE_STATS_JS = """
<script>
(function () {
  var button = document.getElementById('statrefresh');
  var status = document.getElementById('statrefresh-status');
  if (!button || !status) return;

  var endpoint = __HISCORES_WORKER__;
  var defaultLabel = 'Refresh gxexe from OSRS Hiscores';
  var timer = 0;

  function levelColour(value) {
    var level = Math.max(1, Math.min(99, Number(value) || 1));
    var stops = [[1, 12], [40, 28], [60, 44], [75, 62], [88, 96], [95, 120], [99, 142]];
    var hue = 142;
    for (var i = 0; i < stops.length - 1; i += 1) {
      var left = stops[i];
      var right = stops[i + 1];
      if (level <= right[0]) {
        hue = left[1] + (right[1] - left[1]) * ((level - left[0]) / (right[0] - left[0]));
        break;
      }
    }
    return 'hsl(' + Math.round(hue) + ' ' + Math.round(70 + 8 * level / 99) + '% ' +
      Math.round(58 + 7 * level / 99) + '%)';
  }

  function setState(kind, message) {
    window.clearTimeout(timer);
    button.disabled = false;
    button.classList.remove('busy', 'ok', 'bad');
    if (kind) button.classList.add(kind);
    button.title = message;
    button.setAttribute('aria-label', message);
    status.textContent = message;
    timer = window.setTimeout(function () {
      button.classList.remove('ok', 'bad');
      button.title = defaultLabel;
      button.setAttribute('aria-label', defaultLabel);
    }, 3500);
  }

  function paint(data) {
    var total = document.querySelector('[data-stat="total"]');
    var combat = document.querySelector('[data-stat="combat"]');
    if (total) total.textContent = data.overall.level;
    if (combat) combat.textContent = data.combat;
    document.querySelectorAll('[data-live-skill]').forEach(function (node) {
      var record = data.skills[node.getAttribute('data-live-skill')];
      if (!record || !Number.isInteger(record.level)) return;
      node.textContent = record.level;
      node.classList.add('lit');
      node.classList.remove('done');
      node.style.setProperty('--lc', levelColour(record.level));
    });
  }

  button.addEventListener('click', function () {
    window.clearTimeout(timer);
    button.disabled = true;
    button.classList.remove('ok', 'bad');
    button.classList.add('busy');
    button.title = 'Refreshing gxexe…';
    button.setAttribute('aria-label', 'Refreshing gxexe from OSRS Hiscores');
    status.textContent = 'Refreshing gxexe from OSRS Hiscores.';
    fetch(endpoint, { cache: 'no-store' }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok || !data.overall || !data.skills) {
          throw new Error(data.error || 'Hiscores refresh failed');
        }
        return data;
      });
    }).then(function (data) {
      paint(data);
      var snap = document.getElementById('statsnap');
      if (snap) snap.textContent = (data.name || 'gxexe') + ' \u00b7 Hiscores live, just now';
      setState('ok', 'gxexe refreshed from OSRS Hiscores');
    }).catch(function (error) {
      setState('bad', error.message || 'Hiscores refresh failed');
    });
  });
})();
</script>
""".replace("__HISCORES_WORKER__", json.dumps(HISCORES_WORKER))


def page(title, body, active=None, depth=0, skill_name=None, head_extra="",
         wide=False, coach=False):
    root = "../" if depth else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{e(title)}</title>
<link rel="preload" href="{root}assets/fonts/Geist-Regular.v1.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" type="image/png" sizes="64x64" href="{root}assets/favicon-64.png">
<link rel="icon" type="image/png" sizes="32x32" href="{root}assets/favicon-32.png">
<link rel="apple-touch-icon" href="{root}assets/favicon-64.png">
<link rel="stylesheet" href="{root}assets/style.css">
{f'<script>window.SKILL={json.dumps(skill_name)};</script>' if skill_name else ""}
{focus_data_script()}
{head_extra}
</head>
<body>
<div class="frame">
<header class="sidebar">
  <a class="mark" href="{root}index.html"><img class="capemark" src="{root}assets/media/max-cape.png" alt="">OSRS Max Time-Wasting Plan</a>
  <nav class="topnav">
    <a class="navlink" href="{root}stars.html">{COMET_SVG}Shooting Stars</a>
    <a class="navlink" href="{root}paths.html">Paths</a>
    <a class="navlink" href="{root}calculators.html">Calculators</a>
    <a class="navlink" href="{root}afk.html">AFK</a>
  </nav>
{rail(active=active, depth=depth, coach=coach)}
</header>
<div class="shell{" wide" if wide else ""}">
<main class="main">
{body}
</main>
</div>
</div>
{RAIL_JS}{LIVE_STATS_JS}{COACH_JS if coach else ""}{PICK_JS}{FOCUS_JS}{TASKS_JS}{STARS_JS}{BONUS_JS}{OWN_JS}{POTION_JS}{PATH_JS}
</body>
</html>
"""


# --------------------------------------------------------------------------
# Requirement parsing: which methods are actually open at your level
# --------------------------------------------------------------------------

_ABBREV = {
    "fish": "Fishing", "hunt": "Hunter", "con": "Construction", "cons": "Construction",
    "rc": "Runecraft", "herb": "Herblore", "mage": "Magic", "magic": "Magic",
    "range": "Ranged", "ranged": "Ranged", "att": "Attack", "str": "Strength",
    "def": "Defence", "craft": "Crafting", "smith": "Smithing", "agi": "Agility",
    "slay": "Slayer", "slayer": "Slayer", "cook": "Cooking", "fletch": "Fletching",
    "farm": "Farming", "fm": "Firemaking", "wc": "Woodcutting", "mine": "Mining",
    "mining": "Mining", "thiev": "Thieving", "pray": "Prayer", "prayer": "Prayer",
    "construction": "Construction", "hitpoints": "Hitpoints", "sailing": "Sailing",
}
for _n in ("Attack", "Strength", "Defence", "Ranged", "Magic", "Prayer", "Slayer",
           "Fishing", "Hunter", "Agility", "Thieving", "Mining", "Woodcutting",
           "Runecraft", "Farming", "Smithing", "Crafting", "Fletching",
           "Construction", "Herblore", "Cooking", "Firemaking", "Sailing"):
    _ABBREV[_n.lower()] = _n

COMBAT_KEY = "__combat__"


def parse_reqs(req, own_skill):
    """(skill, level) pairs a requirement string implies. `own_skill` for bare
    numbers. Slash groups take the lowest entry point."""
    if not req or req in ("—", "any", "varies"):
        return []

    out, bare = [], []
    text = req.replace("–", "-")

    for m in re.finditer(r"(?<![A-Za-z0-9])(\d{1,3})\s*\+?\s*([A-Za-z']+)?", text):
        num = int(m.group(1))
        word = (m.group(2) or "").strip("'").lower()
        if not 1 <= num <= 126:
            continue
        if word.startswith("combat"):
            out.append((COMBAT_KEY, num))
        elif word in _ABBREV:
            out.append((_ABBREV[word], num))
        else:
            bare.append(num)

    for m in re.finditer(r"([A-Za-z']+)\s+(\d{1,3})\b", text):
        word = m.group(1).lower()
        num = int(m.group(2))
        if word in _ABBREV and (_ABBREV[word], num) not in out:
            out.append((_ABBREV[word], num))
            if num in bare:
                bare.remove(num)

    if bare:
        out.append((own_skill, min(bare)))
    return out


QUEST_ALIASES = {
    "mm2": "Monkey Madness II",
    "blood moon rises": "The Blood Moon Rises",
    "lunars": "Lunar Diplomacy",
    "fossil island": "Bone Voyage",
}


def quest_unmet(req):
    """An explicitly named quest or diary requirement that is still locked."""
    if not QUESTS or not req:
        return None
    states = QUESTS["states"]
    lower = req.lower()
    names = {name.lower(): name for name in states}
    for alias, quest in QUEST_ALIASES.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lower):
            if states.get(quest) != 2:
                return quest
    for key, quest in sorted(names.items(), key=lambda item: -len(item[0])):
        if re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", lower):
            if states.get(quest) != 2:
                return quest
    if "ardy medium" in lower and DIARIES:
        ardougne = next((r for r in DIARIES["regions"]
                         if r.get("name") == "Ardougne"), {})
        medium = (ardougne.get("tiers") or {}).get("Medium") or {}
        if not medium.get("complete"):
            return "Ardougne medium diary"
    return None


def unmet(req, own_skill):
    """First requirement your account does not meet, or None."""
    locked_quest = quest_unmet(req)
    if locked_quest:
        return locked_quest
    if not STATS:
        return None
    for skill, lvl in parse_reqs(req, own_skill):
        if skill == COMBAT_KEY:
            if (STATS.get("combat") or 0) < lvl:
                return f"{lvl} combat"
            continue
        st = stat_of(skill)
        if not st or st["level"] < lvl:
            return f"{lvl} {skill}"
    return None


def rate_value(rate):
    """Rough XP/hr from the rate column, for ranking unlocked methods."""
    if not rate:
        return 0
    nums = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)", rate.replace(",", ""))]
    if not nums:
        return 0
    scale = 1000 if "k" in rate.lower() else 1
    return max(nums) * scale


DOT_SVG = ('<svg viewBox="0 0 16 16" width="11" height="11" aria-hidden="true">'
           '<circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor" stroke-width="1.6"/>'
           '<circle cx="8" cy="8" r="2" fill="currentColor"/></svg>')

LOCK_SVG = ('<svg viewBox="0 0 16 16" width="10" height="10" aria-hidden="true">'
            '<rect x="3.5" y="7" width="9" height="6.5" rx="1.5" fill="none" '
            'stroke="currentColor" stroke-width="1.6"/>'
            '<path d="M5.6 7V5.2a2.4 2.4 0 0 1 4.8 0V7" fill="none" '
            'stroke="currentColor" stroke-width="1.6"/></svg>')

CHECK_SVG = ('<svg viewBox="0 0 16 16" width="11" height="11" aria-hidden="true">'
             '<path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')


# Methods whose useful variant changes with your level. (level, what you make
# or do at that level), lowest first.
TIERS = {
    "Dragonhide bodies": [(63, "green"), (71, "blue"), (77, "red"), (84, "black")],
    "Battlestaves": [(54, "water"), (58, "earth"), (62, "fire"), (66, "air")],
    "Gem cutting": [(20, "sapphire"), (27, "emerald"), (34, "ruby"), (43, "diamond"),
                    (55, "dragonstone"), (67, "onyx"), (89, "zenyte")],
    "Blast Furnace – other bars": [(30, "steel"), (50, "mithril"), (70, "adamant"),
                                   (85, "runite, and profitable")],
    "Burning logs at a bank": [(30, "willow"), (45, "maple"), (60, "yew"),
                               (75, "magic"), (90, "redwood")],
    "Rooftop courses": [(10, "Draynor"), (20, "Al Kharid"), (30, "Varrock"),
                        (40, "Canifis"), (50, "Falador"), (60, "Seers'"),
                        (70, "Pollnivneach"), (80, "Rellekka"), (90, "Ardougne")],
    "Blackjacking": [(45, "bearded bandits"), (65, "Menaphite thugs")],
    "Pyramid Plunder": [(21, "room 1"), (31, "room 2"), (41, "room 3"), (51, "room 4"),
                        (61, "room 5"), (71, "room 6"), (81, "room 7"), (91, "room 8")],
    "Mahogany Homes": [(20, "novice contracts"), (50, "adept"), (70, "expert"),
                       (90, "master")],
    "Barracuda Trials": [(30, "Tempor Tantrum"), (55, "Jubbly Jive"),
                         (72, "Gwenith Glide")],
    "Courier tasks": [(46, "Summer Shore"), (62, "Rellekka"), (70, "Prifddinas"),
                      (76, "Lunar Isle round trips")],
    "Shooting Stars": [(10, "tier 1 stars"), (20, "tier 2"), (30, "tier 3"),
                       (40, "tier 4"), (50, "tier 5"), (60, "tier 6"), (70, "tier 7"),
                       (80, "tier 8"), (90, "tier 9")],
    "Ironwood / rosewood trees": [(80, "ironwood"), (92, "rosewood")],
}


def tier_line(method, skill_name):
    """For example, "At 75 Crafting you can make blue. Red unlocks at 77.", or None."""
    steps = TIERS.get(method)
    st = stat_of(skill_name)
    if not steps or not st:
        return None
    cur = st["level"]
    have = [t for t in steps if t[0] <= cur]
    nxt = next((t for t in steps if t[0] > cur), None)
    if not have:
        first = steps[0]
        return (f'Nothing unlocked yet: {first[1]} starts at {first[0]} '
                f'{skill_name}.')
    best = have[-1]
    line = f'At {cur} {skill_name}, the best tier open to you is <b>{e(best[1])}</b>.'
    if nxt:
        line += f' Next: {e(nxt[1])} at {nxt[0]}.'
    return line


# XP-affecting gear, per skill. `pct` is the effective XP-rate change, `applies`
# limits it to certain methods, and `note` says what the item actually does,
# because several of these are speed or loot effects rather than XP multipliers.
BONUSES = {
    "Mining": [dict(name="Prospector kit", pct=2.5, applies=None,
                    note="Full set, +2.5% Mining XP.")],
    "Fishing": [dict(name="Angler's outfit", pct=2.5,
                     applies=["Barbarian Fishing", "2-tick harpooning", "Minnows",
                              "Tempoross", "Karambwans", "Monkfish",
                              "Aerial fishing", "Leechfin fishing", "Dark crabs",
                              "Anglerfish"],
                     note="Full set, +2.5% Fishing XP where supported. It does not "
                          "boost Drift Net Fishing or deep-sea trawling.")],
    "Woodcutting": [dict(name="Lumberjack outfit", pct=2.5, applies=None,
                         note="Full set, +2.5% Woodcutting XP.")],
    "Firemaking": [dict(name="Pyromancer outfit", pct=2.5, applies=None,
                        note="Full set, +2.5% Firemaking XP.")],
    "Construction": [dict(name="Carpenter's outfit", pct=2.5, applies=None,
                          note="Full set, +2.5% Construction XP.")],
    "Farming": [dict(name="Farmer's outfit", pct=2.5, applies=None,
                     note="Full set, +2.5% Farming XP.")],
    "Hunter": [dict(name="Guild hunter outfit", pct=0, applies=None,
                    note="Full set gives +2.5% catch rate, but its exact XP/hr effect "
                         "is not established, so the calculator does not inflate rates.")],
    "Smithing": [
        dict(name="Smiths' uniform — Foundry", pct=20,
             applies=["Giants' Foundry"],
             note="The full set averages about +20% XP/hr inside Giants' Foundry."),
        dict(name="Smiths' uniform — anvil", pct=25,
             applies=["Anvil smithing (plates/darts)", "Cannonballs",
                      "Rune items (3-bar)"],
             note="The full set cuts ordinary anvil actions from 5 ticks to 4, "
                  "which is +25% throughput."),
        dict(name="Goldsmith gauntlets", pct=150, applies=["Blast Furnace – gold bars"],
             note="Gold bars go from 22.5 to 56.2 XP each. This is the whole reason the "
                  "method exists."),
    ],
    "Cooking": [dict(name="Cooking gauntlets", pct=5,
                     applies=["Fish at Hosidius / Myths' Guild", "Sharks / Anglerfish"],
                     note="Fewer burns on lobsters, swordfish, sharks and anglerfish, so "
                          "slightly more XP per inventory.")],
    "Runecraft": [dict(name="Raiments of the Eye", pct=0, applies=None,
                       note="Bonus runes, not bonus XP. Worth wearing for the profit, but "
                            "it will not move these rates.")],
    "Thieving": [dict(name="Rogue's outfit", pct=0, applies=None,
                      note="Doubles loot, no XP effect.")],
}


def bonus_controls(skill_name):
    items = BONUSES.get(skill_name)
    if not items:
        return ""
    pills = []
    for i, b in enumerate(items):
        scope = "" if b["applies"] is None else " (some rows)"
        eff = f'+{b["pct"]:g}%' if b["pct"] else "no XP change"
        pills.append(
            f'<label class="bonus" title="{e(b["note"])}">'
            f'<input type="checkbox" data-bonus="{i}" data-pct="{b["pct"]}" '
            f'data-applies="{e("|".join(b["applies"]) if b["applies"] else "")}">'
            f'<span class="bn">{e(b["name"])}</span>'
            f'<span class="bp">{eff}{scope}</span></label>')
    notes = "".join(f'<li><b>{e(b["name"])}</b>. {e(b["note"])}</li>' for b in items)
    return (f'<div class="bonusbar" id="bonusbar" data-skill="{e(skill_name)}">'
            f'<span class="blabel">XP gear</span>{"".join(pills)}</div>'
            f'<details class="bdetails"><summary>What These Actually Do</summary>'
            f'<ul>{notes}</ul></details>')


def best_for_level(methods, skill_name):
    """Highest-rate method whose requirements you already meet."""
    if not STATS:
        return None
    open_now = [(m, rate_value(m[2])) for m in methods if not unmet(m[1], skill_name)]
    if not open_now:
        return None
    rated = [(m, v) for m, v in open_now if v > 0]
    if rated:
        return max(rated, key=lambda pair: pair[1])[0][0]
    # no comparable rates (Slayer masters, for example): first one you can use
    return open_now[0][0][0]


# Route legs are written for the paths page, method rows for the tables, and
# the names do not always agree. Where a leg is not the row name or the row
# name followed by a qualifier, this says which row it belongs to.
ROUTE_ROWS = {
    "Nieve, cannon and burst tasks": "Nieve / Steve",
    "Nieve, cannon and burst": "Nieve / Steve",
    "Nieve, Venator bow on long tasks": "Nieve / Steve",
    "Duradel, barrage tasks": "Duradel",
    "Duradel, cannon and barrage": "Duradel",
    "Duradel, Venator bow on long tasks": "Duradel",
    "Ice Burst on maniacal monkeys": "Bursting maniacal monkeys",
    "Ice Barrage on maniacal monkeys": "Bursting maniacal monkeys",
    "Ice Burst on Slayer tasks": "Bursting/barraging Slayer tasks",
    "Ice Barrage on Slayer tasks": "Bursting/barraging Slayer tasks",
    "Blood Burst at the Bandit Camp lodge": "Bandit Camp lodge, blood spells",
    "Blood Barrage at the Bandit Camp lodge": "Bandit Camp lodge, blood spells",
    "Gilded altar, superior dragon bones": "Gilded altar – superior dragon bones",
    "Gilded altar, one click per inventory": "Gilded altar – dragon bones",
    "Chaos altar, dragon bones": "Wilderness Chaos altar",
    "Lava runes, Magic Imbue": "Lava runes (binding necklace)",
    "Lava runes, giant pouch": "Lava runes (binding necklace)",
    "Lava runes, colossal pouch": "Lava runes (binding necklace)",
    "Ourania altar, daeyalt essence": "ZMI altar",
    "Blood runes at Arceuus": "Blood runes (Arceuus)",
    "Soul runes at Arceuus": "Soul runes (Arceuus)",
    "Seers' Village rooftop": "Rooftop courses",
    "Colossal Wyrm basic course": "Colossal Wyrm course",
    "Colossal Wyrm advanced course": "Colossal Wyrm course",
    "3-tick granite": "3-tick iron / granite",
    "1.5-tick teaks": "Forestry teaks",
    "Rosewood trees": "Ironwood / rosewood trees",
    "Burning yew logs": "Burning logs at a bank",
    "Burning magic logs": "Burning logs at a bank",
    "Burning redwood logs": "Burning logs at a bank",
    "Campfire, maple logs": "Bonfires",
    "Campfire, magic logs": "Bonfires",
    "Campfire, redwood logs": "Bonfires",
    "Red d'hide bodies": "Dragonhide bodies",
    "Black d'hide bodies": "Dragonhide bodies",
    "Blast Furnace gold bars": "Blast Furnace – gold bars",
    "Mithril dart tips": "Anvil smithing (plates/darts)",
    "Adamant dart tips": "Anvil smithing (plates/darts)",
    "Rune nails": "Anvil smithing (plates/darts)",
    "Zamorak brews": "Brews",
    "Ancient brews": "Brews",
    "Armadyl brews": "Brews",
    "Potions, an inventory at a time": "Super restores",
    "Gnome benches": "Mahogany tables",
    "Tempor Tantrum, Marlin rank": "Barracuda Trials",
    "Jubbly Jive, Marlin rank": "Barracuda Trials",
    "Jubbly Jive, Shark rank": "Barracuda Trials",
    "Gwenith Glide, Marlin rank": "Barracuda Trials",
    "Rellekka and Etceteria courier route": "Courier tasks",
    "Lunar Isle courier route": "Courier tasks",
    "Salvaging, Cabin Boy Jenkins on a hook": "Shipwreck salvaging",
    "Salvaging, two crew on dragon hooks": "Shipwreck salvaging",
    "Nightmare Zone, absorptions and blowpipe": "Nightmare Zone",
    "Nightmare Zone, absorptions and Venator bow": "Nightmare Zone",
    "Hallowfell on maniacal monkeys, auto-retaliate": "Hallowfell on maniacal monkeys",
    "Red chinchompas, low-intensity stacking": "Red chinchompas on maniacal monkeys",
}


def route_rows(skill_name):
    """Which route each method row belongs to: {row name: [route keys]}."""
    opts = PATHS.get(skill_name)
    sk = next((s for s in SKILLS if s["name"] == skill_name), None)
    if not opts or not sk:
        return {}
    names = [m[0] for m in sk["methods"]]
    out = {}
    for key, _, _ in PATH_META:
        for _, leg, _ in opts[key]:
            row = ROUTE_ROWS.get(leg)
            if row is None:
                row = next((n for n in names
                            if leg == n or leg.startswith(n + ", ")
                            or leg.startswith(n + " ")), None)
            if row in names and key not in out.setdefault(row, []):
                out[row].append(key)
    return out


ROUTE_WORD = {"fast": "speed", "hybrid": "realistic", "afk": "afk"}


def method_table(methods, pick, skill_name=None):
    rows = []
    rec = best_for_level(methods, skill_name)
    on_route = route_rows(skill_name) if skill_name else {}
    for name, req, rate, note in methods:
        cls = " chosen" if pick and name == pick else ""
        blocker = unmet(req, skill_name)
        if blocker:
            cls += " locked"
        if name == rec:
            cls += " rec"
        src = media_path(METHOD_MEDIA.get(name, ""), depth=1)
        pic = (f'<img class="thumb" src="{src}" alt="" loading="lazy">'
               if src else '<span class="thumb blank"></span>')
        if blocker:
            btn = (f'<button class="pickbtn" type="button" disabled aria-pressed="false" '
                   f'title="Needs {e(blocker)}" aria-label="Locked: needs '
                   f'{e(blocker)}">{LOCK_SVG}</button>')
        else:
            pressed = "true" if pick and name == pick else "false"
            btn = (f'<button class="pickbtn" type="button" aria-pressed="{pressed}" '
                   f'title="Use this method" aria-label="Use {e(name)}">'
                   f'{CHECK_SVG}</button>')
        tag = ""
        if blocker:
            tag = f'<span class="rtag lock">needs {e(blocker)}</span>'
        elif name == rec:
            tag = '<span class="rtag rec">best at your level</span>'
        routes = "".join(
            f'<span class="rtag route {k}" title="On the {ROUTE_WORD[k]} path">'
            f'{ROUTE_WORD[k]}</span>' for k in on_route.get(name, []))
        if routes:
            tag += f'<span class="routes">{routes}</span>'
        rows.append(
            f'    <tr class="m{cls}" id="m-{slug(name)}" data-method="{e(name)}">'
            f'<td class="pic">{pic}</td>'
            f'<td>{wiki_link(name, METHOD_MEDIA.get(name), cased=False)}{tag}</td>'
            f"<td class=\"req\">{e(req)}</td>"
            f'<td class="rate" data-base="{e(rate)}">{e(rate)}</td>' 
            f'<td class="notes">{annotate(note, depth=1, skip=(skill_name,))}</td>'
            f'<td class="choose">{btn}</td></tr>'
        )
    body = "\n".join(rows)
    return f"""<div class="tablewrap"><div class="tablescroll">
<table class="methods">
  <thead><tr><th class="pic"><span class="sr">Image</span></th><th>Method</th>
  <th>Requirement</th><th>XP/hr</th><th>Notes</th>
  <th class="choose"><span class="sr">Choose</span></th></tr></thead>
  <tbody>
{body}
  </tbody>
</table>
</div></div>"""


# --------------------------------------------------------------------------
# Slayer guide: masters, points, task verdicts, Mortimer
# --------------------------------------------------------------------------

MASTERS = [
    ("Turael / Aya", "Burthorpe", "Any level", "0", "40"),
    ("Spria", "Draynor Village", "A Porcine of Interest", "0", "40"),
    ("Mazchna / Achtryn", "Canifis", "Priest in Peril, 20 combat", "6", "50"),
    ("Vannaka", "Edgeville Dungeon", "40 combat", "8", "60"),
    ("Chaeldar", "Zanaris", "Lost City, 70 combat", "10", "70"),
    ("Konar quo Maten", "Mount Karuulm", "75 combat", "18", "80"),
    ("Nieve / Steve", "Tree Gnome Stronghold", "85 combat or 99 Slayer", "12", "90"),
    ("Duradel / Kuradal", "Shilo Village", "Shilo Village; 100 combat + 50 Slayer, or 99 Slayer", "15", "100"),
    ("Krystilia", "Edgeville", "Any level, Wilderness tasks", "25", "100"),
    ("Mortimer", "Wyrmscraig Cavern", "Partly complete Fallen From Grace; 100 combat + 70 Slayer, or 99 Slayer", "modifier only", "120"),
]

POINT_ORDER = [
    ("Block slots", "The single biggest lever. Blocks cost 90 points at Nieve and 100 at Duradel. The lists are master-specific, so rebuild yours when you switch; you get seven slots, one per 50 quest points, with the seventh behind the elite Lumbridge and Draynor diary."),
    ("Bigger and Badder", "50 points. Superior encounters carry the imbued heart and eternal gem, and can be toggled off freely."),
    ("Slayer helmet", "400 points for the helm plus the components. The imbued version is the best melee and magic head slot on task."),
    ("Extensions", "Only on tasks that already pay. Araxytes go from 60-80 to 200-250, which is worth it; metal dragons are not."),
    ("Everything else", "Slayer rings, Task Storage at 500 points, Gargoyle Smasher if you keep gargoyle tasks."),
]

MORTIMER = dict(
    live="Live since 29 July 2026. The modifiers and thresholds below are the launch values; settled community strategy is still developing.",
    unlock="Reach Wyrmscraig Cavern partway through Fallen From Grace, then have 100 combat and 70 Slayer, or 99 Slayer at any combat level.",
    points=[
        "He offers two tasks to choose from, and a third once you have completed 50 tasks for him.",
        "Every offer can carry a Mortifier: Slayer points, changed quantity, better clue rates, bonus Slayer XP, or a better superior unique roll. Mortimer gives no baseline points without the points Mortifier.",
        "Points and quantity are available immediately; clues unlock at 15 tasks, superior unique rolls at 25, Slayer XP at 40, and the third choice at 50.",
        "Skipping costs 100 points, Turael cannot reset a Mortimer task, and you only get two block slots at 120 points each.",
        "His streak is separate from normal Slayer, and he only assigns creatures with superior variants. The design is aimed at imbued-heart and eternal-gem hunters.",
        "Venators are exclusive to him and need no unlock, only The Blood Moon Rises.",
        "Task extensions carry over, but master-specific task unlocks do not. Gryphons, aquanites and basilisks are available without paying to unlock them.",
    ],
    verdict="Use Mortimer when superior drops or choosing between known tasks matter more than flexible blocks and cheap skips. Stay on Duradel for established raw-XP routing and boss tasks while Mortimer's launch strategy settles.",
)


OSRSGUIDE = "https://www.osrsguide.com/"

# Reference sites for the rail
SITE_LINKS = [
    ("OSRS Guide", OSRSGUIDE + "skilling-guides/"),
    ("Calculators", "https://07.gg/calculators"),
    ("OSRS Wiki", "https://oldschool.runescape.wiki/"),
]

# Per-skill guide on osrsguide.com; combat stats share the combat guide
GUIDE_SLUG = {
    "Attack": "osrs-combat-training-guide", "Strength": "osrs-combat-training-guide",
    "Defence": "osrs-combat-training-guide", "Hitpoints": "osrs-combat-training-guide",
    "Ranged": "osrs-ranged-guide", "Magic": "osrs-magic-guide",
    "Prayer": "osrs-prayer-guide", "Slayer": "osrs-slayer-guide",
    "Agility": "osrs-agility-guide", "Thieving": "osrs-thieving-guide",
    "Fishing": "osrs-fishing-guide", "Hunter": "osrs-hunter-guide",
    "Mining": "osrs-mining-guide", "Woodcutting": "osrs-woodcutting-guide",
    "Runecraft": "osrs-runecrafting-guide", "Farming": "osrs-farming-guide",
    "Sailing": "osrs-sailing-guide", "Smithing": "osrs-smithing-guide",
    "Crafting": "osrs-crafting-guide", "Fletching": "osrs-fletching-guide",
    "Construction": "osrs-construction-guide", "Herblore": "osrs-herblore-guide",
    "Cooking": "osrs-cooking-guide", "Firemaking": "osrs-firemaking-guide",
}

WIKI_TRAINING = {
    "Attack": "Attack_training", "Strength": "Strength_training",
    "Defence": "Defence_training", "Hitpoints": "Hitpoints",
    "Ranged": "Ranged_training", "Magic": "Magic_training",
    "Prayer": "Prayer_training", "Slayer": "Slayer_training",
    "Agility": "Agility_training", "Thieving": "Thieving_training",
    "Fishing": "Fishing_training", "Hunter": "Hunter_training",
    "Mining": "Mining_training", "Woodcutting": "Woodcutting_training",
    "Runecraft": "Runecraft_training", "Farming": "Farming_training",
    "Sailing": "Sailing_training", "Smithing": "Smithing_training",
    "Crafting": "Crafting_training", "Fletching": "Fletching_training",
    "Construction": "Construction_training", "Herblore": "Herblore_training",
    "Cooking": "Cooking_training", "Firemaking": "Firemaking_training",
    "Diaries": "Achievement_Diary",
}


def guide_links(skill_name):
    """Outside guides for a skill, shown under the page title."""
    out = []
    wiki = WIKI_TRAINING.get(skill_name)
    if wiki:
        out.append(f'<a class="glink" href="{WIKI}{wiki}" rel="noopener" target="_blank">'
                   f'Wiki guide</a>')
    slug_ = GUIDE_SLUG.get(skill_name)
    if slug_:
        out.append(f'<a class="glink" href="{OSRSGUIDE}{slug_}/" rel="noopener" '
                   f'target="_blank">OSRS Guide</a>')
    return f'<div class="glinks">{"".join(out)}</div>' if out else ""


# Live third-party panels embedded on a skill page. These load from the other
# site at view time, so they need a connection and they follow that site's
# styling, not ours.
EMBEDS = {
    "Mining": dict(
        url="https://07.gg/trackers/shooting-star",
        host="07.gg",
        note="Crashed stars land about every 90 minutes per world. Mining stardust "
             "is the most AFK training in the skill and buys the celestial ring.",
    ),
}


def starmap_script(depth=0):
    """Crash-site maps plus the tracker icon path for the client."""
    path = os.path.join(OUT, "assets", "media", "starmaps", "manifest.json")
    maps = load_object(path)
    if not maps or not all(isinstance(v, dict) and isinstance(v.get("file"), str)
                           for v in maps.values()):
        return ""
    slim = {k: {"f": v["file"]} for k, v in maps.items()}
    root = "../" if depth else ""
    return ("<script>window.STARMAPS=" + json.dumps(slim, separators=(",", ":"))
            + ";window.STARMAPROOT=" + json.dumps(root + "assets/media/starmaps/")
            + ";</script>")


def embed_panel(skill_name, full=False, depth=0):
    """A live panel fed by serve.py, rendered in our own UI."""
    cfg = EMBEDS.get(skill_name)
    if not cfg:
        return ""
    return (
        f'<div class="embed{" bare" if full else ""}" id="stars" '
        f'data-root="{"../" if depth else ""}" '
        f'data-mining="{(stat_of("Mining") or {}).get("level", 0)}">'
        f'<div class="ehead"><a class="cometlink" href="{"../" if depth else ""}stars.html" '
        f'title="Open the Shooting Stars page">{COMET_SVG}</a>'
        '<span class="k">Shooting Stars</span>'
        '<span class="espace"></span>'
        '<span class="tierlbl">tier</span>'
        '<select class="tierpick" id="tiermin" aria-label="Minimum star tier"><option value="1">10 Mining &middot; T1</option><option value="2">20 Mining &middot; T2</option><option value="3">30 Mining &middot; T3</option><option value="4">40 Mining &middot; T4</option><option value="5">50 Mining &middot; T5</option><option value="6">60 Mining &middot; T6</option><option value="7">70 Mining &middot; T7</option><option value="8">80 Mining &middot; T8</option><option value="9">90 Mining &middot; T9</option></select>'
        '<span class="tierto">to</span>'
        '<select class="tierpick" id="tiermax" aria-label="Maximum star tier"><option value="1">10 Mining &middot; T1</option><option value="2">20 Mining &middot; T2</option><option value="3">30 Mining &middot; T3</option><option value="4">40 Mining &middot; T4</option><option value="5">50 Mining &middot; T5</option><option value="6">60 Mining &middot; T6</option><option value="7">70 Mining &middot; T7</option><option value="8">80 Mining &middot; T8</option><option value="9">90 Mining &middot; T9</option></select>'
        '<span class="estatus" id="starstatus">loading</span>'
        '<button class="refresh" id="starrefresh" type="button" title="Refresh stars" '
        'aria-label="Refresh stars">'
        '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">'
        '<path d="M13.6 8a5.6 5.6 0 1 1-1.7-4" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round"/>'
        '<path d="M13.4 1.4v3h-3" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg></button>'
        "</div>"
        + (f'<p class="enote">{e(cfg["note"])}</p>' if not full else "")
        + '<div class="starhead"><span>tier</span><span>world</span>'
        '<span>location</span><span>map</span><span>mining</span>'
        '<span>ends</span></div>'
        f'<div class="starlist{" full" if full else ""}" id="starlist" '
        f'data-limit="{99 if full else 12}"></div>'
        f'<div class="qfoot one"><a class="srclink" href="{cfg["url"]}" target="_blank" '
        f'rel="noopener"><img src="{"../" if depth else ""}assets/media/site/07gg.png" '
        f'alt="" width="14" height="14">Stars called on {e(cfg["host"])} &#8599;</a></div>'
        "</div>"
    )


SMALL_WORDS = {"of", "the", "in", "on", "at", "to", "and", "a", "an", "for", "by"}


def title_case(text):
    """Task and method names, capitalised the way the game writes them."""
    words = str(text).split()
    out = []
    for i, w in enumerate(words):
        bare = re.sub(r"[^A-Za-z]", "", w)
        if not bare:
            out.append(w)
        elif w.upper() == w and len(bare) > 1:
            out.append(w)
        elif i and bare.lower() in SMALL_WORDS:
            out.append(w.lower())
        else:
            out.append(w[0].upper() + w[1:])
    return " ".join(out)


def wiki_search(name):
    """Jump straight to the wiki page when the name matches one."""
    return ("https://oldschool.runescape.wiki/w/Special:Search?go=Go&search="
            + urllib.parse.quote(str(name)))


def wiki_link(name, page=None, cls="wl", cased=True):
    """`cased` title-cases the label; our own copy is already written properly,
    the wiki task table is not."""
    href = (f"{WIKI}{urllib.parse.quote(page.replace(' ', '_'), safe='/#')}"
            if page else wiki_search(name))
    label = title_case(name) if cased else name
    return (f'<a class="{cls}" href="{e(href)}" target="_blank" rel="noopener">'
            f'{e(label)}</a>')


POTIONS_PATH = os.path.join(OUT, "data", "potions.json")
_potion_data = load_object(POTIONS_PATH, {})
POTIONS = _potion_data.get("potions", [])
if not isinstance(POTIONS, list):
    POTIONS = []
POTIONS = [p for p in POTIONS if isinstance(p, dict)
           and all(key in p for key in ("name", "level", "xp", "inputs", "made"))
           and isinstance(p["inputs"], list) and p["inputs"]]


def potion_ladder():
    """The XP-per-potion ladder from where you are to 99: each rung is the next
    unlock that actually beats the one before it."""
    lvl = (stat_of("Herblore") or {}).get("level", 1)
    best_so_far = 0
    rungs = []
    for p in sorted(POTIONS, key=lambda x: (x["level"], -x["xp"])):
        if p["xp"] > best_so_far:
            best_so_far = p["xp"]
            rungs.append(p)

    live = [r for r in rungs if r["level"] >= lvl] or rungs[-1:]
    current = [r for r in rungs if r["level"] <= lvl]
    if current:
        live = [current[-1]] + [r for r in live if r["level"] > lvl]

    cells = []
    for r in live:
        now = r["level"] <= lvl
        cells.append(
            f'<span class="rung{" now" if now else ""}">'
            f'<span class="rl">{r["level"]}</span>'
            f'<span class="rn">{e(r["name"])}</span>'
            f'<span class="rx">{r["xp"]:g} XP</span></span>')

    return ('<div class="ladder"><span class="k">Fastest ladder to 99</span>'
            f'<div class="rungs">{"".join(cells)}</div>'
            '<p class="lede2">Actions per hour barely change between potions, so '
            'the highest XP per potion is the fastest. Each rung is the next '
            'unlock worth switching to.</p></div>')


def potion_section():
    """Every potion you can make, priced live in the browser."""
    if not POTIONS:
        return ""
    lvl = (stat_of("Herblore") or {}).get("level", 1)

    rows = []
    duplicate_names = {p["name"] for p in POTIONS
                       if sum(q["name"] == p["name"] for q in POTIONS) > 1}
    for p in sorted(POTIONS, key=lambda x: x["level"]):
        ing = ", ".join(f'{i["name"]}' + (f' x{i["qty"]}' if i["qty"] > 1 else "")
                        for i in p["inputs"])
        label = p["name"]
        if label in duplicate_names:
            label += f' — {p["inputs"][-1]["name"]}'
        rows.append(
            f'<tr class="pot" data-level="{p["level"]}" data-xp="{p["xp"]}" '
            f'data-made="{e(p["made"])}" '
            f'data-inputs="{e(json.dumps(p["inputs"], separators=(chr(44), chr(58))))}">'
            f'<td class="req">{p["level"]}</td>'
            f'<td class="tn">{wiki_link(label, page=p["name"], cased=False)}</td>'
            f'<td class="notes">{e(ing)}</td>'
            f'<td class="rate">{p["xp"]:g}</td>'
            f'<td class="rate gpxp">-</td>'
            f'<td class="rate profit">-</td></tr>')

    return (
        '<div class="potbar">'
        '<span class="k">Live GE prices</span>'
        '<span class="espace"></span>'
        '<span class="estatus" id="potstatus">loading</span>'
        '<button class="refresh" id="potrefresh" type="button" title="Refresh prices" '
        'aria-label="Refresh prices">'
        '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">'
        '<path d="M13.6 8a5.6 5.6 0 1 1-1.7-4" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round"/>'
        '<path d="M13.4 1.4v3h-3" fill="none" stroke="currentColor" stroke-width="1.7" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg></button>'
        "</div>"
        '<div class="potpick" id="potpick"></div>'
        + potion_ladder()
        + '<div class="tablewrap"><div class="tablescroll">'
        f'<table class="pottable" id="pottable" data-level="{lvl}" data-skill="Herblore"><thead><tr><th>Lvl</th><th>Potion</th>'
        '<th>Ingredients</th><th>XP</th><th>GP/XP</th><th>Profit each</th>'
        '</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div></div>'
        '<p class="lede2">Prices come straight from the OSRS Wiki real-time price API when the '
        'page opens, so they are current rather than baked in. Profit assumes you '
        'sell what you make.</p>'
    )


def slayer_summary():
    """Block / never-unlock / skip lists at a glance."""
    by = {}
    for t in SLAYER_TASKS:
        by.setdefault(t["tag"], []).append(t)

    def chips(tag):
        return "".join(
            f'<a class="tchip {tag}" href="{e(wiki_search(t["name"]))}" target="_blank" '
            f'rel="noopener" title="{e(t["rec"])}">{e(title_case(t["name"]))}'
            f'<span>w{t["weight"]}</span></a>'
            for t in sorted(by.get(tag, []), key=lambda x: -int(x["weight"] or 0)))

    return (
        '<div class="vsum">'
        '<div class="vrow"><span class="verdict block">block</span>'
        f'<div class="vchips">{chips("block")}</div></div>'
        '<div class="vrow"><span class="verdict lock">never unlock</span>'
        f'<div class="vchips">{chips("lock")}</div></div>'
        '<div class="vrow"><span class="verdict skip">skip</span>'
        f'<div class="vchips">{chips("skip")}</div></div>'
        '<p class="vnote">This table is for Duradel: blocks cost 100 points and skips cost '
        '30. Nieve has different task weights, extra assignments and 90-point blocks; '
        'block lists do not transfer. w is the task weight, so blocking a heavy task saves '
        'more rolls than blocking a rare one.</p>'
        "</div>"
    )


def slayer_sections():
    """Extra sections rendered on the Slayer page only."""
    order = {"do": 0, "mixed": 1, "skip": 2, "block": 3, "lock": 4}
    label = {"do": "do", "mixed": "depends", "skip": "skip",
             "block": "block", "lock": "never unlock"}
    rows = []
    for t in sorted(SLAYER_TASKS, key=lambda x: (order[x["tag"]], -int(x["weight"] or 0))):
        why = t["cons"] if t["tag"] in ("skip", "block", "lock") else t["pros"]
        meta = f'lvl {t["level"]} &middot; weight {t["weight"]}'
        level_match = re.search(r"\d+", t["level"])
        level = int(level_match.group()) if level_match else 0
        rows.append(
            f'<tr class="tk {t["tag"]}" data-tag="{t["tag"]}" '
            f'data-order="{order[t["tag"]]}" data-weight="{int(t["weight"] or 0)}" '
            f'data-xp="{rate_value(t["xp"]):g}" data-level="{level}">'
            f'<td class="tv"><span class="verdict {t["tag"]}">{label[t["tag"]]}</span></td>'
            f'<td class="tn">{wiki_link(t["name"])}<span class="tmeta">{meta}</span>'
            f'<span class="tmeta xp">{e(t["xp"])}</span></td>'
            f'<td class="notes"><b>{e(t["rec"])}</b> {e(why)}</td></tr>')

    counts = {k: sum(1 for t in SLAYER_TASKS if t["tag"] == k) for k in order}
    filters = "".join(
        f'<button class="tf" type="button" data-f="{k}" aria-pressed="false">'
        f'{label[k]}<span>{counts[k]}</span></button>' for k in order if counts[k])
    controls = (
        '<div class="tcontrols">'
        f'<button class="tf on" type="button" data-f="all" aria-pressed="true">'
        f'all<span>{len(SLAYER_TASKS)}</span></button>'
        f'{filters}'
        '<span class="tspace"></span>'
        '<span class="tsortlbl">sort</span>'
        '<button class="ts on" type="button" data-s="verdict" aria-pressed="true">verdict</button>'
        '<button class="ts" type="button" data-s="weight" aria-pressed="false">how often</button>'
        '<button class="ts" type="button" data-s="xp" aria-pressed="false">XP/hr</button>'
        '<button class="ts" type="button" data-s="level" aria-pressed="false">level</button>'
        "</div>")

    tasks_table = (
        f'{controls}<div class="tablewrap"><div class="tablescroll">'
        '<table class="tasktable" id="tasktable"><thead><tr><th>Verdict</th><th>Task</th>'
        '<th>What the wiki says</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div></div>'
    )

    masters = "".join(
        f'<tr><td class="tn">{wiki_link(n, cased=False)}</td><td>{e(loc)}</td>'
        f'<td class="notes">{e(req)}</td>'
        f'<td class="rate">{e(pts)}</td><td class="req">{e(blk)}</td></tr>'
        for n, loc, req, pts, blk in MASTERS)
    masters_table = (
        '<div class="tablewrap"><div class="tablescroll">'
        '<table class="mtable"><thead><tr><th>Master</th><th>Where</th>'
        '<th>Requirement</th><th>Points/task</th><th>Block cost</th></tr></thead>'
        f'<tbody>{masters}</tbody></table></div></div>'
    )

    points = "".join(f'<li><b>{e(n)}</b>. {annotate(d, depth=1, skip=("Slayer",))}</li>'
                     for n, d in POINT_ORDER)

    mort = (
        '<div class="panel warn"><div class="k">Not Live Yet</div>'
        f'<p>{e(MORTIMER["live"])}</p></div>'
        f'<p class="lede2">{annotate(MORTIMER["unlock"], depth=1, skip=("Slayer",))}</p>'
        "<ul>" + "".join(f"<li>{e(x)}</li>" for x in MORTIMER["points"]) + "</ul>"
        f'<div class="panel"><div class="k">Where It Fits</div><p>{e(MORTIMER["verdict"])}</p></div>'
    )

    return [
        ("tasks", "Which Tasks to Do, Skip or Block",
         '<p class="lede2">Verdicts and rates are the wiki\'s, for Duradel tasks. '
         'Sorted by verdict, then by how often the task comes up. Weight is its share '
         'of the assignment roll, so a heavy task you dislike is worth a block slot '
         'more than a rare one.</p>' + tasks_table),
        ("points", "Spending Slayer Points", f"<ol class=\"pts\">{points}</ol>"),
        ("masters", "The Masters", masters_table),
        ("mortimer", "Mortimer, the New Master", mort),
    ]


# Bird house tiers: (log, Crafting level, Hunter level, Hunter XP per house)
BIRDHOUSE_TIERS = [
    ("Regular", 5, 5, 280), ("Oak", 15, 14, 420), ("Willow", 25, 24, 560),
    ("Teak", 35, 34, 700), ("Maple", 45, 44, 820), ("Mahogany", 50, 49, 960),
    ("Yew", 60, 59, 1020), ("Magic", 75, 74, 1140), ("Redwood", 90, 89, 1200),
]

BIRDHOUSE_STOPS = [
    ("Verdant Valley", "Two spots south of the Museum Camp, next to each other."),
    ("Mushroom Meadow", "West of the ancient shroom, straight north of the magic mushtree."),
    ("Sticky Swamp", "By the Tar Swamp entrance, south from the mushtree."),
]


def birdhouse_box():
    """The run itself, at whatever tier the account can build."""
    craft = (stat_of("Crafting") or {}).get("level", 1)
    hunt = (stat_of("Hunter") or {}).get("level", 1)
    if not STATS:
        return ""

    usable = [t for t in BIRDHOUSE_TIERS if t[1] <= craft and t[2] <= hunt]
    best = usable[-1] if usable else BIRDHOUSE_TIERS[0]
    nxt = next((t for t in BIRDHOUSE_TIERS
                if t[1] > craft or t[2] > hunt), None)

    per_run = best[3] * 4
    per_hour = round(per_run * 60 / 55)

    stops = "".join(
        f'<li><b>{e(name)}</b>. {e(note)}</li>' for name, note in BIRDHOUSE_STOPS)

    nxt_line = ""
    if nxt:
        need = []
        if nxt[1] > craft:
            need.append(f"{nxt[1]} Crafting")
        if nxt[2] > hunt:
            need.append(f"{nxt[2]} Hunter")
        nxt_line = (f'<p class="gap">Next tier: <b>{e(nxt[0])}</b> at '
                    f'{e(" and ".join(need))}, worth {nxt[3] * 4:,} per run.</p>')

    return (
        '<div class="panel"><div class="k">Birdhouse run</div>'
        f'<h3>{e(best[0])} bird houses &mdash; {per_run:,} Hunter XP a run</h3>'
        f'<p>Four houses, emptied and rebuilt every 50 minutes. That is about '
        f'{per_hour:,} XP an hour for two minutes of work, and it stacks with '
        f'whatever else you are doing. Seeds are 10 low-level ones per house, so '
        f'use whatever is cheapest.</p>'
        f'{nxt_line}'
        '<p class="gap"><b>The route.</b> Digsite pendant to Fossil Island, then the '
        'magic mushtree at the House on the Hill to hop between stops:</p>'
        f'<ol class="bhstops">{stops}</ol>'
        '<p class="gap">Carry a hammer, chisel, logs, seeds and five clockworks: '
        'building the next house while walking saves a trip. '
        f'<a href="{WIKI}Bird_house_trapping" target="_blank" rel="noopener">'
        'Full guide on the wiki &#8599;</a></p>'
        '<div class="subpanel"><div class="k">While drift netting</div>'
        '<p>Both happen on Fossil Island, so the run costs you about three minutes '
        'of fishing. Set the houses before you dive, so the 50-minute timer runs while '
        'you are underwater.</p>'
        '<ol class="bhstops">'
        '<li>Surface and climb out. You land on the small island, which has a '
        '<b>bank</b>: restock nets, seeds and logs here rather than teleporting.</li>'
        '<li>Row back to the Museum Camp, then run south to the '
        '<b>Verdant Valley</b> mushtree. Two houses sit right by it.</li>'
        '<li>Take the mushtree to <b>Mushroom Meadow</b>; the third house is north of it.</li>'
        '<li>Take the mushtree to <b>Sticky Swamp</b>; the fourth house is by the '
        'Tar Swamp entrance. Bring an axe and rake the first time you go.</li>'
        '<li>Mushtree back to <b>Verdant Valley</b>, run north to the camp, row out '
        'and dive.</li>'
        "</ol>"
        '<p class="gap">Two things that pay for themselves: <b>20,000 numulites</b> '
        'for permanent drift net access, so surfacing never costs you the daily fee, '
        'and <b>flippers</b> for sprinting underwater.</p>'
        "</div></div>"
    )


MILESTONES = [60, 62, 70, 72, 74, 75, 80, 85, 90, 95, 99]
COMBAT_SKILLS = ["Attack", "Strength", "Defence", "Hitpoints", "Ranged", "Magic"]
SHORT = {"Attack": "Att", "Strength": "Str", "Defence": "Def", "Hitpoints": "HP",
         "Ranged": "Rng", "Magic": "Mag", "Hunter": "Hunter", "Smithing": "Smith",
         "Agility": "Agi"}


def climb(route, xp_now, xp_target):
    """Hours and carried XP for one stretch of a route."""
    hours, carried, pos = 0.0, {}, xp_now
    for leg in legs_for(route, xp_now):
        span = min(leg["xp"], max(0, xp_target - pos))
        if span <= 0:
            break
        got = (span / leg["rate"]) if leg["rate"] else 0
        hours += got
        for name, rate in CARRIES.get(leg["method"], {}).items():
            carried[name] = carried.get(name, 0) + got * rate
        pos += span
    return hours, carried


def carry_panel(skill_name, pick=None):
    """Where the other skills end up while you train this one.

    Only for routes that train more than one thing. The rates are the ones the
    route tables use, so these numbers agree with Which Path.
    """
    from hiscores import combat_level

    st = stat_of(skill_name)
    opts = PATHS.get(skill_name)
    if not st or not opts:
        return ""

    route = opts["hybrid"]
    carries = {}
    for _, method, _ in route:
        for name, rate in (CARRIES.get(method) or {}).items():
            if name != skill_name and stat_of(name):
                carries[name] = max(carries.get(name, 0), rate)
    if not carries:
        return ""

    others = ([n for n in COMBAT_SKILLS if n in carries]
              + sorted(n for n in carries if n not in COMBAT_SKILLS))
    combat = any(n in COMBAT_SKILLS for n in others)
    base = {n: (stat_of(n) or {}).get("xp") or 0 for n in SKILL_NAMES}

    def row(label, hours, xp):
        levels = {n: level_at(min(v, MAX_XP)) for n, v in xp.items()}
        cells = "".join(f'<td class="rate">{levels[n]}</td>' for n in others)
        cl = (f'<td class="rate afkgap">{combat_level(levels)}</td>'
              if combat else "")
        hrs = f"{hours:,.0f}h" if hours else "—"
        return (f'<tr><td class="tn">{label}</td>'
                f'<td class="rate">{hrs}</td>{cells}{cl}</tr>')

    rows = [row("now", 0, base)]
    for goal in MILESTONES:
        if goal <= st["level"]:
            continue
        hours, carried = climb(route, st["xp"] or 0, XP_TABLE[goal])
        xp = dict(base)
        xp[skill_name] = max(xp[skill_name], XP_TABLE[goal])
        for name, amount in carried.items():
            xp[name] = min(xp[name] + amount, MAX_XP)
        rows.append(row(f"{skill_name} {goal}", hours, xp))

    if len(rows) < 2:
        return ""

    heads = "".join(f"<th>{e(SHORT.get(n, n))}</th>" for n in others)
    return (
        '<h2 id="alongtheway">Along the Way</h2>'
        f'<p class="savednote">Training with {e(route_label(route))} trains '
        + e(", ".join(others[:-1]) + (" and " if len(others) > 1 else "")
            + others[-1])
        + ' alongside it. Where those land as you go'
        + (', and what your combat level reads at each point.'
           if combat else '.') + '</p>'
        '<div class="tablewrap"><div class="tablescroll">'
        '<table class="pathtable carry"><thead><tr><th>At</th><th>Hours</th>'
        f'{heads}{"<th>Cmb</th>" if combat else ""}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div></div>')


def three_ways_panel(skill_name):
    """Speed, Realistic and AFK for this one skill, costed from today's XP.

    The paths page prices carries and ordering; this is the same three routes
    read on their own, so a skill page answers "how long, and doing what" at a
    glance.
    """
    st = stat_of(skill_name)
    opts = PATHS.get(skill_name)
    if not st or not opts:
        return ""
    xp = st["xp"] or 0
    if xp >= MAX_XP or all(rate == 0 for key, _, _ in PATH_META
                           for _, _, rate in opts[key]):
        return ""
    cols = []
    for key, label, _ in PATH_META:
        legs = merged_legs(legs_for(opts[key], xp))
        hours = sum(leg["hours"] for leg in legs)
        items = "".join(
            f'<li><span class="wm">{e(leg["method"])}</span>'
            f'<span class="wb">{leg["from"]}–{leg["to"]}</span>'
            f'<span class="wr">{rate_span(leg["rates"])}</span>'
            f'<span class="wh">{fmt_hours(leg["hours"])}</span></li>'
            for leg in legs)
        cols.append(
            f'<div class="way {key}"><div class="whead"><h3>{e(label)}</h3>'
            f'<b class="wt">{hours:,.0f}h</b></div>'
            f'<span class="wp">{e((PATH_PROFILE.get(key) or ("",))[0])}</span>'
            f'<ol class="wlegs">{items}</ol></div>')
    return ('<section class="ways" id="ways"><div class="k">Three Ways to 99</div>'
            f'<div class="waygrid">{"".join(cols)}</div>'
            '<p class="wnote">From your XP today at each route\'s rates, before '
            'anything another skill hands over. <a class="wl" href="../paths.html">'
            'Which Path</a> prices those carries and the order.</p></section>')


def build_skill_page(skill, prev_skill, next_skill):
    name = skill["name"]
    pick = skill.get("pick")
    parts = []

    parts.append('<a class="backlink" href="../index.html" title="Back to the plan" '
                 'aria-label="Back to the plan">'
                 '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">'
                 '<path d="M9.5 3.5 5 8l4.5 4.5" fill="none" stroke="currentColor" '
                 'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
                 '</svg></a>')
    parts.append(f'<div class="kick">{e(skill["group"])}</div>')
    parts.append('<div class="page-head">'
                 f'{icon(name, depth=1, cls="lg")}'
                 f'<h1 class="page">{e(name)}</h1></div>')
    parts.append(f'<p class="lede">{annotate(skill["phase"], depth=1, skip=(name,))}</p>')
    parts.append(guide_links(name))

    pr = progress(skill)
    if pr:
        cur, nxt, pct, done = pr
        st = stat_of(name) or {}
        xp = st.get("xp") or 0
        togo = max(0, xp_for_level(nxt) - xp) if nxt else 0
        goals = milestones(skill)
        frm = max([g for g in goals if g <= cur] or [1])
        head = (f'<b class="big num lit"{level_style(cur)} '
                f'data-skill-level="{e(name)}">{cur}</b>'
                + (f'<span class="goal" data-skill-goal="{e(name)}" '
                   f'data-goals="{e(",".join(map(str, goals)))}" data-prefix="of " '
                   f'data-done="target met">of {nxt}</span>' if nxt else
                   '<span class="goal done">target met</span>'))
        bar = (f'<span class="prog wide"><span class="fill lit" '
               f'style="width:{pct}%;{bar_colours(frm, cur)}" data-skill-bar="{e(name)}" '
               f'data-goals="{e(",".join(map(str, goals)))}" '
               f'data-from="{frm}" data-goal="{nxt or 99}"></span></span>')
        facts = [f'<span><i>XP</i> <b class="num">{xp:,}</b></span>']
        if nxt:
            facts.append(f'<span><i>To {nxt}</i> <b class="num">{togo:,}</b></span>')
        parts.append('<div class="livebox"><div class="k">Your Level</div>'
                     f'<div class="lvlrow">{head}</div>{bar}'
                     f'<div class="facts">{"".join(facts)}</div></div>')

    parts.append(embed_panel(name, depth=1))
    if name == "Hunter":
        parts.append(birdhouse_box())
    if name == "Herblore":
        parts.append('<h2 id="potions">Potions, Priced Live</h2>')
        parts.append(potion_section())

    parts.append('<div class="pillrow">')
    done_cls = " done" if skill.get("done") else ""
    parts.append(f'<span class="pill{done_cls}"><span class="pl">Target</span>'
                 f'<span class="pv">{e(skill["target"])}</span></span>')
    if pick:
        parts.append(f'<span class="pill pick"><span class="pl">Method</span>'
                     f'<span class="pv">{e(pick)}</span></span>')
    parts.append(f'<span class="pill"><span class="pl">Options</span>'
                 f'<span class="pv">{len(skill["methods"])}</span></span>')
    parts.append("</div>")

    chosen = next((m for m in skill["methods"] if m[0] == pick), None) if pick else None
    detail = f"<p>{annotate(chosen[3], depth=1, skip=(name,))}</p>" if chosen else ""
    tline = tier_line(pick, name) if pick else None
    if tline:
        detail += f'<p class="tiernow">{tline}</p>'
    if pick and skill.get("pick_note"):
        detail += ("<p class=\"gap\">"
                   f'{annotate(skill["pick_note"], depth=1, skip=(name,))}</p>')
    psrc = media_path(METHOD_MEDIA.get(pick, ""), depth=1) if pick else None
    pimg = (f'<img class="thumb lg" id="pickimg" src="{psrc}" alt="" loading="lazy">'
            if psrc else '<img class="thumb lg" id="pickimg" alt="" hidden>')
    parts.append(f'<div class="panel pick withpic" id="pickpanel"{"" if pick else " hidden"}>'
                 '<div class="k">Your Pick</div>'
                 f'<div class="pickbody">{pimg}'
                 f'<div><h3 id="pickname">{e(pick or "")}</h3>'
                 f'<div id="pickdetail">{detail}</div></div></div></div>')
    if not skill.get("done"):
        parts.append(f'<div class="panel warn" id="nopick"{" hidden" if pick else ""}>'
                     '<div class="k">Open Decision</div>'
                     '<h3>No Method Locked In</h3>'
                     "<p>The plan sets a target here but does not name a method. "
                     "Pick one with the box at the end of any row below.</p></div>")

    parts.append(three_ways_panel(name))
    parts.append(carry_panel(name, pick))

    if name == "Slayer":
        parts.append('<h2 id="blocklist">Block and Skip List</h2>')
        parts.append(slayer_summary())

    parts.append('<h2 id="methods">Methods</h2>')
    parts.append(bonus_controls(name))
    rec = best_for_level(skill["methods"], name)
    st_now = stat_of(name)
    if rec and st_now:
        rrate = next((m[2] for m in skill["methods"] if m[0] == rec), "")
        parts.append(f'<p class="savednote">At {st_now["level"]} {e(name)}, the best '
                     f'option open to you is <b>{e(rec)}</b>'
                     + (f' ({e(rrate)}/hr).' if rrate and rrate[0].isdigit() else '.')
                     + ' Locked rows need a higher level.</p>')
    else:
        parts.append('<p class="savednote" id="savednote">Tap the box on any row to '
                     'make it your method.</p>')
    parts.append(method_table(skill["methods"], pick, skill_name=name))

    if skill.get("notes"):
        parts.append('<h2 id="notes">Notes</h2>')
        parts.append("<ul>")
        for n in skill["notes"]:
            parts.append(f"  <li>{annotate(n, depth=1, skip=(name,))}</li>")
        parts.append("</ul>")

    if name == "Slayer":
        for anchor, title, body in slayer_sections():
            parts.append(f'<h2 id="{anchor}">{e(title)}</h2>')
            parts.append(body)

    nav = []
    if prev_skill:
        nav.append(f'<a class="prev" href="{slug(prev_skill["name"])}.html">'
                   f'<span class="d">Previous</span>'
                   f'<span class="n">{e(prev_skill["name"])}</span></a>')
    else:
        nav.append('<span class="ghost"></span>')
    if next_skill:
        nav.append(f'<a class="next" href="{slug(next_skill["name"])}.html">'
                   f'<span class="d">Next</span>'
                   f'<span class="n">{e(next_skill["name"])}</span></a>')
    else:
        nav.append('<span class="ghost"></span>')
    parts.append(f'<div class="prevnext">{"".join(nav)}</div>')

    maps = starmap_script(depth=1) if name == "Mining" else ""
    return page(name, "\n".join(parts), active=slug(name), depth=1,
                skill_name=name, head_extra=maps)


PAIRS = {"Fishing": "Hunter", "Hunter": "Fishing"}


def card_head(s, tag="span"):
    """Icon, name, level/target and (once linked) a progress bar."""
    done_cls = " done" if s.get("done") else ""
    card_target = re.sub(r"\s*\(.*\)", "", s["target"])
    pr = progress(s)
    if pr:
        cur, nxt, pct, done = pr
        goals = milestones(s)
        frm = max([g for g in goals if g <= cur] or [1])
        done_cls = " done" if done else ""
        lstyle = level_style(cur)
        right = (f'<span class="lvl lit"{lstyle} data-skill-level="{e(s["name"])}">{cur}</span>'
                 f'<span class="arrow">&rarr;</span>'
                 f'<span class="target{done_cls}" data-skill-goal="{e(s["name"])}" '
                 f'data-goals="{e(",".join(map(str, goals)))}">{nxt}</span>'
                 if not done else
                 f'<span class="lvl lit"{lstyle} data-skill-level="{e(s["name"])}">{cur}</span>')
        bar = (f'<span class="prog"><span class="fill lit" '
               f'style="width:{pct}%;{bar_colours(frm, cur)}" data-skill-bar="{e(s["name"])}" '
               f'data-goals="{e(",".join(map(str, goals)))}" '
               f'data-from="{frm}" data-goal="{nxt or 99}"></span></span>')
    else:
        right = f'<span class="target{done_cls}">{e(card_target)}</span>'
        bar = ""
    return (f'<span class="row">{icon(s["name"])}'
            f'<span class="name">{e(s["name"])}</span>'
            f'<span class="lvls">{right}</span></span>{bar}')


def skill_card(s):
    return (
        f'  <a class="card" href="skills/{slug(s["name"])}.html">'
        f'{card_head(s)}</a>'
    )


def pair_card(a, b):
    """Two skills trained by one method live in a single panel."""
    halves = []
    for s in (a, b):
        halves.append(
            f'    <a class="half" href="skills/{slug(s["name"])}.html">'
            f'{card_head(s)}</a>'
        )
    return '  <div class="card pair">\n' + "\n".join(halves) + "\n  </div>"


def build_stars_page():
    cfg = EMBEDS["Mining"]
    body = [
        '<div class="kick">Live Tracker</div>',
        '<div class="page-head"><span class="comethead">' + COMET_SVG
        + '</span><h1 class="page">Shooting Stars</h1></div>',
        f'<p class="lede">{e(cfg["note"])}</p>',
        # The callers all post to 07.gg, so the tracker itself is the panel.
        '<iframe class="siteframe" src="https://07.gg/trackers/shooting-star" '
        'title="Shooting star tracker on 07.gg" loading="lazy" '
        'referrerpolicy="no-referrer"></iframe>',
        '<p class="note">Called worlds come from '
        '<a class="wl" href="https://07.gg/trackers/shooting-star" '
        'target="_blank" rel="noopener">07.gg</a>. If the frame stays blank the '
        'tracker is refusing to be embedded; open it directly.</p>',
        '<h2 id="how">How the Tiers Work</h2>',
        '<ul>'
        '<li>Tier 1 needs 10 Mining, then ten levels per tier to tier 9 at 90.</li>'
        '<li>Seven minutes per layer. Tier 9 lasts longest; a dying star is not '
        'worth the hop.</li>'
        '<li>Stardust buys the celestial ring, which gives an invisible +4 Mining '
        'boost, at Dusuri\'s Star Shop.</li>'
        '<li>A house telescope narrows the next landing to a 24-, 9-, or 2-minute '
        'window.</li>'
        '</ul>',
    ]
    return page("Shooting Stars", "\n".join(body), depth=0)


# Skilling outfits: what each piece is called, what the set does, and where it
# comes from. `bonus` points at the matching entry in BONUSES so completing a
# set switches on that skill's rate toggle.
OUTFITS = [
    dict(name="Prospector Kit", skill="Mining", wiki="Prospector_kit", bonus=0,
         icon="prospector", effect="+2.5% Mining XP",
         source="180 golden nuggets at Motherlode Mine",
         pieces=["Prospector helmet", "Prospector jacket", "Prospector legs",
                 "Prospector boots"]),
    dict(name="Angler's Outfit", skill="Fishing", wiki="Angler%27s_outfit", bonus=0,
         icon="angler", effect="+2.5% Fishing XP, excluding drift net fishing and deep-sea trawling",
         source="Fishing Trawler",
         pieces=["Angler hat", "Angler top", "Angler waders", "Angler boots"]),
    dict(name="Lumberjack Outfit", skill="Woodcutting", wiki="Lumberjack_outfit", bonus=0,
         icon="lumberjack", effect="+2.5% Woodcutting XP",
         source="Temple Trekking rewards",
         pieces=["Lumberjack hat", "Lumberjack top", "Lumberjack legs",
                 "Lumberjack boots"]),
    dict(name="Pyromancer Outfit", skill="Firemaking", wiki="Pyromancer_outfit", bonus=0,
         icon="pyromancer", effect="+2.5% Firemaking XP",
         source="Wintertodt reward cart",
         pieces=["Pyromancer hood", "Pyromancer garb", "Pyromancer robe",
                 "Pyromancer boots"]),
    dict(name="Carpenter's Outfit", skill="Construction", wiki="Carpenter%27s_outfit",
         bonus=0, icon="carpenter", effect="+2.5% Construction XP",
         source="2,000 carpenter points from Mahogany Homes",
         pieces=["Carpenter's helmet", "Carpenter's shirt", "Carpenter's trousers",
                 "Carpenter's boots"]),
    dict(name="Smiths' Uniform", skill="Smithing", wiki="Smiths%27_Uniform", bonus=[0, 1],
         icon="worn-equipment",
         effect="About +20% Foundry XP/hr; anvil actions 5 ticks to 4",
         source="15,000 Foundry Reputation at Giants' Foundry",
         pieces=["Smiths tunic", "Smiths trousers", "Smiths gloves", "Smiths boots"]),
    dict(name="Guild Hunter Outfit", skill="Hunter", wiki="Guild_hunter_outfit", bonus=0,
         icon="hunterguild", effect="+2.5% catch rate; exact XP/hr effect unknown",
         source="1/50 from non-basic Hunters' Rumour loot sacks",
         pieces=["Guild hunter headwear", "Guild hunter top", "Guild hunter legs",
                 "Guild hunter boots"]),
    dict(name="Raiments of the Eye", skill="Runecraft", wiki="Raiments_of_the_Eye",
         bonus=0, icon="eye", effect="Up to 60% bonus runes, no extra XP",
         source="1,350 abyssal pearls from Guardians of the Rift",
         pieces=["Hat of the eye", "Robe top of the eye", "Robe bottoms of the eye",
                 "Boots of the eye"]),
    dict(name="Rogue's Outfit", skill="Thieving", wiki="Rogue_equipment", bonus=0,
         icon="rogue", effect="Doubles pickpocket loot, no XP change",
         source="Rogues' Den wall safes",
         pieces=["Rogue mask", "Rogue top", "Rogue trousers", "Rogue gloves",
                 "Rogue boots"]),
    dict(name="Farmer's Outfit", skill="Farming", wiki="Farmer%27s_outfit", bonus=0,
         icon="farmer", effect="+2.5% Farming XP", source="400 points at Tithe Farm",
         pieces=["Farmer's strawhat", "Farmer's jacket", "Farmer's boro trousers",
                 "Farmer's boots"]),
    dict(name="Graceful Outfit", skill="Agility", wiki="Graceful_outfit", bonus=None,
         icon="graceful", effect="Run energy restores faster, no XP change",
         source="260 marks of grace from rooftops",
         pieces=["Graceful hood", "Graceful top", "Graceful legs", "Graceful gloves",
                 "Graceful boots", "Graceful cape"]),
    dict(name="Zealot's Robes", skill="Prayer", wiki="Zealot%27s_robes", bonus=None,
         icon="zealot", effect="Chance of extra XP when burying or scattering",
         source="Gold chests in the Shade Catacombs",
         pieces=["Zealot's helm", "Zealot's robe top", "Zealot's robe bottom",
                 "Zealot's boots"]),
]


def piece_label(setname, piece):
    """Drop whatever the piece repeats from the set name, so the label reads
    'hat' rather than "Angler's hat"."""
    stop = {"outfit", "kit", "uniform", "robes", "raiments", "of", "the", "eye",
            "guild", "s"}
    owned = {w.strip("'s").lower() for w in setname.replace("'s", "").split()} | stop
    words = piece.split()
    while words and words[0].strip("'s").lower() in owned:
        words.pop(0)
    while words and words[-1].lower() in {"of", "the", "eye"}:
        words.pop()
    label = " ".join(words).strip()
    for lead in ("'s ", "' ", "'"):
        if label.startswith(lead):
            label = label[len(lead):]
            break
    label = label.strip()
    return (label[0].lower() + label[1:]) if label else piece


def outfit_section():
    """Every skilling outfit, ticked off a piece at a time."""
    rows = []
    for o in OUTFITS:
        sk = o["skill"]
        maxed = (stat_of(sk) or {}).get("level", 0) >= 99
        pieces = "".join(
            f'<label class="piece"><input type="checkbox" class="piecebox" '
            f'data-set="{e(o["name"])}" data-piece="{e(pc)}" '
            f'title="{e(pc)}"><span>{e(piece_label(o["name"], pc))}</span></label>'
            for pc in o["pieces"])
        bonuses = o["bonus"] if isinstance(o["bonus"], list) else [o["bonus"]]
        bonus_attr = (f' data-skill="{e(sk)}" data-bonuses="'
                      f'{"|".join(str(x) for x in bonuses)}"'
                      if o["bonus"] is not None else "")
        rows.append(
            f'<div class="outfit{" spent" if maxed else ""}" '
            f'data-set="{e(o["name"])}" data-total="{len(o["pieces"])}"{bonus_attr}>'
            f'<img class="ofit" src="assets/media/site/{o["icon"]}.png" alt="" '
            f'loading="lazy">'
            f'<span class="oname">{icon(sk)}'
            f'<a href="{WIKI}{o["wiki"]}" target="_blank" rel="noopener">'
            f'{e(o["name"])}</a></span>'
            f'<span class="ocount">0/{len(o["pieces"])}</span>'
            f'<span class="oeffect">{e(o["effect"])}</span>'
            f'<span class="osource">{e(o["source"])}</span>'
            f'<span class="opieces">{pieces}</span>'
            "</div>")
    return ('<p class="lede2">Tick each piece as you get it. The calculator models '
            "full-set effects only; partial-set bonuses stay a checklist until the "
            'set is complete.</p>'
            f'<div class="outfits">{"".join(rows)}</div>')


# Sustained rate for the method the plan actually picks, and whether those
# hours pay you, break even, or cost gold. Used to estimate what is left.
# Planning rate per skill for the index cards, and whether the method pays.
# The rate is the Realistic route's first leg, so the front page and Which
# Path quote the same hours.
SKILL_RATE = {
    "Slayer": (30_000, "pays"), "Attack": (60_000, "pays"),
    "Strength": (60_000, "pays"), "Defence": (60_000, "pays"),
    "Hitpoints": (0, "free"), "Ranged": (300_000, "costs"),
    "Magic": (130_000, "costs"), "Prayer": (500_000, "costs"),
    "Runecraft": (40_000, "pays"), "Agility": (53_000, "pays"),
    "Thieving": (170_000, "pays"), "Hunter": (120_000, "pays"),
    "Mining": (70_000, "neutral"), "Fishing": (72_000, "neutral"),
    "Woodcutting": (86_000, "neutral"), "Sailing": (20_000, "neutral"),
    "Firemaking": (226_000, "pays"), "Herblore": (350_000, "costs"),
    "Crafting": (300_000, "costs"), "Construction": (500_000, "costs"),
    "Smithing": (165_000, "neutral"), "Cooking": (470_000, "costs"),
    "Fletching": (0, "free"), "Farming": (0, "free"),
}

# The order, and why each block sits where it does.
MAX_ORDER = [
    dict(title="Slayer to 99",
         why="Every hour here is also Attack, Strength, Defence and Hitpoints, "
             "and Ranged and Magic on cannon and barrage tasks. Bank the bones: "
             "they are most of your Prayer.",
         skills=["Slayer"]),
    dict(title="Finish combat",
         why="Whatever Slayer did not already carry. Hallowfell at the maniacal "
             "monkeys finishes the melee stats, chins or a Venator bow finish "
             "Ranged, barrage finishes Magic, Prayer burns the bones you banked, "
             "and Hitpoints arrives on its own.",
         caveat="Slayer's carry is already subtracted, which is why Hitpoints "
                "is free and Magic is nearly so.",
         skills=["Attack", "Strength", "Defence", "Ranged", "Magic", "Prayer",
                 "Hitpoints"]),
    dict(title="The grinds that pay",
         why="Long, but they fund everything after them. Runecraft first: 77 turns "
             "blood runes into income for the rest of the account.",
         skills=["Runecraft", "Agility", "Thieving", "Hunter", "Firemaking"]),
    dict(title="Slow gatherers",
         why="The tail. Roughly break-even, so do them once the bank is fat and "
             "nothing else depends on them.",
         skills=["Mining", "Fishing", "Woodcutting", "Sailing"]),
    dict(title="Buyables last",
         why="Fast, and paid for by the blocks above. Cheapest per hour first so "
             "the bank drains most slowly.",
         skills=["Cooking", "Smithing", "Construction", "Crafting", "Herblore"]),
]


def hours_left(skill_name):
    """Hours to 99 at the plan's method, from the live XP."""
    rate = SKILL_RATE.get(skill_name, (0, ""))[0]
    st = stat_of(skill_name)
    if not st or not rate:
        return None
    left = max(0, xp_for_level(99) - (st["xp"] or 0))
    return left / rate if left else 0


def post_diary_rows(key="hybrid"):
    """Where every skill stands once the Diary Cape is done, and what is left.

    The block is titled post-diary-cape, so it has no business costing the
    levels you buy on the way there. The floor for each skill is the higher of
    where you are now and what the hardest elite tier asks of it. Rates and
    carries are the route model's, so this and Which Path cannot disagree.
    """
    wall = dict(diary_wall("Elite"))
    out = []
    for name, opts in PATHS.items():
        st = stat_of(name)
        if not st:
            continue
        floor = min(99, wall.get(name, 1))
        xp = max(st["xp"] or 0, XP_TABLE[floor])
        out.append(dict(skill=name, level=level_at(xp), route=opts[key], key=key,
                        method=opts[key][0][1], rate=opts[key][0][2], legs=[],
                        need=max(0, MAX_XP - xp), xp=xp, hours=0, left=0,
                        carried=0, gives=[], diaries=[], order=0,
                        arrive=level_at(xp)))
    rows, total, _ = walk(plan_order(out), diaries=False)
    return {r["skill"]: r for r in rows}, total


def max_order_block(phase, after):
    chips = []
    total = 0
    for name in phase["skills"]:
        sk = next((x for x in SKILLS if x["name"] == name), None)
        if not sk:
            continue
        row = after.get(name)
        hrs = row["hours"] if row else None
        done = row is not None and row["need"] <= 0
        if hrs:
            total += hrs
        money = SKILL_RATE.get(name, (0, ""))[1]
        chips.append(
            f'<a class="mo {money}{" met" if done else ""}" '
            f'href="skills/{slug(name)}.html">{icon(name)}'
            f'<span class="mn">{e(name)}</span>'
            + (f'<span class="ml">{row["level"]}</span>' if row else "")
            + ('<span class="mh done">99</span>' if done else
               (f'<span class="mh">{hrs:.0f}h</span>' if hrs else
                '<span class="mh">free</span>'))
            + "</a>")
    head = (f'<b>{e(phase["title"])}</b>'
            + (f'<span class="mtot">{total:.0f} hours</span>' if total else ""))
    caveat = (f'<p class="mcaveat">{annotate(phase["caveat"])}</p>'
              if phase.get("caveat") else "")
    return (f'  <li>{head}'
            f'<p class="mwhy">{annotate(phase["why"])}</p>{caveat}'
            f'<div class="mochips">{"".join(chips)}</div></li>')


# Things that make one grind pay into another. Requirements are the wiki's,
# checked rather than remembered: the infernal tools are all "not boostable",
# which is why they have to be planned for rather than boosted into.
FEEDERS = [
    dict(name="Infernal pickaxe", wiki="Infernal_pickaxe", skill="Mining",
         gives="Smithing", needs=[("Smithing", 85), ("Mining", 61)],
         note="A third of the ore you mine combusts for about half the "
              "smelting XP. Wants ore, so it does nothing at Motherlode."),
    dict(name="Infernal axe", wiki="Infernal_axe", skill="Woodcutting",
         gives="Firemaking", needs=[("Firemaking", 85), ("Woodcutting", 61)],
         note="A third of your logs burn as you cut them, for half the "
              "Firemaking XP. On teaks that is most of a Firemaking 99."),
    dict(name="Infernal harpoon", wiki="Infernal_harpoon", skill="Fishing",
         gives="Cooking", needs=[("Cooking", 85), ("Fishing", 75)],
         note="A third of your catch cooks itself for half the Cooking XP."),
    dict(name="Daeyalt essence", wiki="Daeyalt_essence", skill="Runecraft",
         gives="Runecraft", needs=[("Mining", 60)], quest="Sins of the Father",
         note="Mine it yourself; it does not trade. Fifty per cent more "
              "Runecraft XP per essence, and it stacks with Ourania."),
    dict(name="Guardians of the Rift", wiki="Guardians_of_the_Rift",
         skill="Runecraft", gives="Mining and Crafting", needs=[("Runecraft", 27)],
         note="Pays passive Mining and Crafting the whole time you are in it."),
    dict(name="Zalcano", wiki="Zalcano", skill="Mining", gives="Smithing",
         needs=[("Mining", 70), ("Smithing", 70)], quest="Song of the Elves",
         note="Mining and Smithing off the same fight, plus crystal shards."),
    dict(name="Tempoross", wiki="Tempoross", skill="Fishing", gives="Cooking",
         needs=[("Fishing", 35)],
         note="The fish it pays out cook straight into a Cooking 99."),
    dict(name="Wintertodt", wiki="Wintertodt", skill="Firemaking",
         gives="supplies", needs=[("Firemaking", 50)],
         note="Herbs, ore and gems in the reward crates, which feed the "
              "buyables you would otherwise pay for."),
    dict(name="Birdhouse runs", wiki="Bird_house_trapping", skill="Hunter",
         gives="Hunter", needs=[("Hunter", 5), ("Crafting", 5)],
         note="Runs on its own clock while you do something else. Most of a "
              "Hunter 99 for a few minutes every fifty."),
    dict(name="Herb runs", wiki="Herb_patch", skill="Farming", gives="Herblore",
         needs=[("Farming", 32)],
         note="The cheapest Herblore there is: grow the second ingredient "
              "instead of buying it."),
]


def feeder_state(f):
    """Whether the levels are there, and what is missing if not."""
    short = []
    for name, level in f["needs"]:
        st = stat_of(name)
        if not st or st["level"] < level:
            short.append((name, level, st["level"] if st else 0))
    return short


def feeders_section():
    rows = []
    for f in FEEDERS:
        short = feeder_state(f)
        needs = " · ".join(
            f'<span class="fneed{" short" if (n, lv) in [(a, b) for a, b, _ in short] else " ok"}">'
            f'{icon(n)}{lv}</span>' for n, lv in f["needs"])
        quest = (f'<span class="fneed quest">{e(f["quest"])}</span>'
                 if f.get("quest") else "")
        rows.append(
            f'<div class="feeder{" locked" if short else ""}">'
            f'<a class="fname" href="{WIKI}{f["wiki"]}" target="_blank" '
            f'rel="noopener">{e(f["name"])}</a>'
            f'<span class="fpays">{icon(f["skill"])}{e(f["skill"])} '
            f'<i>pays</i> {e(f["gives"])}</span>'
            f'<span class="fneeds">{needs}{quest}</span>'
            f'<span class="fnote">{annotate(f["note"])}</span>'
            "</div>")
    open_now = sum(1 for f in FEEDERS if not feeder_state(f))
    return (f'<p class="lede2">{open_now} of {len(FEEDERS)} are open to you now. '
            'These are the reason the order matters: reach the requirement '
            'before the grind it pays into, not after, or the free XP lands on '
            'levels you already bought.</p>'
            f'<div class="feeders">{"".join(rows)}</div>')


def h2(anchor, title, ico=None):
    """Section heading, with the matching game icon where there is one."""
    mark = (f'<img class="h2ico" src="{ico}" alt="" width="20" height="20">'
            if ico else "")
    return f'<h2 id="{anchor}">{mark}{e(title)}</h2>'


# The least-attention option for each skill. `every` is how long you can leave
# it between clicks, which is the thing that actually makes something AFK.
# Rates are the wiki's for the idle version of the method, not the active one.
AFK = [
    dict(skill="Hunter", method="Birdhouse runs", level="5+", every=50 * 60,
         xp="4-5k", note="Four houses, then nothing for 50 minutes. Nothing else "
                         "in the game asks so little of you."),
    dict(skill="Attack", method="Nightmare Zone, absorptions", level="Quest reqs",
         every=20 * 60, xp="~100k",
         note="Absorption potions and a rock cake in a normal rumble. The game "
              "stops you after 20 idle minutes; one click starts it again. Works "
              "for Strength, Defence and Hitpoints too."),
    dict(skill="Ranged", method="Nightmare Zone, absorptions and Venator bow",
         level="80 (Quest reqs)", every=20 * 60, xp="90-150k",
         note="Same rumble, same timer. A Venator bow bounces between the bosses "
              "for 145k; a blowpipe manages 90k and a magic shortbow 70k."),
    dict(skill="Magic", method="Blood Burst at the Bandit Camp lodge", level="68",
         every=20 * 60, xp="150-230k",
         note="Two tiles inside the lodge door every bandit comes to you, and blood "
              "spells heal more than they hit. Auto-retaliate for 20 minutes at a "
              "time; Blood Barrage at 92 is 230k. Costs the runes with nothing back."),
    dict(skill="Mining", method="Shooting Stars", level="10+", every=7 * 60,
         xp="24-31k", note="One click per layer, seven minutes apart. Stardust "
                           "buys the celestial ring on the side. Motherlode Mine "
                           "is twice the XP for a click every half minute, which "
                           "is what the AFK route uses."),
    dict(skill="Woodcutting", method="Rosewood trees", level="92 (79 Sailing)",
         every=270,
         xp="85-90k", note="Drumstick Isle. A tree stands for four and a half "
                           "minutes, the longest of any tree, and there is no bank "
                           "to distract you. Redwoods at 90 are the version without "
                           "the boat."),
    dict(skill="Strength", method="Gemstone Crab", level="1+", every=10 * 60,
         xp="30-60k", note="Shared health pool in Varlamore, so it never dies on "
                           "you and never stops being aggressive. Slower than NMZ; "
                           "no quests needed."),
    dict(skill="Fishing", method="Anglerfish", level="82", every=6 * 60,
         xp="15-39k", note="From a boat off Piscarilius the spot never moves, so an "
                           "inventory is six to seven minutes of nothing. Monkfish "
                           "from a raft at 62 is the same trick at 37k."),
    dict(skill="Firemaking", method="Bonfires", level="1+", every=150,
         xp="135-233k", note="Add the whole inventory to a forester's campfire and "
                             "it burns through unattended. Maples 135k, magic 202k, "
                             "redwood 233k."),
    dict(skill="Sailing", method="Shipwreck salvaging with crew", level="15 (42 better)",
         every=3 * 60, xp="15-40k",
         note="Crewmates on the hooks keep salvaging while you sort. Jagex "
              "measured 35-40k an hour at 97 with two crew on dragon hooks; expect "
              "less with worse crew and wrecks."),
    dict(skill="Smithing", method="Cannonballs", level="35", every=3 * 60,
         xp="14-28k", note="A full inventory of steel bars smelts itself. Profitable, "
                           "and the rate is as bad as it looks. The double ammo "
                           "mould doubles it; the ancient furnace at 87 Sailing doubles "
                           "it again. Dart tips are one click a minute for 53-80k and "
                           "still profit, which is what the AFK route uses."),
    dict(skill="Hunter", method="Maniacal monkey deadfalls", level="60 (+ MM2)",
         every=28, xp="51-110k",
         note="Bait a boulder with a banana from the back of a stunted gorilla, "
              "reset it when it drops. A basket of bananas is a 50-minute trip. "
              "The active AFK option once birdhouses are running."),
    dict(skill="Runecraft", method="Blood runes at Arceuus", level="77", every=90,
         xp="~36k", note="Mine essence, chip it, run it to the altar. Low attention, "
                         "it pays, and it drips Mining and Crafting."),
    dict(skill="Thieving", method="Stealing valuables", level="50", every=60,
         xp="72-105k", note="Pickpocket a house key, then loot the house while the "
                            "owner is out. Both halves are about one click a minute."),
    dict(skill="Agility", method="Colossal Wyrm advanced course", level="62",
         every=20, xp="~42k",
         note="Six clicks per lap and two 20-second stretches of nothing. The "
              "only course that lets you look away."),
    dict(skill="Crafting", method="Cutting amethyst", level="83", every=35,
         xp="~165k", note="One click and it cuts the inventory on its own. The only "
                          "Crafting worth calling AFK, and it roughly breaks even."),
    dict(skill="Construction", method="Shipwrights' workbench", level="1+",
         every=29, xp="250-440k",
         note="Hull parts at Deepfin Point: an inventory of planks builds itself "
              "for up to 29 seconds while you wait. Half the XP per plank, but the "
              "parts sell back."),
    dict(skill="Cooking", method="Karambwans, one click per inventory", level="30",
         every=67, xp="218-273k",
         note="The Hosidius kitchen without the tick timing: one click, then 67 "
              "seconds of cooking. Fish are the same idea at 165-285k."),
    dict(skill="Herblore", method="Potions, an inventory at a time", level="varies",
         every=17, xp="~250k",
         note="Fourteen potions per inventory, 17 seconds a batch. Never idle for "
              "long, but the rate makes it the shortest grind on the page."),
    dict(skill="Prayer", method="Bonecrusher and ash sanctifier", level="Passive",
         every=None, xp="passive",
         note="Zero clicks: bones and ashes convert while you are killing things "
              "for something else. Around 40k an hour at the monkeys. When you "
              "do sit down to train it, a gilded altar offers an inventory of "
              "bones one by one from a single click, about 270k with dragon bones."),
]

NO_AFK = [
    ("Slayer", "Individual tasks can be low effort with a Venator bow, but the skill itself is not."),
    ("Agility", "The Colossal Wyrm course is as idle as it gets: 20 seconds at a time, twice a lap."),
    ("Herblore", "Potions are made an inventory at a time, by hand. Seventeen seconds is the ceiling."),
]


def afk_rows():
    rows = []
    for a in sorted(AFK, key=lambda x: -(x["every"] or 10 ** 9)):
        if a["every"] is None:
            gap = "no clicks"
        elif a["every"] >= 60 * 60:
            gap = f'{a["every"] // 3600}h'
        elif a["every"] >= 60:
            gap = f'{a["every"] // 60} min'
        else:
            gap = f'{a["every"]}s'
        st = stat_of(a["skill"])
        lvl = f'<span class="al">{st["level"]}</span>' if st else ""
        src = media_path(METHOD_MEDIA.get(a["method"], ""))
        pic = (f'<img class="thumb" src="{src}" alt="" loading="lazy">'
               if src else '<span class="thumb blank"></span>')
        rows.append(
            f'<tr><td class="pic">{pic}</td>'
            f'<td class="tn"><a href="skills/{slug(a["skill"])}.html">'
            f'{icon(a["skill"])}{e(a["skill"])}</a>{lvl}</td>'
            f'<td>{e(a["method"])}</td>'
            f'<td class="req">{e(a["level"])}</td>'
            f'<td class="rate afkgap">{e(gap)}</td>'
            f'<td class="rate">{e(a["xp"])}</td>'
            f'<td class="notes">{annotate(a["note"])}</td></tr>')
    return "".join(rows)


def build_afk_page():
    body = [
        '<div class="kick">Least attention wins</div>',
        '<div class="page-head">'
        + '<img class="icon lg" src="assets/media/site/skills-icon.png" alt="">'
        + '<h1 class="page">The AFK Path</h1></div>',
        '<p class="lede">Sorted by how long you can leave it alone, which is the '
        'only measure that matters here. XP rates are the price you pay for that. '
        'The <a class="wl" href="paths.html#afk">AFK path</a> turns these into a '
        'full route to the cape.</p>',
        '<div class="tablewrap"><div class="tablescroll">'
        '<table class="afktable"><thead><tr>'
        '<th class="pic"><span class="sr">Image</span></th><th>Skill</th>'
        '<th>Method</th><th>Needs</th><th>Click every</th><th>XP/hr</th>'
        '<th>Why</th></tr></thead>'
        f'<tbody>{afk_rows()}</tbody></table></div></div>',
        '<h2 id="none">Where AFK Runs Out</h2>',
        '<p class="lede2">Being honest about these is more useful than pretending. '
        'If you want to idle, spend the time on the table above and come back to '
        'these when you can pay attention.</p>',
        '<ul>' + "".join(f'<li><b>{e(n)}</b>. {e(why)}</li>' for n, why in NO_AFK)
        + "</ul>",
        '<h2 id="stack">Stacking Them</h2>',
        '<ul>'
        '<li>Birdhouses run on a 50-minute timer that ignores what else you are '
        'doing, so they stack with everything on this page.</li>'
        '<li>A bonecrusher and ash sanctifier turn any combat into passive Prayer, '
        'including the Nightmare Zone and crab hours.</li>'
        '<li>Drift net fishing trains Fishing and Hunter at once, and the birdhouse '
        'run fits inside its downtime.</li>'
        '<li>The 20-minute combat timer is the ceiling: Nightmare Zone and the '
        'bandit lodge both stop when it runs out, so one click every twenty '
        'minutes is as idle as combat gets.</li>'
        "</ul>",
    ]
    return page("The AFK Path", "\n".join(body), depth=0, wide=True)


# Three ways to spend the remaining XP. Each route is a list of legs:
# (unlocked at, method, xp/hr). Real training is staged, so one method to 99
# was always a fiction. A leg is used from its level until the next one opens.
# Rates are the OSRS Wiki training guides' as of September 2026, taken at the
# level band each leg covers; where the wiki quotes a range, the solo figure
# without alt accounts is the one used.
#
# fast   Speed. The best rate there is: tick manipulation, stacked monkeys,
#        bought XP, and the Wilderness where it is clearly faster.
# hybrid Realistic. A pace you can hold for hundreds of hours: no tick
#        manipulation, no runners, methods that pay for themselves or nearly
#        do. What most people who actually max end up doing.
# afk    AFK. The least attention that still trains the skill. Where a skill
#        has no idle option, it holds the least demanding thing available.
PATHS = {
    "Slayer": dict(
        # The account starts at 95 combat, so Nieve/Steve is the real first
        # master. Slayer ~85 is the carry model's approximate 100-combat point;
        # only then do the Duradel rates become available.
        fast=[(1, "Nieve, cannon and burst tasks", 38_000),
              (85, "Duradel, barrage tasks", 70_000)],
        hybrid=[(1, "Nieve, cannon and burst", 30_000),
                (85, "Duradel, cannon and barrage", 50_000)],
        afk=[(1, "Nieve, Venator bow on long tasks", 25_000),
             (85, "Duradel, Venator bow on long tasks", 35_000)]),
    "Attack": dict(
        fast=[(1, "Sulphur Nagua", 110_000),
              (75, "Hallowfell on maniacal monkeys", 220_000)],
        hybrid=[(1, "Slayer tasks", 60_000),
                (75, "Hallowfell on maniacal monkeys, auto-retaliate", 150_000)],
        afk=[(1, "Nightmare Zone, absorptions", 95_000)]),
    "Strength": dict(
        fast=[(1, "Sulphur Nagua", 110_000),
              (75, "Hallowfell on maniacal monkeys", 220_000)],
        hybrid=[(1, "Slayer tasks", 60_000),
                (75, "Hallowfell on maniacal monkeys, auto-retaliate", 150_000)],
        afk=[(1, "Nightmare Zone, absorptions", 95_000)]),
    "Defence": dict(
        fast=[(1, "Sulphur Nagua", 110_000),
              (75, "Hallowfell on maniacal monkeys", 220_000)],
        hybrid=[(1, "Slayer tasks", 60_000),
                (75, "Hallowfell on maniacal monkeys, auto-retaliate", 150_000)],
        afk=[(1, "Nightmare Zone, absorptions", 95_000)]),
    "Hitpoints": dict(
        fast=[(1, "Arrives with combat", 0)],
        hybrid=[(1, "Arrives with combat", 0)],
        afk=[(1, "Arrives with combat", 0)]),
    "Ranged": dict(
        fast=[(1, "Red chinchompas on maniacal monkeys", 450_000),
              (85, "Black chinchompas on maniacal monkeys", 650_000)],
        hybrid=[(1, "Red chinchompas, low-intensity stacking", 300_000),
                (80, "Venator bow on maniacal monkeys", 200_000)],
        afk=[(1, "Nightmare Zone, absorptions and blowpipe", 90_000),
             (80, "Nightmare Zone, absorptions and Venator bow", 145_000)]),
    "Magic": dict(
        fast=[(1, "Ice Burst on maniacal monkeys", 300_000),
              (94, "Ice Barrage on maniacal monkeys", 400_000)],
        hybrid=[(1, "Ice Burst on Slayer tasks", 130_000),
                (94, "Ice Barrage on Slayer tasks", 180_000)],
        afk=[(1, "Blood Burst at the Bandit Camp lodge", 150_000),
             (92, "Blood Barrage at the Bandit Camp lodge", 230_000)]),
    "Prayer": dict(
        fast=[(1, "Gilded altar, superior dragon bones", 1_300_000)],
        hybrid=[(1, "Chaos altar, dragon bones", 500_000)],
        afk=[(1, "Gilded altar, one click per inventory", 270_000)]),
    "Runecraft": dict(
        fast=[(1, "Lava runes, Magic Imbue", 65_000),
              (75, "Lava runes, giant pouch", 80_000),
              (85, "Lava runes, colossal pouch", 100_000),
              (90, "Aether runes", 100_000)],
        hybrid=[(1, "Guardians of the Rift", 40_000),
                (75, "Ourania altar, daeyalt essence", 85_000)],
        afk=[(1, "Guardians of the Rift", 40_000),
             (77, "Blood runes at Arceuus", 36_000),
             (90, "Soul runes at Arceuus", 44_000)]),
    "Agility": dict(
        fast=[(1, "Wilderness Agility Course", 55_000),
              (62, "Hallowed Sepulchre, floors 1–2", 56_000),
              (72, "Hallowed Sepulchre, floors 1–3", 69_000),
              (77, "Hallowed Sepulchre, floors 1–4", 80_000),
              (87, "Hallowed Sepulchre, all five floors", 98_000)],
        hybrid=[(1, "Seers' Village rooftop", 53_000),
                (62, "Hallowed Sepulchre, floors 1–2", 50_000),
                (72, "Hallowed Sepulchre, floors 1–3", 62_000),
                (77, "Hallowed Sepulchre, floors 1–4", 72_000),
                (87, "Hallowed Sepulchre, all five floors", 86_000)],
        afk=[(1, "Colossal Wyrm basic course", 31_000),
             (62, "Colossal Wyrm advanced course", 42_000)]),
    "Thieving": dict(
        fast=[(1, "Stealing artefacts", 165_000),
              (65, "Blackjacking", 230_000),
              (84, "Rogues' Castle chests", 280_000)],
        hybrid=[(1, "Stealing artefacts", 170_000),
                (91, "Pyramid Plunder, final room", 270_000)],
        afk=[(1, "Stealing valuables", 85_000)]),
    "Mining": dict(
        fast=[(1, "3-tick granite", 110_000)],
        hybrid=[(1, "Volcanic Mine", 70_000),
                (85, "Volcanic Mine, crystal pickaxe", 86_000)],
        afk=[(1, "Motherlode Mine, upper level", 55_000),
             (90, "Motherlode Mine, full upgrades", 62_000)]),
    "Fishing": dict(
        fast=[(1, "Barbarian Fishing, 3-tick", 85_000),
              (71, "2-tick harpooning", 95_000),
              (85, "2-tick harpooning, crystal harpoon", 117_000)],
        hybrid=[(1, "Drift Net Fishing", 72_000),
                (70, "Drift Net Fishing", 88_000)],
        afk=[(1, "Karambwans", 29_000), (62, "Monkfish from a raft", 37_000)]),
    "Woodcutting": dict(
        fast=[(1, "1.5-tick teaks", 194_000),
              (80, "1.5-tick teaks", 208_000),
              (90, "1.5-tick teaks", 222_000)],
        hybrid=[(1, "Sulliuscep", 86_000),
                (77, "Bloodwood trees", 170_000)],
        afk=[(1, "Blisterwood tree", 69_000),
             (92, "Rosewood trees", 87_000)]),
    "Firemaking": dict(
        fast=[(1, "Burning yew logs", 300_000),
              (75, "Burning magic logs", 450_000),
              (90, "Burning redwood logs", 520_000)],
        hybrid=[(1, "Wintertodt", 226_000),
                (80, "Wintertodt", 258_000),
                (90, "Wintertodt", 290_000)],
        afk=[(1, "Campfire, maple logs", 135_000),
             (75, "Campfire, magic logs", 200_000),
             (90, "Campfire, redwood logs", 233_000)]),
    "Cooking": dict(
        fast=[(1, "1-tick karambwans", 740_000),
              (80, "1-tick karambwans", 810_000),
              (90, "1-tick karambwans", 880_000)],
        hybrid=[(1, "Jugs of wine", 470_000)],
        afk=[(1, "Karambwans, one click per inventory", 218_000),
             (80, "Karambwans, one click per inventory", 251_000)]),
    "Crafting": dict(
        fast=[(1, "Red d'hide bodies", 390_000),
              (84, "Black d'hide bodies", 435_000)],
        hybrid=[(1, "Battlestaves", 300_000)],
        afk=[(1, "Glassblowing", 90_000),
             (83, "Cutting amethyst", 160_000)]),
    "Smithing": dict(
        fast=[(1, "Blast Furnace gold bars", 380_000)],
        hybrid=[(1, "Giants' Foundry, steel and mithril", 165_000),
                (70, "Giants' Foundry, mithril and adamant", 198_000),
                (85, "Giants' Foundry, adamant and rune", 253_000)],
        afk=[(1, "Mithril dart tips", 53_000),
             (74, "Adamant dart tips", 66_000),
             (89, "Rune nails", 80_000)]),
    "Herblore": dict(
        fast=[(1, "Zamorak brews", 437_000),
              (85, "Ancient brews", 520_000),
              (89, "Armadyl brews", 560_000)],
        hybrid=[(1, "Super restores", 350_000)],
        afk=[(1, "Potions, an inventory at a time", 250_000)]),
    "Construction": dict(
        fast=[(1, "Mahogany tables", 900_000),
              (77, "Gnome benches", 1_100_000)],
        hybrid=[(1, "Oak dungeon doors", 500_000)],
        afk=[(1, "Shipwrights' workbench, hull parts", 400_000)]),
    "Hunter": dict(
        fast=[(1, "Razor-backed kebbits", 130_000),
              (72, "Hunters' Rumours", 160_000),
              (91, "Hunters' Rumours, master tier", 200_000)],
        hybrid=[(1, "Razor-backed kebbits", 120_000),
                (72, "Hunters' Rumours", 150_000),
                (91, "Hunters' Rumours, master tier", 185_000)],
        afk=[(1, "Maniacal monkey deadfalls", 59_000),
             (80, "Maniacal monkey deadfalls", 82_000),
             (90, "Maniacal monkey deadfalls", 96_000)]),
    "Sailing": dict(
        fast=[(1, "Tempor Tantrum, Marlin rank", 24_000),
              (55, "Jubbly Jive, Marlin rank", 85_000),
              (72, "Gwenith Glide, Marlin rank", 180_000)],
        hybrid=[(1, "Courier tasks", 20_000),
                (55, "Jubbly Jive, Shark rank", 78_000),
                (65, "Rellekka and Etceteria courier route", 95_000),
                (76, "Lunar Isle courier route", 140_000)],
        afk=[(1, "Shipwreck salvaging with crew", 15_000),
             (60, "Salvaging, Cabin Boy Jenkins on a hook", 25_000),
             (85, "Salvaging, two crew on dragon hooks", 37_000)]),
}


PATH_META = [
    ("fast", "Speed", "The fastest rate the game has for every skill: tick "
                      "manipulation, stacked monkeys, bought XP, and the Wilderness "
                      "where it is clearly quicker. This route asks the most of you."),
    ("hybrid", "Realistic", "A pace you can hold for hundreds of hours. No tick "
                            "manipulation, no runners, and methods that pay for "
                            "themselves or come close. This is how most people who "
                            "actually max get there."),
    ("afk", "AFK", "The least attention that still trains the skill: one click every "
                   "minute to every twenty. The rate is the price of that. Where a "
                   "skill has no idle option, it holds the least demanding thing "
                   "available."),
]

# What each route asks of you, in three words each. Shown under the route
# title so the totals above can be read as a trade rather than a ranking.
PATH_PROFILE = {
    "fast": ("the top rate, whatever it asks", "buys XP", "some Wilderness"),
    "hybrid": ("ordinary clicking", "pays or breaks even", "safe"),
    "afk": ("a click a minute or less", "cheap", "safe"),
    "opt": ("mixed", "priced by the hour", "the search's pick"),
}


# What a method hands to other skills per hour. Rough, but ignoring it makes
# every total wrong: drift net trains two skills at once, Slayer trains six.
# Hitpoints is a third of the combat XP for melee and ranged, and a share of
# the damage for Magic.
CARRIES = {
    "Nieve, cannon and burst tasks": {
        "Attack": 12_000, "Strength": 12_000, "Defence": 12_000,
        "Hitpoints": 15_000, "Magic": 16_000, "Ranged": 16_000,
    },
    "Nieve, cannon and burst": {"Attack": 10_000, "Strength": 10_000,
                                 "Defence": 10_000, "Hitpoints": 13_000,
                                 "Magic": 14_000, "Ranged": 14_000},
    "Nieve, Venator bow on long tasks": {"Attack": 6_000, "Strength": 6_000,
                                          "Defence": 6_000, "Hitpoints": 12_000,
                                          "Ranged": 22_000},
    "Duradel, barrage tasks": {"Attack": 20_000, "Strength": 20_000,
                               "Defence": 20_000, "Hitpoints": 25_000,
                               "Magic": 35_000},
    "Duradel, cannon and barrage": {"Attack": 18_000, "Strength": 18_000,
                                    "Defence": 18_000, "Hitpoints": 22_000,
                                    "Magic": 25_000, "Ranged": 20_000},
    "Duradel, Venator bow on long tasks": {"Attack": 8_000, "Strength": 8_000,
                                            "Defence": 8_000, "Hitpoints": 16_000,
                                            "Ranged": 32_000},
    "Slayer tasks": {"Hitpoints": 20_000},
    "Sulphur Nagua": {"Hitpoints": 37_000},
    "Hallowfell on maniacal monkeys": {"Hitpoints": 73_000, "Prayer": 30_000},
    "Hallowfell on maniacal monkeys, auto-retaliate": {"Hitpoints": 50_000,
                                                       "Prayer": 25_000},
    "Nightmare Zone, absorptions": {"Hitpoints": 32_000},
    "Red chinchompas on maniacal monkeys": {"Hitpoints": 150_000, "Prayer": 30_000},
    "Black chinchompas on maniacal monkeys": {"Hitpoints": 215_000, "Prayer": 30_000},
    "Red chinchompas, low-intensity stacking": {"Hitpoints": 100_000,
                                                "Prayer": 25_000},
    "Venator bow on maniacal monkeys": {"Hitpoints": 66_000, "Prayer": 25_000},
    "Nightmare Zone, absorptions and blowpipe": {"Hitpoints": 30_000},
    "Nightmare Zone, absorptions and Venator bow": {"Hitpoints": 48_000},
    "Ice Burst on maniacal monkeys": {"Hitpoints": 100_000, "Prayer": 30_000},
    "Ice Barrage on maniacal monkeys": {"Hitpoints": 130_000, "Prayer": 30_000},
    "Ice Burst on Slayer tasks": {"Hitpoints": 43_000},
    "Ice Barrage on Slayer tasks": {"Hitpoints": 60_000},
    "Blood Burst at the Bandit Camp lodge": {"Hitpoints": 50_000},
    "Blood Barrage at the Bandit Camp lodge": {"Hitpoints": 75_000},
    "Guardians of the Rift": {"Magic": 8_000, "Mining": 3_700, "Crafting": 2_000},
    "Blood runes at Arceuus": {"Mining": 5_700, "Crafting": 4_200},
    "Soul runes at Arceuus": {"Mining": 5_700, "Crafting": 4_100},
    "Barbarian Fishing, 3-tick": {"Strength": 8_000, "Agility": 13_000},
    "Drift Net Fishing": {"Hunter": 105_000},
    "Wintertodt": {"Woodcutting": 15_000},
    "Herbiboar": {"Herblore": 3_300},
}


MAX_XP = xp_for_level(99)

DIARY_REQS_PATH = os.path.join(OUT, "data", "diary_reqs.json")
DIARY_REQS = load_object(DIARY_REQS_PATH, {})


def level_at(xp):
    """Level for an XP figure, capped at 99."""
    lv = 1
    for level in range(2, 100):
        if xp >= XP_TABLE[level]:
            lv = level
        else:
            break
    return lv


def legs_for(route, xp_now):
    """Split the climb to 99 at each point the route changes method."""
    legs = []
    for i, (from_level, method, rate) in enumerate(route):
        start = max(xp_now, XP_TABLE[from_level] if from_level > 1 else 0)
        nxt = route[i + 1][0] if i + 1 < len(route) else None
        stop = min(XP_TABLE[nxt] if nxt else MAX_XP, MAX_XP)
        if stop <= start:
            continue
        gained = stop - start
        legs.append({
            "method": method, "rate": rate, "xp": gained,
            "from": level_at(start), "to": level_at(stop),
            "hours": (gained / rate) if rate else 0,
        })
    return legs


PLAN_BLOCK = {}
for _i, _blk in enumerate(MAX_ORDER):
    for _j, _sk in enumerate(_blk.get("skills") or []):
        PLAN_BLOCK[_sk] = (_i, _j, _blk["title"])


def plan_order(rows):
    """The order the Max Order blocks on the front page lay out."""
    return sorted(rows, key=lambda r: PLAN_BLOCK.get(r["skill"], (99, 99, ""))[:2])


def carrier_order(rows):
    """Carriers first, then longest first.

    A method that hands XP to another skill is worth doing before the skill
    that receives it. Slayer, for example, should land its combat XP before
    the calculator charges separately for those combat levels.
    """
    naive = {r["skill"]: sum(leg["hours"] for leg in legs_for(r["route"], r["xp"]))
             for r in rows}
    need = {r["skill"]: r["need"] for r in rows}

    def rank(r):
        hands_over = any(need.get(name, 0) > 0
                         for _, method, _ in r["route"]
                         for name in CARRIES.get(method, {})
                         if name != r["skill"])
        return (0 if hands_over else 1, -naive[r["skill"]])

    return sorted(rows, key=rank)


def total_of(order):
    """Hours for one ordering. No diary work: this runs inside the search."""
    return walk(list(order), diaries=False)[1]


def best_order(rows, within_plan=False):
    """Move one skill at a time until nothing gets cheaper.

    Order changes the bill because carried XP only counts if it arrives before
    you would have paid for those levels. Seeded from both the plan order and
    the carriers-first rule, since either can be the better start.
    """
    seeds = [plan_order(rows), carrier_order(rows)]
    if within_plan:                      # reshuffle inside each block only
        seeds = [sorted(seed, key=lambda r: PLAN_BLOCK.get(r["skill"], (99,))[0])
                 for seed in seeds]

    best_seq, best = None, None
    for seed in seeds:
        order = list(seed)
        score = total_of(order)
        for _ in range(6):
            moved = False
            for i in range(len(order)):
                for j in range(len(order)):
                    if i == j:
                        continue
                    trial = list(order)
                    trial.insert(j, trial.pop(i))
                    if within_plan and [PLAN_BLOCK.get(r["skill"], (99,))[0]
                                        for r in trial] != sorted(
                            PLAN_BLOCK.get(r["skill"], (99,))[0] for r in trial):
                        continue
                    got = total_of(trial)
                    if got < score - 0.01:
                        order, score, moved = trial, got, True
            if not moved:
                break
        if best is None or score < best:
            best_seq, best = order, score
    return best_seq, best


# the wiki lists quest points alongside the skills; nothing here knows how many
# you have, so that requirement is left out and called out on the page
NOT_A_SKILL = {"Quest"}
DIARY_TIERS = sum(1 for r in DIARY_REQS.values() for t in r.values() if t)


def diary_state(levels):
    """Which diary tiers the levels alone would cover."""
    ok = set()
    for region, tiers in DIARY_REQS.items():
        for tier, reqs in tiers.items():
            wants = {sk: lv for sk, lv in reqs.items() if sk not in NOT_A_SKILL}
            if wants and all(levels.get(sk, 0) >= lv for sk, lv in wants.items()):
                ok.add(f"{region} {tier}")
    return ok


def walk(rows, diaries=True):
    """Train the list in order and record where every skill ends up.

    Sequential rather than an average: a skill trained late has already been
    carried by everything above it, which is the whole point of the ordering.
    """
    xp = {r["skill"]: r["xp"] for r in rows}
    # seed from every skill, not just the ones still being trained: a diary
    # tier can hang on a 99 that is already banked
    levels = {name: (stat_of(name) or {}).get("level", 0) for name in SKILL_NAMES}
    levels.update({r["skill"]: r["level"] for r in rows})
    have = diary_state(levels) if diaries else set()

    total = 0
    for i, r in enumerate(rows, 1):
        r["order"] = i
        r["arrive"] = level_at(min(xp[r["skill"]], MAX_XP))
        r["carried"] = max(0, min(xp[r["skill"]], MAX_XP) - r["xp"])

        r["left"] = max(0, MAX_XP - xp[r["skill"]])
        r["legs"] = legs_for(r["route"], xp[r["skill"]])
        r["hours"] = sum(leg["hours"] for leg in r["legs"])
        r["method"] = (" → ".join(leg["method"] for leg in merged_legs(r["legs"]))
                       or "Carried to 99 by the steps above")
        r["rate"] = r["legs"][0]["rate"] if r["legs"] else 0
        total += r["hours"]

        xp[r["skill"]] = max(xp[r["skill"]], MAX_XP)
        levels[r["skill"]] = 99

        handed = {}
        for leg in r["legs"]:
            for name, rate in CARRIES.get(leg["method"], {}).items():
                if name == r["skill"] or name not in xp:
                    continue
                handed[name] = handed.get(name, 0) + leg["hours"] * rate

        gives = []
        for name, amount in handed.items():
            before = levels[name]
            xp[name] += amount
            levels[name] = level_at(min(xp[name], MAX_XP))
            if levels[name] > before:
                gives.append((name, levels[name]))
        r["gives"] = gives

        if diaries:
            unlocked = diary_state(levels) - have
            have |= unlocked
            r["diaries"] = sorted(unlocked)

    return rows, total, have


def rows_for(choice, order="carrier", diaries=False):
    """Hours to 99 per skill, given a route key per skill."""
    out = []
    for name, opts in PATHS.items():
        st = stat_of(name)
        if not st:
            continue
        key = choice.get(name, "hybrid")
        route = opts[key]
        out.append(dict(skill=name, level=st["level"], route=route, key=key,
                        method=route[0][1], rate=route[0][2], legs=[],
                        need=max(0, MAX_XP - (st["xp"] or 0)),
                        xp=st["xp"] or 0, hours=0, left=0, carried=0,
                        gives=[], diaries=[], order=0, arrive=st["level"]))

    if order == "best":
        out, _ = best_order(out)
    elif order == "plan":
        out = plan_order(out)
    elif order == "plan-best":
        out, _ = best_order(out, within_plan=True)
    else:
        out = carrier_order(out)
    rows, total, _ = walk(out, diaries=diaries)
    return rows, total


def path_hours(key, **kw):
    return rows_for({name: key for name in PATHS}, **kw)


def optimal_mix():
    """The best method per skill once cross-skill XP is priced in.

    Picking each skill's fastest method in isolation need not be the best plan:
    a slower method can still win overall when it hands enough XP to another
    skill. Search the three routes' options one skill at a time until nothing
    improves.
    """
    keys = [k for k, _, _ in PATH_META]
    choice = {name: "fast" for name in PATHS}
    best = rows_for(choice)[1]

    for _ in range(8):
        moved = False
        for name in PATHS:
            for k in keys:
                if k == choice[name]:
                    continue
                trial = dict(choice, **{name: k})
                total = rows_for(trial)[1]
                if total < best - 0.01:
                    best, choice, moved = total, trial, True
        if not moved:
            break
    return choice, best


def fmt_rate(rate):
    """An hourly rate as the tables print it: 65k, 1.3M, or free."""
    if not rate:
        return "free"
    if rate >= 1_000_000:
        return f"{rate / 1_000_000:.1f}M".replace(".0M", "M")
    return f"{rate // 1000}k"


def merged_legs(legs):
    """Consecutive legs with the same method read as one band.

    A route can change rate without changing method, because the wiki quotes
    the rate by level. That is worth modelling and not worth printing twice.
    """
    out = []
    for leg in legs:
        if out and out[-1]["method"] == leg["method"]:
            out[-1] = dict(out[-1], to=leg["to"], xp=out[-1]["xp"] + leg["xp"],
                           hours=out[-1]["hours"] + leg["hours"],
                           rates=out[-1]["rates"] + [leg["rate"]])
        else:
            out.append(dict(leg, rates=[leg["rate"]]))
    return out


def rate_span(rates):
    """One rate, or the first and last when a band's rate climbs with level."""
    rates = [r for r in rates if r]
    if not rates:
        return "free"
    if len(set(rates)) == 1:
        return fmt_rate(rates[0])
    return f"{fmt_rate(rates[0])}→{fmt_rate(rates[-1])}"


def fmt_hours(hours):
    if not hours:
        return "free"
    return "<1h" if hours < 0.5 else f"{hours:,.0f}h"


def legs_cell(row):
    """The method, or the staged list of them with the band each one covers."""
    legs = merged_legs(row["legs"])
    if not legs:
        return f'<span class="one">{e(row["method"])}</span>'
    if len(legs) == 1:
        return f'<span class="one">{e(legs[0]["method"])}</span>'
    return "".join(
        f'<span class="leg">{e(leg["method"])}'
        f'<i>{leg["from"]}–{leg["to"]} · {fmt_hours(leg["hours"])}</i></span>'
        for leg in legs)


def route_label(route):
    """A route as one line. The AFK table's 'nothing is idle here' tail is there
    to explain that table; anywhere else it is noise."""
    seen = []
    for _, m, _ in route:
        name = m.split(", nothing is idle here")[0]
        if not seen or seen[-1] != name:
            seen.append(name)
    return " → ".join(seen)


def days_line(hours):
    """Hours as a calendar, at a pace a person keeps: three hours a day."""
    days = hours / 3
    if days < 60:
        return f"{days:.0f} days at 3h a day"
    return f"{days / 30.4:.0f} months at 3h a day"


def profile_tags(key):
    """The three-word summary of what a route asks for."""
    tags = PATH_PROFILE.get(key) or ()
    return ('<div class="profile">'
            + "".join(f'<span>{e(t)}</span>' for t in tags) + '</div>')


def optimal_card(choice, computed):
    """What the search actually found, and how close the runners-up came.

    When the optimum is simply one of the three routes in full, a fourth table
    would be a copy of it. The useful thing is the margin: which swaps cost
    almost nothing, because those are the ones worth taking for a calmer
    method.
    """
    best = computed["opt"][1]
    winner = next((lab for k, lab, _ in PATH_META
                   if all(v == k for v in choice.values())), None)
    label_of = {k: lab for k, lab, _ in PATH_META}

    swaps = []
    for name in PATHS:
        for k, lab, _ in PATH_META:
            if k == choice[name]:
                continue
            trial = dict(choice, **{name: k})
            cost = rows_for(trial, order="best")[1] - best
            # the AFK table names these "X, nothing is idle here" to explain
            # itself; out of that context the suffix is just noise
            method = route_label(PATHS[name][k])
            if method == route_label(PATHS[name][choice[name]]):
                continue
            swaps.append((cost, name, method, lab))
    swaps.sort()
    seen, shortlist = set(), []
    for row in swaps:                      # cheapest option per skill only
        if row[1] in seen:
            continue
        seen.add(row[1])
        shortlist.append(row)

    rows = "".join(
        f'<tr><td class="tn"><a href="skills/{slug(name)}.html">'
        f'{icon(name)}{e(name)}</a></td>'
        f'<td>{e(method)}</td>'
        f'<td class="route">{e(lab)}</td>'
        f'<td class="rate afkgap">{"+" if cost >= 0 else "−"}{abs(cost):.0f}h</td></tr>'
        for cost, name, method, lab in shortlist[:12])

    if winner:
        verdict = (f'Every swap was tried against every other route, one skill '
                   f'at a time. Nothing beat <b>{e(winner)}</b> on any of them, '
                   f'so the optimum is that entire route. Using a slower '
                   f'method for the XP it gives another skill never quite pays '
                   f'here.')
    else:
        diffs = ", ".join(
            f'{e(n)} takes the {"AFK" if k == "afk" else e(label_of[k].lower())} method'
            for n, k in sorted(choice.items()) if k != PATH_META[0][0]
        )
        verdict = ('The best mix is not any one route: ' + diffs +
                   '. Those methods are slower for their own skill and still '
                   'win because of the XP they give the other skills.')

    return (
        '<section class="pathcard" id="path-opt" data-path="opt" hidden>'
        '<div class="phead"><h2 id="opt">Optimal</h2>'
        f'<span class="ptot">{best:,.0f} hours</span>'
        f'<span class="pdays">{days_line(best)}</span></div>'
        f'{profile_tags("opt")}'
        f'<p class="lede2">{verdict}</p>'
        '<h3 class="sub">Cheapest swaps</h3>'
        '<p class="note nt">What each change would cost on top of the total. '
        'The ones near the top are close enough to free that the calmer method '
        'is the better buy.</p>'
        '<div class="tablewrap"><div class="tablescroll">'
        '<table class="pathtable swaps"><thead><tr><th>Skill</th>'
        '<th>Swap to</th><th>Route</th><th>Costs</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div></div></section>')


SHORT_BLOCK = {"Slayer to 99": "slayer", "Finish combat": "combat",
               "The grinds that pay": "grinds", "Slow gatherers": "gatherers",
               "Buyables last": "buyables"}


def order_note(key, rows, total):
    """What the front page's block order would cost on this route."""
    plan_rows, plan_total = path_hours(key, order="plan", diaries=True)
    gap = plan_total - total
    if gap < 1:
        return ('<p class="note nt">No ordering beats the Max Order from the '
                'front page on this route: its blocks already put the skills '
                'that carry others first.</p>')

    best_hours = {r["skill"]: r["hours"] for r in rows}
    moves = sorted(((r["hours"] - best_hours.get(r["skill"], 0), r["skill"])
                    for r in plan_rows), reverse=True)
    differences = [(cost, name) for cost, name in moves if cost >= 1]
    named = ", ".join(f"{cost:.0f}h for {e(name)}"
                      for cost, name in differences[:3])
    if len(differences) == 1:
        details = f' The biggest difference is {named}.'
    elif named:
        details = f' The biggest differences are {named}.'
    else:
        details = ' Small losses across several skills account for the difference.'
    return (f'<p class="note nt">The Max Order on the front page costs '
            f'<b>{plan_total:,.0f}h</b> on this route, {gap:,.0f} hours more. It '
            f'trains skills before the ones that would have carried them.'
            f'{details} The order below fixes that by crossing the blocks; the '
            f'blocks themselves are still worth keeping, because they are '
            f'about money and this is only about hours.</p>')


def paths_page():
    computed = {key: path_hours(key, order="best", diaries=True)
                for key, _, _ in PATH_META}
    choice, _ = optimal_mix()
    computed["opt"] = rows_for(choice, order="best", diaries=True)

    alt = {}
    for key, _, _ in PATH_META:
        for r in computed[key][0]:
            alt.setdefault(r["skill"], {})[key] = (r["method"], r["hours"])

    cards, totals = [], {}
    totals["opt"] = computed["opt"][1]
    for key, label, blurb in PATH_META:
        rows, total = computed[key]
        totals[key] = total
        cells = []
        for r in rows:
            if not r["left"] and not r["need"]:
                continue
            rates = [leg["rate"] for leg in r["legs"] if leg["rate"]]
            rate = (fmt_rate(rates[0]) if len(set(rates)) == 1
                    else f'{fmt_rate(rates[0])}→{fmt_rate(rates[-1])}'
                    if rates else "free")
            hrs = f'{r["hours"]:.0f}h' if r["hours"] else "free"
            others = []
            for other, other_label, _ in PATH_META:
                if other == key:
                    continue
                pair = alt.get(r["skill"], {}).get(other)
                if not pair or pair[0] == r["method"]:
                    continue
                delta = pair[1] - r["hours"]
                cost = ("even" if abs(delta) < 0.5
                        else f'{"+" if delta > 0 else ""}{delta:.0f}h')
                others.append(
                    f'<span class="alt"><i>{e(other_label.lower())}</i> '
                    f'{e(pair[0])} <b>{cost}</b></span>')
            gives = " · ".join(f"{n} {lv}" for n, lv in r["gives"])
            got = (f'<span class="carried">arrive at {r["arrive"]}</span>'
                   if r["arrive"] > r["level"] else "")
            blk = PLAN_BLOCK.get(r["skill"])
            got += (f'<span class="blk">{e(SHORT_BLOCK.get(blk[2], blk[2]))}</span>'
                    if blk else "")
            unlocks = "".join(f'<span class="dia">{e(d)}</span>'
                              for d in r["diaries"])
            feeds = "".join(
                f'<span class="feed{" short" if feeder_state(f) else ""}">'
                f'{e(f["name"])}<i>pays {e(f["gives"])}</i></span>'
                for f in FEEDERS if f["skill"] == r["skill"])
            cells.append(
                f'<tr><td class="num">{r["order"]}</td>'
                f'<td class="tn"><a href="skills/{slug(r["skill"])}.html">'
                f'{icon(r["skill"])}{e(r["skill"])}</a>{got}</td>'
                f'<td>{legs_cell(r)}'
                + (f'<span class="gives">leaves {e(gives)}</span>' if gives else "")
                + (f'<div class="alts">{"".join(others)}</div>' if others else "")
                + (f'<div class="dias"><i>unlocks</i>{unlocks}</div>'
                   if unlocks else "")
                + (f'<div class="dias"><i>feeds</i>{feeds}</div>'
                   if feeds else "")
                + "</td>"
                f'<td class="rate">{rate}</td>'
                f'<td class="rate afkgap">{hrs}</td></tr>')
        cards.append(
            f'<section class="pathcard" id="path-{key}" data-path="{key}"'
            f'{"" if key == "hybrid" else " hidden"}>'
            f'<div class="phead"><h2 id="{key}">{e(label)}</h2>'
            f'<span class="ptot">{total:,.0f} hours</span>'
            f'<span class="pdays">{days_line(total)}</span></div>'
            f'{profile_tags(key)}'
            f'<p class="lede2">{e(blurb)}</p>'
            + order_note(key, rows, total)
            + '<div class="tablewrap"><div class="tablescroll">'
            '<table class="pathtable"><thead><tr><th>#</th><th>Skill</th>'
            '<th>Method</th><th>XP/hr</th><th>Hours</th></tr></thead>'
            f'<tbody>{"".join(cells)}</tbody></table></div></div></section>')

    cards.append(optimal_card(choice, computed))

    meta = PATH_META + [("opt", "Optimal", "")]
    buttons = "".join(
        f'<button class="stat pick{" on" if key == "hybrid" else ""}" type="button" '
        f'data-path="{key}" aria-controls="path-{key}" '
        f'aria-pressed="{"true" if key == "hybrid" else "false"}">'
        f'<span class="l">{e(label)}</span>'
        f'<span class="v">{totals[key]:,.0f}<small>hours</small></span>'
        f'<span class="s">{e((PATH_PROFILE.get(key) or ("",))[0])}</span></button>'
        for key, label, _ in meta)

    left = sum(r["need"] for r in computed["fast"][0])
    now = {name: (stat_of(name) or {}).get("level", 0) for name in SKILL_NAMES}
    have_now = len(diary_state(now))
    body = [
        '<div class="kick">Three paths, one cape</div>',
        '<div class="page-head">'
        '<img class="icon lg" src="assets/media/max-cape.png" alt="">'
        '<h1 class="page">Which Path</h1></div>',
        f'<p class="lede">{left:,.0f} XP left. What that costs in hours is '
        'entirely a question of how much attention you are willing to pay.</p>',
        f'<div class="stats switcher">{buttons}</div>',
        '<p class="note">Numbered in the order in which they are worth doing: skills '
        'that hand XP to other skills come first, so the gift lands before you pay '
        'for those levels. The calculation then follows that order, so each '
        'skill shows the level you will actually reach rather than the one '
        f'you are on today. {have_now} of {DIARY_TIERS} diary tiers are '
        'already covered by your current levels; the rest are marked on the step '
        'that brings them in range. Diary tiers also require quest points and items, '
        'which this calculation does not account for, and the XP lamps they award '
        'are not counted.</p>',
    ] + cards
    return page("Which Path", "\n".join(body), depth=0)



CALC_JS = """
<script>
/* Skill calculators. Action tables are the wiki's, prices are the live GE
   feed, the starting level is whatever the Hiscores last said. */
(function () {
  var DATA = null, PRICES = null, VOLUMES = null, STATS = null, skill = null;
  var MAX_LEVEL = 126;

  function ready() {
    var body = document.getElementById('calcbody');
    if (!body) return;
    var tabs = Array.prototype.slice.call(document.querySelectorAll('.ctab'));
    var from = document.getElementById('cfrom');
    var to = document.getElementById('cto');
    var group = document.getElementById('cgroup');
    var find = document.getElementById('cfind');
    var chosen = null;
    var gap = document.getElementById('cgap');
    var pick = document.getElementById('cpick');
    var status = document.getElementById('cstatus');
    var btn = document.getElementById('crefresh');

    function esc(text) {
      var d = document.createElement('div');
      d.textContent = text == null ? '' : String(text);
      return d.innerHTML;
    }

    /* The wiki serves an item's icon straight off its file name. Anything that
       does not resolve removes itself, so a miss costs an empty cell. */
    function itemPic(name) {
      var file = encodeURIComponent(String(name).replace(/ /g, '_')) + '.png';
      return '<td class="pic"><img class="itempic" loading="lazy" alt="" '
        + 'src="https://oldschool.runescape.wiki/w/Special:FilePath/' + file + '"'
        + ' onerror="this.remove()"></td>';
    }

    function xpFor(l) {
      if (l <= 1) return 0;
      var t = 0;
      for (var i = 1; i < l; i++) t += Math.floor(i + 300 * Math.pow(2, i / 7));
      return Math.floor(t / 4);
    }

    function num(n) {
      if (n == null || !isFinite(n)) return '-';
      var sign = n < 0 ? '-' : '';
      return sign + Math.abs(Math.round(n)).toString()
        .replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',');
    }

    function level(el, fallback) {
      var v = parseInt(el.value, 10);
      return isFinite(v) && v >= 1 && v <= MAX_LEVEL ? v : fallback;
    }

    function currentXp() {
      var typed = parseInt(from.value, 10);
      var live = STATS && STATS.skills && STATS.skills[skill];
      if (live && typed === live.level) return live.xp;   // keep the part level
      return xpFor(level(from, 1));
    }

    function groups() {
      var seen = {}, out = [];
      (DATA[skill] || []).forEach(function (a) {
        if (!seen[a.type]) { seen[a.type] = 1; out.push(a.type); }
      });
      out.sort();
      var keep = group.value;
      group.replaceChildren();
      var all = document.createElement('option');
      all.value = ''; all.textContent = 'All';
      group.append(all);
      out.forEach(function (name) {
        var o = document.createElement('option');
        o.value = name; o.textContent = name;
        group.append(o);
      });
      group.value = out.indexOf(keep) >= 0 ? keep : '';
    }

    /* An item nobody has traded in days still carries a last price, and for
       the thin ones that price is fiction. Anything older than three days is
       treated as unpriced rather than believed. */
    var STALE = 3 * 24 * 3600;

    function priceOf(id) {
      var row = id == null ? null : PRICES[id];
      if (!row) return null;
      var age = (Date.now() / 1000) - row.t;
      return age > STALE ? null : row.p;
    }

    /* Barely-traded items still carry a price, and for the thinnest ones it is
       a number nobody could actually transact at. Under a thousand a day is
       the line: the barbarian mixes sit at 0 or 1, the real materials are in
       the tens of thousands. */
    var THIN = 1000;

    function flow(action) {
      if (!VOLUMES) return null;
      var least = null;
      var ids = action.materials.map(function (m) { return m.id; });
      if (action.made != null) ids.push(action.made);
      for (var i = 0; i < ids.length; i++) {
        if (ids[i] == null) continue;
        var v = VOLUMES[ids[i]] || 0;
        if (least === null || v < least) least = v;
      }
      return least;
    }

    function cost(action) {
      if (!PRICES || !action.materials.length) return null;
      var total = 0;
      for (var i = 0; i < action.materials.length; i++) {
        var m = action.materials[i];
        var p = priceOf(m.id);
        if (p == null) return null;
        total += p * m.qty;
      }
      var made = 0;
      if (action.made != null) {
        made = priceOf(action.made);
        if (made == null) return null;
      }
      return total - made;
    }

    function draw() {
      var actions = DATA[skill] || [];
      var start = currentXp();
      var target = xpFor(level(to, 99));
      var need = Math.max(0, target - start);
      var here = level(from, 1);

      gap.textContent = need ? num(need) + ' XP to go' : 'already there';

      var only = group.value;
      var best = null;
      var text = (find.value || '').trim().toLowerCase();
      var rows = actions.map(function (a) {
        if (only && a.type !== only) return null;
        if (text && a.name.toLowerCase().indexOf(text) < 0) return null;
        var count = a.xp > 0 ? Math.ceil(need / a.xp) : null;
        var each = cost(a);
        var total = (each == null || count == null) ? null : each * count;
        var gpxp = each == null ? null : each / a.xp;
        var daily = flow(a);
        var thin = daily != null && daily < THIN;
        if (need && a.level <= here && gpxp != null && !thin
            && (best === null || gpxp < best.gpxp)) {
          best = { name: a.name, gpxp: gpxp, count: count, total: total, xp: a.xp };
        }
        return { a: a, count: count, each: each, total: total, gpxp: gpxp,
                 thin: thin, daily: daily };
      }).filter(Boolean);

      body.replaceChildren();
      rows.forEach(function (r) {
        var locked = r.a.level > here;
        var tr = document.createElement('tr');
        tr.className = (locked ? 'locked' : '')
          + (r.a.name === chosen ? ' chosen' : '');
        tr.setAttribute('data-name', r.a.name);
        tr.innerHTML =
          '<td class="req">' + r.a.level + '</td>' +
          itemPic(r.a.name) +
          '<td class="tn">' + esc(r.a.name) +
            (r.thin ? '<span class="thin">' + num(r.daily)
              + ' traded a day</span>' : '') +
            '<span class="gives">' + esc(r.a.type) + '</span></td>' +
          '<td class="rate">' + (r.a.xp % 1 ? r.a.xp.toFixed(1) : r.a.xp) + '</td>' +
          '<td class="rate afkgap">' + (r.count == null ? '-' : num(r.count)) + '</td>' +
          '<td class="rate">' + (r.each == null ? '-' : num(r.each)) + '</td>' +
          '<td class="rate">' + (r.total == null ? '-' : num(r.total)) + '</td>' +
          '<td class="rate' + (r.gpxp != null && r.gpxp <= 0 ? ' good' : '') + '">'
            + (r.gpxp == null ? '-' : num(r.gpxp)) + '</td>';
        body.append(tr);
      });

      if (best) {
        pick.replaceChildren();
        var k = document.createElement('span');
        k.className = 'k'; k.textContent = 'Cheapest';
        var pic = document.createElement('img');
        pic.className = 'itempic';
        pic.loading = 'lazy';
        pic.alt = '';
        pic.onerror = function () { pic.remove(); };
        pic.src = 'https://oldschool.runescape.wiki/w/Special:FilePath/'
          + encodeURIComponent(best.name.replace(/ /g, '_')) + '.png';
        var b = document.createElement('b'); b.textContent = best.name;
        var d = document.createElement('span');
        d.className = 'pdet';
        d.textContent = num(best.count) + ' \\u00d7 at ' + num(best.gpxp)
          + ' GP per XP \\u00b7 ' + num(best.total) + ' GP all in';
        var w = document.createElement('span');
        w.className = 'pwhy';
        w.textContent = best.gpxp <= 0
          ? 'It pays you to train, so the only cost is the time.'
          : 'Lowest cost per point of experience at your level.';
        pick.append(k, pic, b, d, w);
        pick.hidden = false;
      } else {
        pick.hidden = true;
      }
    }

    function choose(name) {
      skill = name;
      chosen = null;
      tabs.forEach(function (t) {
        var on = t.getAttribute('data-skill') === name;
        t.classList.toggle('on', on);
        t.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      var live = STATS && STATS.skills && STATS.skills[name];
      from.value = live ? live.level : 1;
      groups();
      draw();
      try { localStorage.setItem('osrsplan.calc', name); } catch (err) { /* ignore */ }
    }

    function prices() {
      if (btn.classList.contains('busy')) return;
      btn.classList.add('busy');
      btn.classList.remove('ok', 'bad');
      var started = Date.now();
      var settle = function (fn, bad) {
        setTimeout(function () {
          btn.classList.remove('busy');
          btn.classList.add(bad ? 'bad' : 'ok');
          setTimeout(function () { btn.classList.remove('ok', 'bad'); }, 2500);
          fn();
        }, Math.max(0, 900 - (Date.now() - started)));
      };
      Promise.all([
        fetch('https://prices.runescape.wiki/api/v1/osrs/latest', { cache: 'no-store' })
          .then(function (r) { return r.json(); }),
        fetch('https://prices.runescape.wiki/api/v1/osrs/volumes')
          .then(function (r) { return r.json(); })
          .catch(function () { return null; })
      ])
        .then(function (both) {
          var d = both[0];
          VOLUMES = both[1] && (both[1].data || both[1]);
          var out = {};
          Object.keys(d.data || {}).forEach(function (id) {
            var row = d.data[id];
            var price = row.high || row.low;
            var seen = Math.max(row.highTime || 0, row.lowTime || 0);
            if (price) out[id] = { p: price, t: seen };
          });
          PRICES = out;
          settle(function () { status.textContent = 'priced just now'; draw(); });
        })
        .catch(function () {
          settle(function () { status.textContent = 'prices unavailable'; }, true);
        });
    }

    tabs.forEach(function (t) {
      t.addEventListener('click', function () {
        choose(t.getAttribute('data-skill'));
      });
    });
    [from, to, find].forEach(function (el) { el.addEventListener('input', draw); });
    body.addEventListener('click', function (ev) {
      var row = ev.target.closest('tr[data-name]');
      if (!row) return;
      var name = row.getAttribute('data-name');
      chosen = chosen === name ? null : name;
      draw();
    });
    group.addEventListener('change', draw);
    btn.addEventListener('click', prices);
    document.addEventListener('osrsplan:stats', function (ev) {
      STATS = ev.detail;
      var live = STATS.skills && STATS.skills[skill];
      if (live) { from.value = live.level; draw(); }
    });

    Promise.all([
      fetch('data/calculators.json').then(function (r) { return r.json(); }),
      fetch('data/stats.json').then(function (r) { return r.json(); })
        .catch(function () { return null; })
    ]).then(function (got) {
      DATA = got[0];
      STATS = got[1];
      var saved = null;
      try { saved = localStorage.getItem('osrsplan.calc'); } catch (err) { /* ignore */ }
      choose(DATA[saved] ? saved : tabs[0].getAttribute('data-skill'));
      prices();
    }).catch(function () {
      status.textContent = 'calculator data unavailable';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ready);
  } else {
    ready();
  }
})();
</script>
"""


CALC_PATH = os.path.join(OUT, "data", "calculators.json")


# spelled out rather than reusing a TIERS name, which is already taken in this
# file by the method-tier table
DIARY_TIER_ORDER = ["Easy", "Medium", "Hard", "Elite"]


def diary_wall(tier):
    """The highest level any region asks for at this tier or below.

    Tiers have to be done in order, so the wall in front of Hard is really the
    tallest of Easy, Medium and Hard across all twelve regions.
    """
    order = DIARY_TIER_ORDER
    upto = order[:order.index(tier) + 1] if tier in order else [tier]
    wall = {}
    for region in DIARY_REQS.values():
        for name in upto:
            for skill, level in (region.get(name) or {}).items():
                if skill in NOT_A_SKILL or skill not in SKILL_NAMES:
                    continue
                wall[skill] = max(wall.get(skill, 0), int(level))
    return sorted(wall.items(), key=lambda kv: (-kv[1], kv[0]))


def calculator_skills():
    """Skills the wiki publishes an action table for, in our own order."""
    try:
        with open(CALC_PATH, encoding="utf-8") as f:
            have = set(json.load(f))
    except (OSError, ValueError):
        return []
    ordered = [s["name"] for g in GROUP_ORDER for s in SKILLS
               if s["group"] == g and s["name"] in have]
    return ordered + sorted(have - set(ordered))


def calculators_page():
    """One calculator per skill: how many of a thing to reach a level.

    The action tables are the Wiki's own (Module:Skill calc), so this agrees
    with the Wiki's calculators rather than being a second opinion. Prices are
    live; the current level comes from the Hiscores, and both can be typed over.
    """
    skills = calculator_skills()
    if not skills:
        return page("Calculators", '<p class="lede">No calculator data yet. Run '
                    '<code>python3 fetch_calculators.py</code>.</p>', depth=0)

    tabs = "".join(
        f'<button class="ctab{" on" if i == 0 else ""}" type="button" '
        f'data-skill="{e(name)}" aria-pressed="{"true" if i == 0 else "false"}">'
        f'{icon(name)}{e(name)}</button>'
        for i, name in enumerate(skills))

    body = [
        '<div class="kick">Every skill, every action</div>',
        '<div class="page-head">'
        '<img class="icon lg" src="assets/media/site/combat-achievements.png" alt="">'
        '<h1 class="page">Calculators</h1></div>',
        '<p class="lede">How many actions stand between you and a level, '
        'what they cost at today\'s prices, and which option is cheapest per '
        'point of XP.</p>',
        f'<div class="ctabs">{tabs}</div>',
        '<div class="calcbar">'
        '<label class="cfield"><span>From</span>'
        '<input id="cfrom" type="number" min="1" max="126" inputmode="numeric">'
        '</label>'
        '<label class="cfield"><span>To</span>'
        '<input id="cto" type="number" min="2" max="126" value="99" '
        'inputmode="numeric"></label>'
        '<span class="cgap" id="cgap">—</span>'
        '<span class="espace"></span>'
        '<label class="cfield sel"><span>Group</span>'
        '<select id="cgroup"><option value="">All</option></select></label>'
        '<label class="cfield"><span>Find</span>'
        '<input id="cfind" type="search" class="wide" placeholder="action name" '
        'autocomplete="off"></label>'
        '<span class="estatus" id="cstatus">loading</span>'
        '<button class="refresh" id="crefresh" type="button" '
        'title="Refresh prices" aria-label="Refresh prices">'
        '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">'
        '<path d="M13.6 8a5.6 5.6 0 1 1-1.7-4" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round"/>'
        '<path d="M13.4 1.4v3h-3" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg></button>'
        '</div>',
        '<div class="cpick" id="cpick" hidden></div>',
        '<div class="tablewrap"><div class="tablescroll">'
        '<table class="pathtable calctable" id="calctable"><thead><tr>'
        '<th>Lvl</th><th class="pic"></th><th>Action</th><th>XP each</th><th>Needed</th>'
        '<th>Each</th><th>Total</th><th>GP/XP</th></tr></thead>'
        '<tbody id="calcbody"></tbody></table></div></div>',
        '<p class="lede2">Action tables come from the wiki\'s own skill '
        'calculator modules, so the XP figures match the wiki. Prices are the '
        'live Grand Exchange feed, with anything that has not traded in three '
        'days left unpriced rather than believed. A row flagged with a trade '
        'count is one almost nobody buys or sells, so its price is not a number '
        'you could transact at and it never wins the recommendation. Rows above '
        'your level are '
        'dimmed rather '
        'than hidden, since half of choosing a method is seeing what is '
        'coming.</p>',
    ]
    return page("Calculators", "\n".join(body), depth=0,
                head_extra=CALC_JS, wide=True)


def gear_page():
    """Skilling outfits on their own page, since ticking pieces off is its own
    job rather than something to scroll past on the way down the plan."""
    body = [
        '<div class="kick">What you wear to train</div>',
        '<div class="page-head">'
        '<img class="icon lg" src="assets/media/site/gear-icon.png" alt="">'
        '<h1 class="page">Gear</h1></div>',
        '<p class="lede">Every skilling outfit, what it actually does, and '
        'where it comes from.</p>',
        outfit_section(),
    ]
    return page("Gear", "\n".join(body), depth=0)


def character_coach():
    """Where the sidebar's sync and next-action controls report back. Empty
    until one of them runs, so it takes no space on a fresh page."""
    return (
        '<section class="coach">'
        '<p class="coach-status" id="coach-status" role="status" aria-live="polite"></p>'
        '<div class="coach-output" id="coach-output" hidden></div>'
        '</section>'
    )


def build_index():
    parts = ['<h1 class="sr">OSRS Max Cape Plan</h1>']
    parts.append(character_coach())

    parts.append('<ol class="phases" id="progression">')
    for i, ph in enumerate(PLAN_PHASES, 1):
        body = phase_meter(ph.get("track", ""))
        reqs = ph.get("reqs") or (diary_wall(ph["diary_tier"])
                                  if ph.get("diary_tier") else None)
        if reqs:
            chips = "".join(req_chip(n, lv) for n, lv in reqs)
            if ph.get("combat"):
                chips += combat_chip(ph["combat"])
            body += f'<div class="reqgrid">{chips}</div>'
        if ph.get("subs"):
            body += "<ul>" + "".join(f"<li>{annotate(x)}</li>" for x in ph["subs"]) + "</ul>"
        parts.append(f'  <li id="phase-{i}"><b>{annotate(ph["title"])}</b>'
                     f'{phase_tag(ph.get("track", ""))}{body}</li>')
    parts.append("</ol>")

    parts.append(h2("quests", "Quest Cape", "assets/media/quest-point-cape.png"))
    parts.append(quest_panel())

    parts.append(h2("diaries", "Diaries", "assets/icons/Diaries.png"))
    parts.append(diary_panel())

    parts.append(h2("approach", "Slayer", "assets/icons/Slayer.png"))
    parts.append('<div class="panel"><div class="k">Rules</div><ul>' +
                 "".join(f"<li>{annotate(c)}</li>" for c in COMBAT_APPROACH) +
                 "</ul></div>")

    parts.append(h2("max-order", "Max Order", "assets/media/max-cape.png"))
    after, left = post_diary_rows()
    parts.append(f'<p class="lede2">Starts from where the Diary Cape leaves '
                 f'you, so nothing is counted twice. <b>{left:,.0f} hours</b> on '
                 f'the Realistic route, at the rates the '
                 f'<a class="wl" href="paths.html">route tables</a> use. Skills '
                 f'that pay come before skills that cost; no other order is '
                 f'cheaper.</p>')
    parts.append('<ol class="phases maxorder">')
    for phase in MAX_ORDER:
        parts.append(max_order_block(phase, after))
    parts.append("</ol>")

    parts.append(h2("feeders", "Feeders", "assets/media/site/skills-icon.png"))
    parts.append(feeders_section())

    return page("OSRS Max Time-Wasting Plan", "\n".join(parts), coach=True)


# --------------------------------------------------------------------------
# Time to max. Hours, methods and order are osrsguide.com's; the wording here
# is ours. Every figure is 1-99 from scratch at maximum efficiency, so it does
# not subtract the levels this account already has.
# --------------------------------------------------------------------------

MAXGUIDE_URL = OSRSGUIDE + "time-to-max-osrs/"

MAXGUIDE_COMBAT = [
    "Strength and Attack to 80, then Defence to 80.",
    "Everything after that comes off Slayer tasks, switching style in the same "
    "order: Strength, then Attack, then Defence.",
    "Cannon on task. It pays 0.75 Ranged XP for every point of Slayer XP, which "
    "is most of the way to 90.",
    "Hitpoints arrives on its own. Ranged finishes with ten hours of chinning.",
]

MAXGUIDE_COMBAT_ROWS = [
    ("Strength", "Slayer tasks, aggressive", "150", ""),
    ("Attack", "Slayer tasks, accurate", "150", ""),
    ("Defence", "Slayer tasks, defensive", "150", ""),
    ("Slayer", "Duradel, cannon on multi tasks", "200", "trained alongside the three above"),
    ("Ranged", "Cannon to about 90, then chinning", "10", ""),
    ("Hitpoints", "Passive", "0", "comes with the combat XP"),
]

MAXGUIDE_ROWS = [
    ("Prayer", "Dagannoth bones, superior dragon bones from 70, gilded or chaos altar", "10", ""),
    ("Fletching", "Dart tips", "12-18", "143M"),
    ("Farming", "Tree runs", "15", "80M"),
    ("Construction", "Chairs to 33, oak larders to 52, mahogany tables to 77, gnome benches to 99", "15", "300M"),
    ("Cooking", "1-tick karambwans from 30", "16", "4M profit"),
    ("Herblore", "Attack potions to 38, prayer potions to 63, super restores to 83, anti-venoms from 87", "24", "200M"),
    ("Crafting", "Dragonhide bodies", "34", "120M"),
    ("Firemaking", "Highest logs you can burn, Varrock teleport loop", "35", "11M"),
    ("Smithing", "Blast Furnace gold bars from 40", "37", "43M"),
    ("Magic", "Enchanting bolts, ice barrage in the MM2 caves", "38", ""),
    ("Thieving", "Blackjacking from 45, or Ardougne knights", "57.5", ""),
    ("Woodcutting", "2-tick teaks", "80", ""),
    ("Hunter", "Salamanders to 80, then herbiboar", "110", ""),
    ("Fishing", "Barbarian fishing", "150", "pays 1M Strength and 1M Agility"),
    ("Mining", "3-tick granite at the quarry", "150", ""),
    ("Runecraft", "Lava runes", "190", "ZMI instead costs 70 hours more"),
    ("Agility", "Rooftops", "214", "already 16 hours lighter from barbarian fishing"),
]

MAXGUIDE_ALTS = [
    ("Cooking", "Jugs of wine", "26 hours"),
    ("Firemaking", "Wintertodt", "50 hours, about 3M profit"),
    ("Woodcutting", "3-tick teaks", "120 hours"),
    ("Woodcutting", "Redwoods", "140 hours"),
    ("Runecraft", "ZMI altar", "260 hours"),
]

# Where the guide and the current wiki rates disagree. Both are on the page;
# the reader gets to pick.
MAXGUIDE_CHECKS = [
    "Agility: the guide trains rooftops. The Hallowed Sepulchre now runs to "
    "about 105k/hr and its floors dropped to 77 and 87 in August 2026, which "
    "beats rooftops from 62 up.",
    "Runecraft: lava runes cap near 102k/hr. Aether runes with runners reach "
    "265-345k/hr at 90, at roughly 12-15M per runner hour.",
    "Hunter: birdhouse XP was cut 40-60% in August 2026, so any plan leaning "
    "on passive birdhouse XP is now slower than it looks.",
]


def maxguide_page():
    """The osrsguide.com route, in our words, with its numbers."""
    def rows(data):
        return "".join(
            f'<tr><td class="tn">{icon(name) if name in SKILL_NAMES else ""}'
            f'{e(name)}</td><td class="notes">{e(method)}</td>'
            f'<td class="rate">{e(hours)}</td><td class="req">{e(extra)}</td></tr>'
            for name, method, hours, extra in data
        )

    skills_hours = 1178.5
    body = [
        '<div class="kick">Maxing route</div>',
        '<div class="page-head"><img class="icon lg" src="assets/media/max-cape.png" '
        'alt=""><h1 class="page">Time to Max</h1></div>',
        '<p class="lede">Every skill at its fastest method, tick manipulation '
        'included. This is the ceiling, not a forecast.</p>',
        '<div class="pillrow">'
        f'<span class="pill"><span class="pl">Perfect play</span>'
        f'<span class="pv">{310 + skills_hours:,.1f}h</span></span>'
        '<span class="pill"><span class="pl">Realistic</span>'
        '<span class="pv">2,000-2,500h</span></span>'
        '<span class="pill"><span class="pl">Record</span>'
        '<span class="pv">32d 3h 3m</span></span>'
        "</div>",
        '<p class="note">Hours are 1-99 from nothing, so they do not subtract '
        'the levels you already have. For that, use '
        '<a class="wl" href="index.html#max-order">Max Order</a>, which starts '
        'from your live stats. The record is He Box Jonge\'s. Numbers and route '
        f'from <a class="wl" href="{MAXGUIDE_URL}" target="_blank" '
        'rel="noopener">osrsguide.com</a>.</p>',

        h2("combat", "Combat and Slayer", "assets/icons/Slayer.png"),
        '<p class="lede2">310 hours for the whole block, because Slayer pays '
        'the combat stats while you train it.</p>',
        '<ul>' + "".join(f"<li>{annotate(x)}</li>" for x in MAXGUIDE_COMBAT) + "</ul>",
        '<div class="tablewrap"><div class="tablescroll">'
        '<table class="maxtable"><thead><tr><th>Skill</th><th>Method</th>'
        '<th>Hours</th><th></th></tr></thead>'
        f'<tbody>{rows(MAXGUIDE_COMBAT_ROWS)}</tbody></table></div></div>',

        h2("skills", "The rest, fastest first", "assets/media/site/skills-icon.png"),
        f'<p class="lede2">{skills_hours:,.1f} hours across the seventeen.</p>',
        '<div class="tablewrap"><div class="tablescroll">'
        '<table class="maxtable"><thead><tr><th>Skill</th><th>Method</th>'
        '<th>Hours</th><th>Cost</th></tr></thead>'
        f'<tbody>{rows(MAXGUIDE_ROWS)}</tbody></table></div></div>',

        h2("alts", "Slower, easier", "assets/media/site/quests.png"),
        '<p class="lede2">What each swap costs you.</p>',
        '<div class="tablewrap"><div class="tablescroll">'
        '<table class="maxtable"><thead><tr><th>Skill</th><th>Instead</th>'
        '<th>Costs</th></tr></thead><tbody>'
        + "".join(f'<tr><td class="tn">{icon(name)}{e(name)}</td>'
                  f'<td class="notes">{e(alt)}</td>'
                  f'<td class="rate">{e(cost)}</td></tr>'
                  for name, alt, cost in MAXGUIDE_ALTS)
        + "</tbody></table></div></div>",

        h2("checks", "Worth checking", "assets/icons/Diaries.png"),
        '<p class="lede2">Three places where the guide is behind the current '
        'wiki rates.</p>',
        '<ul>' + "".join(f"<li>{annotate(x)}</li>" for x in MAXGUIDE_CHECKS) + "</ul>",
    ]
    return page("Time to Max", "\n".join(body), depth=0)


def main():
    os.makedirs(os.path.join(OUT, "skills"), exist_ok=True)

    ordered = [s for g in GROUP_ORDER for s in SKILLS if s["group"] == g]
    outputs = {}
    for i, s in enumerate(ordered):
        prev_s = ordered[i - 1] if i else None
        next_s = ordered[i + 1] if i + 1 < len(ordered) else None
        path = os.path.join(OUT, "skills", slug(s["name"]) + ".html")
        outputs[path] = build_skill_page(s, prev_s, next_s)

    outputs.update({
        os.path.join(OUT, "stars.html"): build_stars_page(),
        os.path.join(OUT, "afk.html"): build_afk_page(),
        os.path.join(OUT, "paths.html"): paths_page(),
        os.path.join(OUT, "calculators.html"): calculators_page(),
        os.path.join(OUT, "gear.html"): gear_page(),
        os.path.join(OUT, "maxguide.html"): maxguide_page(),
        os.path.join(OUT, "index.html"): build_index(),
    })
    for path, content in outputs.items():
        atomic_text_dump(path, content)

    print(f"wrote index.html + {len(ordered)} skill pages + 6 reference pages")


if __name__ == "__main__":
    main()
