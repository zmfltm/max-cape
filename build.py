#!/usr/bin/env python3
"""Generates the static OSRS max-plan site: index.html + skills/*.html.

Edit SKILLS / PLAN below and re-run:  python3 build.py
"""

import base64
import html
import json
import os
import re
import sys
import urllib.parse

from hiscores import XP_TABLE, xp_for_level
from media import METHOD_MEDIA, PROSE_ENTITIES
from slayer import TASKS as SLAYER_TASKS

OUT = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# The plan
# --------------------------------------------------------------------------

PLAN_PHASES = [
    dict(title="Quest-cape preparation",
         reqs=[("Defence", 70), ("Ranged", 70), ("Magic", 75), ("Smithing", 75),
               ("Firemaking", 75), ("Runecraft", 65), ("Hunter", 70), ("Fishing", 70),
               ("Agility", 71), ("Thieving", 75), ("Slayer", 72)],
         combat=100,
         subs=["Hunter and Fishing come together through Drift Net Fishing"]),
    dict(title="Quest Cape",
         track="quests",
         subs=["Continue following the Optimal Quest Guide",
               "Use quest XP before manually finishing skill requirements where possible"]),
    dict(title="All Hard Diaries", track="diary_hard", subs=[]),
    dict(title="Slayer to 95",
         track="slayer",
         subs=["Slayer remains the default activity for combat training",
               "Complete elite-diary skill requirements as you reach them"]),
    dict(title="Elite diary skill walls",
         track="diary_elite",
         subs=["Train whatever individual requirements remain",
               "Finish the Diary Cape"]),
    dict(title="Max Cape", track="max", subs=[]),
]

COMBAT_APPROACH = [
    "Nieve/Steve initially.",
    "Konar when useful for milestone points.",
    "Duradel after 100 combat, 50 Slayer and Shilo Village access.",
    "Cannon tasks to train Ranged.",
    "Burst appropriate tasks to train Magic.",
    "Melee priority: Strength to ~85 first, then Attack 80, then Defence 75–80.",
    "Let Slayer and later bossing carry most combat XP rather than separately grinding combats early.",
]


# --------------------------------------------------------------------------
# Skills.  Each entry:
#   target  - short label shown on the index card
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
        phase="80 during the Slayer grind (after Strength ~85), 99 in the combat block after the Diary Cape.",
        summary="Slayer tasks; Strength first, then Attack.",
        methods=[
            ("Slayer tasks", "—", "30–60k", "Your default. XP depends entirely on the task and gear; Duradel tasks with a good weapon are the top end."),
            ("Nightmare Zone", "Quest reqs", "40–80k", "Absorptions + rock cake, very AFK. Dream selection matters; also prints points for imbues."),
            ("Sulphur Nagua", "Varlamore", "60–90k", "Low-attention melee XP with good rates once you have decent gear."),
            ("Gemstone Crab", "1", "30–60k",
             "Shared-health crab in Varlamore. The modern replacement for sand crabs when you want to do nothing."),
            ("Ammonite / sand crabs", "—", "20–40k", "Free, safe, extremely AFK. Fine for early levels, poor once you have Slayer flowing."),
            ("Gemstone Crab", "1", "30–60k",
             "Shared-health crab in Varlamore. The modern AFK option, better rates than sand crabs."),
            ("Bossing", "Varies", "40–80k", "Vorkath, Muspah, ToA. Slower than pure XP methods but pays for the rest of the account."),
        ],
        notes=[
            "Attack is the least valuable of the three melee stats for XP-per-hour purposes. Strength raises max hit, so the plan front-loads it to ~85.",
            "Watch for quest and diary requirements before pushing past your plan target (e.g. Attack requirements for weapon tiers you actually want to use).",
        ],
    ),
    dict(
        name="Strength", group=COMBAT, target="85 → 99", pick="Slayer tasks",
        phase="~85 first among the melee stats, 99 in the combat block after the Diary Cape.",
        summary="Slayer tasks, Strength style first to ~85.",
        methods=[
            ("Slayer tasks", "—", "30–60k", "Your default. Aggressive/Controlled styles on tasks where the melee kill is fastest."),
            ("Nightmare Zone", "Quest reqs", "40–80k", "The classic AFK 99 Strength. Slower per hour than active methods but nearly zero attention."),
            ("Sulphur Nagua", "Varlamore", "60–90k", "Strong low-effort rates; popular replacement for NMZ."),
            ("Scurrius", "Quest-free", "40–60k",
             "The rat boss under Varrock. Solid XP for the level band, and bones plus the spine for the Prayer stockpile."),
            ("Barbarian Fishing", "—", "passive", "Leaping fish give a trickle of Strength and Agility while you train Fishing."),
            ("Ammonite / sand crabs", "—", "20–40k", "Free and AFK; overtaken by anything else once you have gear."),
        ],
        notes=[
            "Strength first is right: max hit drives kill speed on every later Slayer task, which feeds back into Slayer XP rate.",
        ],
    ),
    dict(
        name="Defence", group=COMBAT, target="70 → 75–80 → 99", pick="Slayer tasks",
        phase="70 for the quest cape block; 75–80 after Strength and Attack; 99 in the post-Diary combat block.",
        summary="70 for quests, then 75–80, then 99.",
        methods=[
            ("Slayer tasks", "—", "30–60k", "Defensive or Controlled style on tasks you would be doing anyway."),
            ("Nightmare Zone", "Quest reqs", "40–80k", "Defensive style; the standard AFK route."),
            ("Sulphur Nagua", "Varlamore", "60–90k", "Same as melee. Just swap to Defensive."),
            ("Gemstone Crab", "1", "30–60k",
             "Shared-health crab in Varlamore. Defensive style, near-zero attention."),
            ("Bossing", "Varies", "30–60k", "Defensive style on long boss trips."),
        ],
        notes=[
            "Defence 70 unlocks most of the armour that matters (Bandos, Barrows, Karil's), so the early target is well placed.",
            "Check your remaining quests before overshooting. Several late quests want 70–75 Defence and nothing more.",
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
        name="Ranged", group=COMBAT, target="70 → 99", pick="Cannon on Slayer tasks",
        phase="70 for the quest cape block; 99 in the combat block after the Diary Cape.",
        summary="Cannon on Slayer tasks; chinning later.",
        methods=[
            ("Cannon on Slayer tasks", "—", "40–80k", "Your Pick. Cannon the multi-friendly tasks (dust devils, jellies, nechryael, greater demons) and it trains Ranged while the task still counts."),
            ("Chinning – maniacal monkeys", "MM2", "250–400k+", "The fastest Ranged in the game. Expensive, click-intensive, needs Monkey Madness II. This is the usual 99 route once you can afford chins."),
            ("Chinning – Wilderness caves", "—", "150–250k", "Cheaper (red chins), but PKer risk."),
            ("Blowpipe on crabs / Nagua", "—", "60–100k", "Low effort, scales dart tier."),
            ("Gemstone Crab", "1", "30–60k",
             "Shared-health crab in Varlamore. Nearly zero attention, scales with your gear, and works for any combat style."),
            ("Pest Control", "70 combat", "30–50k",
             "Points convert into XP in whichever combat stat you pick. Low intensity and free, but the rate depends on your team."),
            ("Vorkath / bossing", "Quest reqs", "60–100k", "Decent XP plus serious GP; a good way to fund chinning."),
            ("Nightmare Zone", "Quest reqs", "40–60k", "AFK fallback."),
        ],
        notes=[
            "The cannon is the right early call: it doubles as Slayer-task speed while your Ranged is too low for chinning to be efficient.",
            "Bank chins as you get them from Hunter. They feed straight into the 99 Ranged grind.",
        ],
    ),
    dict(
        name="Magic", group=COMBAT, target="75 → 99", pick="Bursting/barraging Slayer tasks",
        phase="75 for the quest cape block; 99 in the combat block after the Diary Cape.",
        summary="Burst/barrage Slayer tasks.",
        methods=[
            ("Bursting/barraging Slayer tasks", "Desert Treasure I", "100–250k", "Your Pick. Nechryael and dust devils in the Catacombs, smoke devils, jellies. Best XP-plus-Slayer combination in the game, but rune-hungry."),
            ("Bursting maniacal monkeys", "MM2, 70 Magic", "200–300k",
             "The fastest Magic XP in the game. Ice Burst on maniacal monkeys after Monkey Madness II, and it doubles as the Ranged chinning spot."),
            ("Splashing", "—", "10–30k", "Near-zero attention, near-zero rate. Only worth it if you genuinely cannot play actively."),
            ("High Alchemy", "55", "65k", "78k GP-ish per hour spent; the classic buyable Magic. Combine with another activity."),
            ("Stun-alching", "—", "~150k", "Curse/Vulnerability + High Alch at NMZ. Fast but fully click-bound and expensive."),
            ("Powered staff on Slayer", "—", "40–80k", "Trident/Sang on tasks. No rune cost beyond charges."),
            ("Guardians of the Rift", "27 RC", "moderate", "Side Magic XP while training Runecraft."),
            ("Tele-alch", "55", "~100k",
             "Alternate a teleport with High Alchemy for a faster loop than alching alone. Costs more per hour but no combat needed."),
            ("Superheat / Enchant bolts", "43+", "varies", "Doubles up with Smithing / Crafting when you're doing those anyway."),
        ],
        notes=[
            "Barrage tasks are the single best overlap in your plan. Magic XP, Slayer XP and Slayer points from the same hour.",
            "Budget for runes. If the cost gets uncomfortable, fall back to trident tasks and take Magic to 99 later in the combat block.",
        ],
    ),
    dict(
        name="Prayer", group=COMBAT, target="82–85 → 99", pick=None,
        phase="82–85 as an early quality-of-life target (Rigour/Augury tier prayers and Piety), 99 in the post-Diary combat block.",
        summary="Gilded altar bones; ensouled heads as an alternative.",
        methods=[
            ("Gilded altar – dragon bones", "Construction 75", "~250k", "The standard. Two burners lit = 350% XP. Use a friend's house or the POH portal hubs."),
            ("Gilded altar – superior dragon bones", "Construction 75", "~500k+", "Fastest sane method; roughly double the cost of dragon bones."),
            ("Blessed bone shards", "Varlamore", "verify",
             "Libation bowl offerings at the Ancient Temple. Newer than the altar methods, so confirm the current rate and cost."),
            ("Wilderness Chaos altar", "—", "~300k", "Same 350% multiplier with no house needed and a 50% chance not to consume the bone. Effectively half price. PKer risk is real; bring nothing you mind losing."),
            ("Ensouled heads", "Arceuus favour", "~300k", "Reanimate + Demonic Offering. Good when heads are cheap; needs Arceuus spellbook."),
            ("Cremating urium remains", "Shades of Mort'ton", "~250k",
             "Shade remains on a magic pyre. Slower to set up than an altar but cheap, and it drops keys for the reward chests."),
            ("Ectofuntus", "—", "~50k", "Cheapest XP per GP in the game, and painfully slow."),
        ],
        notes=[
            "Your plan didn't fix a method here. Chaos altar is the cost-efficient pick; gilded altar is the safe pick. Both are fine.",
            "Prayer is a pure buyable. Don't spend early hours on it. Bank bones from Slayer and burn them in one go.",
        ],
    ),
    dict(
        name="Slayer", group=COMBAT, target="72 → 95 → 99", pick="Duradel",
        pick_note="Start on Nieve/Steve, use Konar when you want milestone points, and move to Duradel once you have 100 combat, 50 Slayer and Shilo Village.",
        phase="72 for the quest cape block, 95 before the Diary Cape, 99 first in the post-Diary maxing order.",
        summary="The spine of the whole plan.",
        methods=[
            ("Nieve / Steve", "85 combat", "—", "Your starting master. Good task variety, reachable early."),
            ("Konar quo Maten", "75 combat", "—", "Location-locked tasks. Worth using for milestone points and for Hydra access later."),
            ("Duradel", "100 combat, 50 Slayer", "—", "Your main master once you hit 100 combat and have Shilo Village. Highest task XP in the game."),
            ("Krystilia (Wilderness)", "—", "—", "Wilderness-only tasks. Fast points and good drops, but risky. Optional."),
            ("Turael/Spria skipping", "—", "—", "Turael-skip trick to reroll bad tasks without spending points. Useful when point-starved."),
        ],
        notes=[
            "Block list is the highest-leverage decision in this plan. Block the tasks that are slow and unprofitable for your gear (typically the low-XP-per-hour, high-count ones) rather than the merely boring ones.",
            "Extend the tasks you'll want to farm later (nechryael, abyssal demons, gargoyles) once points allow.",
            "Superior slayer encounters (Bigger and Badder) are worth the point cost. They carry the imbue-tier drops.",
            "Everything else in the plan is downstream of Slayer: it carries Attack, Strength, Defence, Hitpoints, and via cannon/barrage it carries Ranged and Magic too.",
        ],
    ),
    # ---------------- gathering ----------------
    dict(
        name="Fishing", group=GATHER, target="70 → 99", pick="Drift Net Fishing",
        phase="70 for the quest cape block (paired with Hunter), 99 in the slow-skills block.",
        summary="Drift Net Fishing with Hunter.",
        methods=[
            ("Drift Net Fishing", "47 Fish / 44 Hunt", "40–60k each", "Your Pick. Trains Fishing and Hunter simultaneously on Fossil Island. Exactly why it's in the plan for the 70/70 requirement."),
            ("Barbarian Fishing", "48 (+ quest)", "30–55k", "3-tick variant is much faster; also drips Strength and Agility XP."),
            ("2-tick harpooning", "71", "90–110k",
             "Swordfish and tuna with tick manipulation. The genuine fastest Fishing, and the most demanding."),
            ("Minnows", "82", "50–60k", "Converts to sharks for Tempoross-adjacent profit. Fairly click-heavy."),
            ("Tempoross", "35", "40–60k", "Reward XP plus free food and permits. Sociable, low risk."),
            ("Karambwans", "65", "25–35k", "3-tick; feeds 1-tick Cooking later."),
            ("Monkfish", "62", "~30k",
             "Piscatoris. Modest XP but steady, and the fish are worth banking for Slayer trips."),
            ("Aerial fishing", "43 (+ 35 Hunter)", "35–50k",
             "Trains Fishing and Hunter together at Lake Molch, and pays in molch pearls."),
            ("Leechfin fishing", "78", "verify",
             "Newer method from the Varlamore content. Check the wiki for current rates before committing."),
            ("Dark crabs", "85 (+ Wilderness)", "~25k",
             "The best fishing GP in the game, at the cost of being in the deep Wilderness with a lobster pot."),
            ("Anglerfish", "82", "~30k", "Slow but good money and the best non-boss food."),
        ],
        notes=[
            "Drift Net is clearly right for the 70/70 requirement. For the eventual 99, most people switch to 3-tick Barbarian Fishing or minnows.",
            "If you'd rather not tick-manipulate for hours, Tempoross to 99 is slower but far more pleasant.",
        ],
    ),
    dict(
        name="Hunter", group=GATHER, target="70 → 99", pick="Drift Net Fishing",
        phase="70 for the quest cape block (paired with Fishing). Not in the explicit post-Diary list. Slot it with the gathering skills.",
        summary="Drift Net Fishing with Fishing.",
        methods=[
            ("Drift Net Fishing", "44 Hunt / 47 Fish", "40–60k each", "Your Pick for the 70/70 requirement."),
            ("Hunter Rumours (Hunters' Guild)", "Varlamore", "80–120k", "Varlamore contract system. Strong XP with useful rewards; the modern default for high Hunter."),
            ("Black chinchompas", "73", "150–250k", "Best XP in the skill and excellent GP, but deep Wilderness. High risk, high reward."),
            ("Red chinchompas", "63", "100–150k", "Safer, still good, and it stockpiles the chins you'll want for 99 Ranged."),
            ("Letvek and stymphikes", "76 / 82 (+ Blood Moon Rises)", "~145k",
             "Vampyrium. Box-trap letvek at 76 as bait, then hunt stymphikes at 82. With 3-tick manipulation this is the fastest Hunter in the game."),
            ("Razor-backed kebbits", "49", "80–100k",
             "Deadfall trapping in the Piscatoris hunter area. The standard bridge between falconry and chinning."),
            ("Herbiboar", "80 (+ 31 Herb)", "60–80k", "Slower XP, but pays out herbs continuously. Requires Fossil Island access and Bone Voyage."),
            ("Falconry", "43", "60–80k",
             "Spotted and dark kebbits at Piscatoris. No traps, just clicking, and it is the fastest option in its band."),
            ("Birdhouse runs", "5+", "passive", "Two minutes every 50 minutes. Free XP forever. Start doing these now regardless of method."),
        ],
        notes=[
            "Set birdhouse runs as a habit from today; over a max grind they are worth several levels for almost no time.",
            "Chinchompa hunting doubles as Ranged ammunition. It's the natural bridge between your Hunter and Ranged goals.",
        ],
    ),
    dict(
        name="Agility", group=GATHER, target="71 → 99", pick=None,
        phase="71 for the quest cape block, 99 in the slow-skills block.",
        summary="Rooftops, then Hallowed Sepulchre.",
        methods=[
            ("Rooftop courses", "10–90", "20–60k", "Canifis 40, Seers' 60, Pollnivneach 70, Rellekka 80, Ardougne 90. Marks of grace fund graceful."),
            ("Hallowed Sepulchre", "52", "50–90k", "The main 99 route. XP scales with floors unlocked (62/72/82/92) and it's genuinely profitable."),
            ("Colossal Wyrm course", "50 (62 advanced)", "50–70k",
             "The Varlamore course. Pays in wyrm agility tickets for the Colossal Wyrm rewards."),
            ("Prifddinas rooftop", "75 (+ Song of the Elves)", "~60k", "Highest rooftop rate; also drops crystal shards."),
            ("Wilderness Agility Course", "47", "45–60k",
             "Faster than rooftops in its band and drops from the pile at the end, but you are in the Wilderness."),
            ("Brimhaven Agility Arena", "1+", "15–40k", "Slow XP but tickets buy graceful/pet-adjacent rewards. Mostly skipped now."),
            ("Werewolf Skullball", "—", "low", "Only useful for very early levels."),
        ],
        notes=[
            "Your plan doesn't name a method. Rooftops to 52, then Hallowed Sepulchre the rest of the way, is the standard and pays for itself.",
            "Agility is one of the true slow skills. The plan correctly puts 99 late. Do the 71 requirement, then leave it.",
            "Get full graceful early; the run-energy restore compounds across every other skill you train.",
        ],
    ),
    dict(
        name="Thieving", group=GATHER, target="75 → 99", pick=None,
        phase="75 for the quest cape block. Not listed in the post-Diary maxing order, so slot the 99 in with the faster skills.",
        summary="Blackjacking or Pyramid Plunder.",
        methods=[
            ("Blackjacking", "The Feud, 45/65", "200–300k", "Bearded bandits at 45, Menaphite thugs at 65. The fastest Thieving in the game and the most tick-intensive."),
            ("Pyramid Plunder", "21 (71 useful)", "100–260k", "Scales hard with level; the final room at 91 is where the top rates are. Good artefact money and no tick manipulation."),
            ("Stealing artefacts", "49", "60–80k",
             "Port Piscarilius artefact runs. Safe, steady, and it needs no tick manipulation."),
            ("Ardougne knights", "55 + Ardy medium", "100–130k", "Bank-adjacent, decent GP, much easier on the hands than blackjacking."),
            ("Varlamore valuables", "50", "60–90k",
             "Stealing valuables around Civitas illa Fortis. Modern alternative to knights with better GP."),
            ("Vyres", "Sins of the Father", "~200k", "High level only. Blood shards make it the best GP in the skill."),
            ("Rogues' Castle chests", "84", "100–130k",
             "Deep Wilderness chests. Among the best rates in the skill if you accept the PKer risk."),
            ("Master farmers", "38", "low", "Seed money rather than XP."),
            ("Sorceress's Garden", "1+", "low", "Early levels and free sq'irks; largely skipped now."),
        ],
        notes=[
            "Rogue's outfit (Rogues' Den) gives double loot and is worth grabbing before any long stint.",
            "Ardougne medium diary is the single biggest quality-of-life unlock here: knights become far more reliable.",
            "Your plan needs 75 for quests, which Pyramid Plunder reaches comfortably without tick manipulation.",
        ],
    ),
    dict(
        name="Mining", group=GATHER, target="99 (slow-skills block)", pick=None,
        phase="Slow-skills block, after Runecraft and Agility.",
        summary="Motherlode Mine or Volcanic Mine.",
        methods=[
            ("Motherlode Mine", "30", "30–65k", "The AFK standard. Prospector kit, upper level at 72, pay-dirt sack upgrades. Gives free ores and nuggets."),
            ("Shooting Stars", "10 (60+ useful)", "20–40k",
             "Crashed stars, a Distraction and Diversion. One click every 7 minutes, so it is the most AFK Mining there is, and stardust buys the celestial ring (+4 invisible Mining boost). Star tier scales with your level."),
            ("Volcanic Mine", "70 (+ quests)", "70–100k", "Fastest non-tick-manipulated Mining. Group activity, needs attention."),
            ("3-tick iron / granite", "15 / 45", "60–100k", "Top rates if you're willing to tick-manipulate. Granite at the Quarry, iron at the Mining Guild."),
            ("Rubium rocks", "48 Mining, 60 Sailing", "50-80k",
             "Charred Dungeon, reached by docking at Charred Island. Higher XP than the nearby deposits but much more attention; the deposits at 68 are the AFK version."),
            ("Amethyst", "92", "~20k", "Very AFK and profitable; used mainly for the last stretch or while doing something else."),
            ("Calcified rocks", "41 (+ Fossil Island)", "25–45k",
             "Underwater at Fossil Island. Very low attention and no competition for rocks."),
            ("Zalcano", "70 (+ Song of the Elves)", "40–60k",
             "Group boss that pays in crystal shards and Zalcano shards alongside the XP."),
            ("Infernal shale", "78", "verify",
             "Chasm of Fire. The crushed shale is what oathplate armour is made from, so the value is in the drops rather than the rate."),
            ("Blast Mine", "Lovakengj", "40–60k", "Good GP, decent XP, high click intensity."),
        ],
        notes=[
            "Check whether Mining shows up in your remaining elite diary requirements before deciding how far to push it early.",
            "Motherlode's nuggets buy the prospector kit and the sack upgrades. Do those first, they permanently improve the rate.",
        ],
    ),
    dict(
        name="Woodcutting", group=GATHER, target="99 (slow-skills block)", pick="Forestry teaks",
        phase="Slow-skills block.",
        summary="Forestry teaks (2-tick).",
        methods=[
            ("Forestry teaks", "35", "80–150k", "Your Pick. 2-tick teaks with Forestry events layered on top is the top sustained rate; the events also fund the Forestry shop."),
            ("Sulliuscep", "65 (+ Fossil Island)", "70–90k", "Fast, and drops fossils for the museum. A good change of pace."),
            ("Redwoods", "90", "~65k", "The AFK 99. Low rate, almost no attention."),
            ("Ironwood / rosewood trees", "80 / 92", "70–110k",
             "The high-level trees added alongside Sailing. Rosewood at 92 feeds the rosewood hull, which is a straight Sailing XP multiplier."),
            ("Bloodwood trees", "77 (+ Blood Moon Rises)", "~55k",
             "Vampyrium. Needs an empty bucket; the sap upgrades arrows into seeking arrows. Slower than teaks, worth it for the sap."),
            ("Yews / Magics", "60 / 75", "30–50k", "Slow but profitable; mostly obsolete for XP."),
            ("Blisterwood tree", "62 (+ Sins of the Father)", "~60k",
             "No competition, banks itself through the Darkmeyer bank, and drops blisterwood logs for vampyre gear."),
            ("Woodcutting Guild", "60", "—", "Invisible +7 boost and a bank; use it wherever it applies."),
        ],
        notes=[
            "Teaks are correct. Nothing else combines rate and accessibility as well.",
            "If 2-ticking wears you out, alternate with Sulliuscep trips or Forestry group events.",
        ],
    ),
    dict(
        name="Runecraft", group=GATHER, target="65 → 77 → 99", pick="Guardians of the Rift",
        pick_note="ZMI is the named fallback in the plan if you would rather train solo without the minigame timer.",
        phase="65 for the quest cape block, ~77 relatively early (blood runes), 99 first in the slow-skills block.",
        summary="GOTR, then blood runes or ZMI.",
        methods=[
            ("Guardians of the Rift", "27", "40–80k", "Your Pick. XP scales with level, plus pouches, the Abyssal needle, outfit and eventually the pet. The default modern Runecraft."),
            ("ZMI altar", "50 (+ Lunar Diplomacy)", "40–70k", "Consistent, solo, no minigame timer. Needs pouches and the Ourania teleport."),
            ("Blood runes (Arceuus)", "77", "~40k", "Low attention, strong profit. This is why the plan wants 77 early. It turns Runecraft into passive income."),
            ("Lava runes with runners", "23", "80–130k",
             "The classic runner method. Far faster than solo lavas, but you depend on other players showing up."),
            ("Lava runes (binding necklace)", "23", "50–80k", "Cheap and fast; requires a lot of clicking through the abyss."),
            ("Mud runes", "23 (+ Lunars)", "60–100k",
             "Binding necklace runs like lavas but with the Magic Imbue spell instead of an earth talisman staff. Similar rate; take whichever is cheaper."),
            ("Aether runes with runners", "90", "verify",
             "The top-end runner method. Newer, so check current rates on the wiki."),
            ("Wrath runes", "95", "~60k", "Best XP and money at the very top end."),
            ("Daeyalt essence", "Sins of the Father", "+XP", "Straight multiplier on any essence-based method. Get it before long Runecraft sessions."),
        ],
        notes=[
            "Reaching 77 early is the highest-value part of this skill's plan: blood runes then run in the background for the rest of the account.",
            "Get all four pouches and the Abyssal needle/outfit from GOTR before committing to the long grind.",
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
        name="Sailing", group=GATHER, target="99 (slow-skills block)", pick=None,
        phase="Listed last in the slow-skills block. Pandemonium has to be done before any Sailing XP is possible, so it also belongs in your quest list.",
        summary="Barracuda Trials, or courier runs.",
        methods=[
            ("Barracuda Trials", "30 / 55 / 72", "80–200k", "The fastest Sailing from 30 onwards. Tempor Tantrum at 30, Jubbly Jive at 55, Gwenith Glide at 72; each has Swordfish/Shark/Marlin ranks with tighter timers. Gwenith Glide at Marlin rank reaches 200k+ with a rosewood hull and a crystal extractor running."),
            ("Courier tasks", "1 (46+ useful)", "30–145k", "Cargo runs between ports. Summer Shore 46–55 gives ~30k, Rellekka 62–70 gives 55–90k, Prifddinas 70–72 gives 65–70k, and Lunar Isle round trips from 76 give 120–145k once you can hold five tasks at 84. Far less intense than trials."),
            ("Sea charting", "1", "~10k", "The starting method and the best XP before 30. One-off task rewards tracked in the captain's log, with bonuses for clearing a region. Charting everything needs 78 Sailing and unlocks horizon's lure, a permanent 2.5% Sailing XP boost."),
            ("Bounty tasks", "30", "middle", "Kill an assigned sea monster for its bounty drop, structured like Hunter Rumours. Sits between salvaging and trials for rate, pays well, and at 80+ every task is available. Magic or Ranged with a cannon crew."),
            ("Shipwreck salvaging", "15 (42 better)", "8–40k", "The AFK option. Two salvaging hooks, a salvaging station and crewmates on a sloop; a crewmate on your hook makes it nearly idle at roughly 8k/hr. Tick manipulation roughly doubles it if you want to work for it."),
            ("Deep sea trawling", "Fishing hybrid", "moderate", "Trawling nets over fish shoals. Trains Sailing while producing raw deep-sea fish, so it doubles up with your Fishing goal."),
            ("Crystal extractor", "73 (+ 67 Con)", "+10–15k", "Not a method, a passive top-up. 250 XP per harvest roughly every 63 seconds, stacking on top of whatever else you are doing. Build it as soon as you hit 73."),
            ("Wyrmscraig", "62", "not live yet",
             "The player-designed island lands 29 July 2026 in the Unquiet Ocean. It gates Mortimer, the new Slayer master, behind The Fallen From Grace. Expect the rate picture here to move once it is out."),
            ("Ocean encounters", "1", "passive", "Glows, strong winds and castaways while sailing. No requirement; trim your sails every time for the free XP."),
        ],
        notes=[
            "Pandemonium is mandatory before any training, and several quests give Sailing XP. Chart the seas to about 30, then switch to Barracuda Trials.",
            "The plan puts Sailing in the slow block, which fits: it is the newest skill and its rates are still being balanced. Re-check the wiki guide before the long grind.",
            "Two permanent multipliers are worth detouring for: horizon's lure from full charting (78 Sailing, 2.5% bonus to everything) and the crystal extractor at 73 Sailing plus 67 Construction.",
            "Boat speed is XP rate. A rosewood hull at 93 Sailing and 84 Construction is about 20% faster, which is roughly 15% more XP per hour on trials.",
            "If you want the least attention-heavy route, salvaging with crewmates and courier runs get there without any tick manipulation, just slower.",
            "Deep sea trawling overlaps with Fishing, so it is the natural pick on days you want both skills moving.",
        ],
    ),
    # ---------------- artisan ----------------
    dict(
        name="Smithing", group=ARTISAN, target="75 → 99", pick=None,
        phase="75 for the quest cape block, then the buyables block at the end.",
        summary="Blast Furnace or Giants' Foundry.",
        methods=[
            ("Blast Furnace – gold bars", "40 (60 for best rate)", "~350k", "With goldsmith gauntlets, the fastest Smithing XP in the game. Loses GP; you're buying levels."),
            ("Giants' Foundry", "15", "150–300k", "Good XP with no real loss, plus moulds and the Smiths' uniform, which speeds up every later anvil session. The best all-round option."),
            ("Cannonballs", "35", "~20k", "Extremely AFK and profitable. Terrible XP rate. Only for background training."),
            ("Blast Furnace – other bars", "varies", "100–250k", "Runite bars at 85 are profitable rather than costly."),
            ("Rune items (3-bar)", "95", "~120k",
             "Profitable at the very top end, unlike gold bars."),
            ("Anvil smithing (plates/darts)", "varies", "50–150k", "Mostly obsolete since Giants' Foundry."),
        ],
        notes=[
            "Get the Smiths' uniform from Giants' Foundry early. It is not an XP bonus: each piece gives a 20% chance to cut anvil actions from 5 ticks to 4, so the full set is effectively a quarter faster at the anvil, plus better preform progress in the Foundry.",
            "For the 75 requirement, Giants' Foundry is the cheapest sane route. Save gold-bar blasting for the final push to 99 when you have GP to burn.",
        ],
    ),
    dict(
        name="Crafting", group=ARTISAN, target="90 → 99", pick=None,
        phase="90 as an interim target, 99 in the buyables block.",
        summary="D'hide bodies or battlestaves.",
        methods=[
            ("Dragonhide bodies", "63/71/77/84", "150–300k", "Green 63, blue 71, red 77, black 84. Simple, scalable, moderately expensive."),
            ("Battlestaves", "54–66", "150–250k", "Water 54, earth 58, fire 62, air 66. Buy orbs, attach to staves. Often the cheapest GP per XP."),
            ("Glassblowing / Superglass Make", "77 Magic", "150–250k", "Lunar spell + molten glass. Good rate; light hourly cost."),
            ("Crafting drift nets", "26", "low",
             "Worth knowing because you will be running Drift Net Fishing anyway; make your own nets instead of buying them."),
            ("Gem cutting", "varies", "100–200k", "Dragonstones and up are fast; usually a loss."),
            ("Amethyst", "—", "low", "AFK bolt tips/arrowtips while doing something else."),
        ],
        notes=[
            "Your plan sets 90 as an interim target. Check which elite diary or quest wants it and stop exactly there before moving on.",
            "Battlestaves vs d'hide is a pure GP question; price-check both before committing, they swap places regularly.",
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
        name="Construction", group=ARTISAN, target="83–85 → 99", pick=None,
        phase="83–85 early for the house upgrades that matter, 99 in the buyables block.",
        summary="Mahogany Homes, then oak/mahogany builds.",
        methods=[
            ("Mahogany Homes", "20+", "50–120k", "Contracts. By far the cheapest GP per XP, plus the carpenter's outfit and plank sack. The right way to reach your 83–85 target."),
            ("Oak larders", "33", "~180k", "Classic butler-based training; cheap planks, high clicks."),
            ("Oak dungeon doors", "74", "~250k", "The mid-game standard once you pass 74."),
            ("Mounted mythical capes", "50 (+ Dragon Slayer II)", "~200k",
             "Teak-based and cheaper per XP than mahogany furniture, with a butler doing the running."),
            ("Mahogany tables", "52", "~300k+", "Fast and very expensive."),
            ("Shipwrights' workbench", "Sailing content", "verify",
             "Boat facilities built at the workbench. Ties Construction into your Sailing goals; check the wiki for current rates."),
            ("Teak garden benches", "66", "~350k", "Similar rate to mahogany tables, usually cheaper per XP."),
        ],
        notes=[
            "83–85 is a sensible early target. Gilded altar (75), the ornate pool, and the spirit tree/fairy ring portals pay for themselves across the rest of the plan.",
            "Do Mahogany Homes for the outfit and plank sack first even if you then switch methods; both cut the eventual 99 cost noticeably.",
            "Unlock the demon butler before any bulk-building session.",
        ],
    ),
    dict(
        name="Herblore", group=ARTISAN, target="99 (buyables block)", pick=None,
        phase="Buyables block, after Construction.",
        summary="Potions. Cheapest available tier.",
        methods=[
            ("Mastering Mixology", "60 (81 better)", "60–90k",
             "The Aldarin minigame. Cheaper per XP than buying potions outright and it pays in mixology rewards, including the alchemist's amulet."),
            ("Unfinished potions", "any", "up to ~300k", "Making unfinished potions is the fastest raw XP per hour, though XP per herb is lower."),
            ("Prayer potions", "38", "~150k", "Reliable, usually near break-even."),
            ("Super restores", "63", "~180k", "The long mid-game staple."),
            ("Stamina potions", "77", "~200k", "Amylase from Marks of Grace makes these cheap if you've been doing rooftops."),
            ("Super combat potions", "90", "~250k", "The standard 99 finisher; you'll drink plenty anyway."),
            ("Extended super antifires", "98", "~250k", "Only relevant for the last level."),
        ],
        notes=[
            "Herblore is a pure buyable. The plan is right to leave it late. Bank every herb you get from Slayer, Herbiboar and farm runs in the meantime.",
            "Clean herbs and make unfinished potions during any AFK activity; it costs almost nothing to bank a stockpile over months.",
        ],
    ),
    dict(
        name="Cooking", group=ARTISAN, target="99 (buyables block)", pick=None,
        phase="Buyables block, near the end.",
        summary="Wines or 1-tick karambwans.",
        methods=[
            ("Jugs of wine", "35", "300–450k", "The fastest and cheapest 99 Cooking. Mind-numbing but short."),
            ("1-tick karambwans", "30", "700k+", "The fastest cooking in the game by a wide margin, and it needs perfect tick timing."),
            ("Bake Pie", "10 (+ 65 Magic)", "~150k",
             "The Lunar spell. Trains Cooking and Magic at once, which is why it shows up in both guides."),
            ("Fish at Hosidius / Myths' Guild", "varies", "150–250k", "Range next to a bank; no burning at Hosidius."),
            ("Sharks / Anglerfish", "80/84", "—", "Cook what you catch if you fished it yourself."),
        ],
        notes=[
            "One of the fastest 99s remaining. Wines are the low-effort answer; karambwans if you want it over in a couple of days.",
        ],
    ),
    dict(
        name="Firemaking", group=ARTISAN, target="75 → 99", pick="Wintertodt",
        phase="75 for the quest cape block, last in the buyables block.",
        summary="Wintertodt.",
        methods=[
            ("Wintertodt", "50", "150–300k", "Your effective pick. Profitable, sociable, gives the pyromancer outfit, herbs, seeds and gems. Almost everyone does 50–99 here."),
            ("Burning logs at a bank", "varies", "200–400k", "Faster raw XP with magic/redwood logs, but pure GP loss and zero rewards."),
            ("Forestry bonfires", "—", "bonus", "Group bonfires during Forestry events add XP while you cut teaks."),
            ("Fire pits / wilderness ring", "—", "—", "Situational only."),
        ],
        notes=[
            "Wintertodt for the 75 requirement and then again for 99 is the obvious call; the supply drops effectively pay you to train.",
            "The pyromancer outfit gives an XP bonus. Get the full set early in the grind, not late.",
        ],
    ),
]

DIARY = dict(
    name="Diaries", group=SUPPORT, target="Hard → Elite", pick=None,
    phase="All Hard diaries after the Quest Cape; elite skill requirements cleared during the Slayer 72→95 stretch.",
    summary="Hard diaries, then elite skill walls.",
    methods=[
        ("Hard diaries", "—", "—", "Do these as a block after the Quest Cape. Most requirements will already be met by then."),
        ("Elite diaries", "—", "—", "The remaining walls are skill levels, not content. Clear them opportunistically while training Slayer to 95."),
    ],
    notes=[
        "Diary rewards compound: Ardougne cloak teleports, Karamja gloves for Slayer, Morytania legs for barrows, Fremennik boots for run energy, Varrock armour for Mining.",
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


# plain marks for the two entries that are not a thing in the game
REF_SVG = {
    "progression": ('<svg class="refsvg" viewBox="0 0 16 16" width="14" height="14" '
                    'aria-hidden="true"><path d="M2 13h3V8H2zM6.5 13h3V5h-3zM11 13h3V2h-3z" '
                    'fill="currentColor"/></svg>'),
    "skills": ('<svg class="refsvg" viewBox="0 0 16 16" width="14" height="14" '
               'aria-hidden="true"><rect x="2" y="2" width="5" height="5" rx="1.2" '
               'fill="currentColor"/><rect x="9" y="2" width="5" height="5" rx="1.2" '
               'fill="currentColor" opacity=".65"/><rect x="2" y="9" width="5" height="5" '
               'rx="1.2" fill="currentColor" opacity=".65"/><rect x="9" y="9" width="5" '
               'height="5" rx="1.2" fill="currentColor"/></svg>'),
}


PLAN_LINKS = [
    ("progression", "Progression", "assets/media/site/combat-achievements.png"),
    ("quests", "Quests", "assets/media/site/quests.png"),
    ("diaries", "Diaries", "assets/icons/Diaries.png"),
    ("approach", "Slayer", "assets/icons/Slayer.png"),
    ("max-order", "Max Order", "assets/media/max-cape.png"),
    ("outfits", "Gear", "assets/media/site/gear-icon.png"),
    ("skills", "Skills", "assets/media/site/skills-icon.png"),
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
except (OSError, ValueError):
    MANIFEST = {}
    print("warning: no assets/media/manifest.json, run fetch_media.py", file=sys.stderr)

SKILL_NAMES = {s["name"] for s in SKILLS if s["group"] != SUPPORT}

# alias -> (kind, path-fragment); skills use their pixel icon, everything else
# the downloaded wiki thumbnail
_ALIASES = {}
for _n in SKILL_NAMES:
    _ALIASES[_n] = ("skill", f"assets/icons/{_n}.png")
for _d in ("Diary", "Diaries", "diary", "diaries", "Achievement Diary",
           "Achievement Diaries", "Diary Cape"):
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

QUESTS_PATH = os.path.join(OUT, "data", "quests.json")
try:
    with open(QUESTS_PATH, encoding="utf-8") as _f:
        QUESTS = json.load(_f)
except (OSError, ValueError):
    QUESTS = None

DIARIES_PATH = os.path.join(OUT, "data", "diaries.json")
try:
    with open(DIARIES_PATH, encoding="utf-8") as _f:
        DIARIES = json.load(_f)
except (OSError, ValueError):
    DIARIES = None

FOCUS_PATH = os.path.join(OUT, "data", "focus.json")
try:
    with open(FOCUS_PATH, encoding="utf-8") as _f:
        FOCUS = (json.load(_f) or {}).get("skill")
except (OSError, ValueError):
    FOCUS = None

PICKS_PATH = os.path.join(OUT, "data", "picks.json")
try:
    with open(PICKS_PATH, encoding="utf-8") as _f:
        PICKS = json.load(_f)
except (OSError, ValueError):
    PICKS = {}

for _s in SKILLS:
    _chosen = PICKS.get(_s["name"])
    if _chosen and any(m[0] == _chosen for m in _s["methods"]):
        _s["pick"] = _chosen
        _s.pop("pick_note", None)

STATS_PATH = os.path.join(OUT, "data", "stats.json")
try:
    with open(STATS_PATH, encoding="utf-8") as _f:
        STATS = json.load(_f)
except (OSError, ValueError):
    STATS = None


def stat_of(skill_name):
    if not STATS:
        return None
    return STATS.get("skills", {}).get(skill_name)


def milestones(skill):
    """Numeric level targets pulled from the plan's target string."""
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


WIKI = "https://oldschool.runescape.wiki/w/"
OQG_URL = WIKI + "Optimal_quest_guide"


def quest_link(name):
    return WIKI + urllib.parse.quote(name.replace(" ", "_"))


def quest_panel():
    """Where you are in the optimal quest guide, and what is left."""
    if not QUESTS:
        return ('<div class="panel"><div class="k">Quest Cape</div>'
                '<h3>Not Linked Yet</h3><p>Run <code>fetch_quests.py</code> once the '
                'WikiSync plugin has uploaded your account. It reads quest completion '
                'from RuneLite, which the hiscores do not carry.</p>'
                f'<p class="gap"><a class="btn ghost sm" href="{OQG_URL}" '
                'rel="noopener">Optimal quest guide</a></p></div>')

    done, total = QUESTS["done"], QUESTS["total"]
    pct = round(100 * done / total) if total else 0
    started = set(QUESTS.get("in_progress") or [])
    nxt = QUESTS.get("next")
    remaining = QUESTS.get("remaining") or []

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
        label = step["name"] + (f' &middot; {step["tier"]}' if step.get("tier") else "")
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
                    f'<a href="{WIKI}{step["wiki"]}" rel="noopener" target="_blank">'
                    f'{label}</a>{tag}</li>')

    remaining = [s for s in route if s["state"] in (0, 1)]
    nxt = (nxt_step.get("name", "") +
           (f' ({nxt_step["tier"]})' if nxt_step.get("tier") else ""))
    started = [s for s in route if s["state"] == 1]

    synced = (QUESTS.get("synced") or "")[:10]
    return (
        '<div class="questbox">'
        '<div class="qhead">'
        f'<div><div class="k">Quest Cape</div>'
        f'<div class="qcount"><b class="num">{done}</b>'
        f'<span>of {total} done</span></div></div>'
        f'<div class="qright"><b class="num">{len(remaining)}</b>'
        '<span>to go</span></div>'
        "</div>"
        f'<span class="prog wide"><span class="fill" style="width:{pct}%"></span></span>'
        + (f'<p class="qnow">Next in the guide: '
           f'<a href="{WIKI}{nxt_step.get("wiki", "")}" rel="noopener" '
           f'target="_blank"><b>{e(nxt)}</b></a>'
           + (f' &middot; {len(started)} part-finished' if started else "")
           + "</p>" if nxt else
           '<p class="qnow">Every step in the guide is done.</p>')
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


def mini_bar(pct, colour=None):
    style = f"width:{max(0, min(100, pct))}%"
    if colour:
        style += f";--lc:{colour}"
    return f'<span class="prog mini"><span class="fill lit" style="{style}"></span></span>'


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
            f'{mini_bar(pct, level_color(cur))}</span>')


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
            f'{mini_bar(pct, level_color(min(99, cb)))}</span>')


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
                f'<span>of {goal} Slayer</span>{mini_bar(pct, level_color(cur))}</div>')

    if kind == "max" and STATS:
        skills_only = [x for x in SKILLS if x["group"] != SUPPORT]
        done = sum(1 for x in skills_only
                   if (stat_of(x["name"]) or {}).get("level", 1) >= 99)
        total = len(skills_only)
        pct = round(100 * done / total)
        cur_total = STATS.get("overall", {}).get("level")
        return (f'<div class="pmeter"><b>{done}</b><span>of {total} skills at 99</span>'
                f'{mini_bar(pct)}<span class="pn">total level {cur_total}</span></div>')

    return ""


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


def focus_panel():
    name = default_focus()
    sk = next(x for x in SKILLS if x["name"] == name)
    f = skill_facts(sk)
    lvl = f["level"] if f["level"] is not None else "--"
    xp = f"{f['xp']:,}" if f["xp"] is not None else "--"

    also = "".join(
        f'<a class="fa" href="{a["href"]}"><img class="icon sm" src="{a["icon"]}" alt="">'
        f'<span class="fan">{e(a["name"])}</span>'
        f'<b class="fal" style="--lc:{a["colour"]}">{a["level"] if a["level"] else "--"}</b>'
        f'<span class="fag">/{a["goal"]}</span></a>'
        for a in f["also"]
    )

    return (
        '<aside class="focus" id="focus">'
        '<div class="fhead"><span class="k">Currently Levelling</span>'
        f'<a class="flink" id="flink" href="{f["href"]}">Open {e(f["name"])} &rsaquo;</a></div>'
        '<div class="ftop">'
        f'<img class="icon lg" id="fic" src="{f["icon"]}" alt="">'
        f'<span class="fname" id="fname">{e(f["name"])}</span>'
        f'<b class="fbig lit" id="flvl" style="--lc:{f["colour"]}">{lvl}</b>'
        f'<span class="fsep">&rarr;</span><span class="fgoal" id="fgoal">{f["goal"]}</span>'
        '<span class="fspace"></span>'
        f'<a class="fmethod" id="fmethodlink" href="{f["methodHref"]}">'
        f'<i>Method</i><b id="fmethod">{e(f["method"])}</b></a>'
        "</div>"
        '<div class="fbarrow">'
        f'<span class="prog wide"><span class="fill lit" id="fbar" '
        f'style="width:{f["pct"]}%;--lc:{f["colour"]}"></span></span>'
        f'<span class="fxp" id="fxp">{xp} xp</span>'
        "</div>"
        f'<div class="falso" id="falso"{"" if also else " hidden"}>'
        f'<i>Also Trains</i>{also}</div>'
        "</aside>"
    )


def focus_data_script():
    data = {x["name"]: skill_facts(x) for x in SKILLS}
    return ("<script>window.FOCUSDATA=" + json.dumps(data, separators=(",", ":"))
            + ";window.FOCUSNOW=" + json.dumps(default_focus()) + ";</script>")


MAX_TOTAL = sum(1 for x in SKILLS if x["group"] != SUPPORT) * 99
MAX_COMBAT = 126


def rail_meter(root=""):
    """Account line at the top of the index: total level and combat."""
    spin = ('<button class="refresh" type="button" hidden '
            'title="Refresh from the hiscores" aria-label="Refresh from the hiscores">'
            '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">'
            '<path d="M13.6 8a5.6 5.6 0 1 1-1.7-4" fill="none" stroke="currentColor" '
            'stroke-width="1.7" stroke-linecap="round"/>'
            '<path d="M13.4 1.4v3h-3" fill="none" stroke="currentColor" '
            'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
            '</svg></button>')

    if STATS:
        rows = (f'<span class="mrow"><span>Total Level</span>'
                f'<b class="num" data-stat="total">{STATS.get("overall", {}).get("level")}</b>'
                f'<span class="mmax">/{MAX_TOTAL}</span>{spin}</span>'
                f'<span class="mrow"><span>Combat</span>'
                f'<b class="num" data-stat="combat">{STATS.get("combat")}</b>'
                f'<span class="mmax">/{MAX_COMBAT}</span>'
                f'<span class="spacer"></span></span>')
    else:
        rows = (f'<span class="mrow"><span>Not linked</span>{spin}</span>'
                '<span class="mrow hint"><code>fetch_stats.py "RSN"</code></span>')

    return f'  <div class="meter">{rows}</div>'


def rail(active=None, depth=0):
    """Sticky right-hand index: the plan on top, then every skill by group."""
    root = "../" if depth else ""
    p = ['<aside class="rail" aria-label="Site index">',
         rail_meter(root),
         '  <nav class="rail-body">',
         '  <div class="rail-kick">Reference</div>']
    for anchor, label, ico in PLAN_LINKS:
        mark = (REF_SVG[ico[4:]] if ico.startswith("svg:")
                else f'<img class="refico" src="{root}{ico}" alt="" width="15" height="15">')
        p.append(f'  <a href="{root}index.html#{anchor}">{mark}'
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
            f'<span class="r-lvl{cls}"{style}>{e(tag)}</span></a>'
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
            f'<a class="vid" href="https://www.youtube.com/watch?v={vid}{extra}" '
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
    rows.forEach(function (r) { r.classList.toggle('chosen', r === row); });
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
        setBonus(row.getAttribute('data-skill'),
                 parseInt(row.getAttribute('data-bonus'), 10), have === total);
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
    refresh(false);
  });
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
    return text.replace(/(\d[\d,]*(?:\.\d+)?)(\s*k)?/gi, function (all, num, k) {
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
    list.innerHTML = live.slice(0, limit).map(function (s) {
      var tier = int(s.tier), world = int(s.world);
      var req = tier * 10;
      var can = !mining || mining >= req;
      var hit = findMap(s.location);
      var loc = esc(tidy(hit && hit.n ? hit.n : s.location));
      var map = 'https://oldschool.runescape.wiki/w/Special:Search?go=Go&search='
        + encodeURIComponent(hit && hit.n ? hit.n : s.location);
      return '<div class="star' + (can ? '' : ' locked') + '">'
        + '<span class="stier' + (tier >= 7 ? ' hot' : '') + '" title="Tier ' + tier
        + ', needs ' + req + ' Mining">T' + tier + '</span>'
        + '<span class="sworld">' + world + '</span>'
        + '<a class="sloc" href="' + map + '" target="_blank" rel="noopener" '
        + 'title="Find ' + loc + ' on the wiki">' + loc + '</a>'
        + '<button class="sview" type="button" data-loc="' + loc + '" '
        + 'title="Map area. Click to open the tracker">view</button>'
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
    return String(t).toLowerCase().replace(/\(.*?\)/g, ' ')
      .replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
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
    if (ev.target.closest('.sview')) {
      window.open('https://07.gg/trackers/shooting-star', '_blank', 'noopener');
    }
  });

  btn.addEventListener('click', load);
  load();
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
      filters.forEach(function (b) { b.classList.toggle('on', b === btn); });
      rows.forEach(function (r) {
        r.hidden = want !== 'all' && r.getAttribute('data-tag') !== want;
      });
    });
  });

  sorts.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var key = btn.getAttribute('data-s');
      sorts.forEach(function (b) { b.classList.toggle('on', b === btn); });
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
    return n == null ? '--' : String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
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
    set('fxp', fmt(f.xp) + ' xp');
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

LIVE_JS = """
<script>
/* Pulls the hiscores through serve.py's /api/stats proxy. The hiscores send no
   CORS headers, so a static page cannot call them directly. */
(function () {
  var btn = document.querySelector('.refresh');
  if (!btn || !/^https?:$/.test(location.protocol)) return;
  btn.hidden = false;

  function xpFor(l) {
    var t = 0;
    for (var i = 1; i < l; i++) t += Math.floor(i + 300 * Math.pow(2, i / 7));
    return Math.floor(t / 4);
  }

  function apply(d) {
    var skills = d.skills || {}, left = 0;
    document.querySelectorAll('[data-skill-level]').forEach(function (el) {
      var s = skills[el.getAttribute('data-skill-level')];
      if (s) el.textContent = s.level;
    });
    document.querySelectorAll('[data-skill-bar]').forEach(function (el) {
      var s = skills[el.getAttribute('data-skill-bar')];
      if (!s) return;
      var from = parseInt(el.getAttribute('data-from'), 10) || 1;
      var goal = parseInt(el.getAttribute('data-goal'), 10) || 99;
      var lo = xpFor(from), hi = xpFor(goal);
      var pct = hi <= lo ? 100 : Math.round(100 * (s.xp - lo) / (hi - lo));
      el.style.width = Math.max(0, Math.min(100, pct)) + '%';
    });
    Object.keys(skills).forEach(function (k) { if (skills[k].level < 99) left++; });
    var set = function (key, val) {
      var el = document.querySelector('[data-stat="' + key + '"]');
      if (el && val != null) el.textContent = val;
    };
    set('left', left);
    set('total', d.overall && d.overall.level);
    set('combat', d.combat);
  }

  btn.addEventListener('click', function (ev) {
    ev.preventDefault();
    if (btn.classList.contains('busy')) return;
    btn.classList.add('busy');
    btn.classList.remove('ok', 'bad');
    var started = Date.now();
    var settle = function (fn) {
      setTimeout(fn, Math.max(0, 1400 - (Date.now() - started)));
    };
    fetch('/api/stats', { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || d.error) throw new Error(d && d.error || 'failed');
        settle(function () {
          apply(d);
          btn.classList.remove('busy');
          btn.classList.add('ok');
          btn.title = 'Updated just now';
          setTimeout(function () { btn.classList.remove('ok'); }, 2500);
        });
      })
      .catch(function (err) {
        settle(function () {
          btn.classList.remove('busy');
          btn.classList.add('bad');
          btn.title = String(err.message || err).slice(0, 60);
          setTimeout(function () { btn.classList.remove('bad'); }, 3000);
        });
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
  if (here && here.scrollIntoView) here.scrollIntoView({ block: 'nearest' });
})();
</script>
"""


def page(title, where, body, active=None, depth=0, skill_name=None):
    root = "../" if depth else ""
    del where  # the header no longer shows a breadcrumb
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{e(title)}</title>
<link rel="preload" href="{root}assets/fonts/Geist-Regular.v1.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{root}assets/style.css">
{f'<script>window.SKILL={json.dumps(skill_name)};</script>' if skill_name else ""}
{focus_data_script()}
</head>
<body>
<header class="topbar">
  <a class="mark" href="{root}index.html"><img class="capemark" src="{root}assets/media/max-cape.png" alt="">OSRS max time wasting plan</a>
  <nav class="topnav">
    <a class="navlink" href="{root}stars.html">{COMET_SVG}Shooting Stars</a>
    <a class="navlink" href="{root}paths.html">Paths</a>
    <a class="navlink" href="{root}afk.html">AFK</a>
  </nav>
</header>
<div class="shell">
<main class="main">
{body}
</main>
{rail(active=active, depth=depth)}
</div>
{RAIL_JS}{LIVE_JS}{PICK_JS}{FOCUS_JS}{TASKS_JS}{STARS_JS}{BONUS_JS}{OWN_JS}
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

    for m in re.finditer(r"(\d{1,3})\s*\+?\s*([A-Za-z']+)?", text):
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


def unmet(req, own_skill):
    """First requirement your account does not meet, or None."""
    if not STATS:
        return None
    for skill, lvl in parse_reqs(req, own_skill):
        if skill == COMBAT_KEY:
            if (STATS.get("combat") or 0) < lvl:
                return f"{lvl} combat"
            continue
        st = stat_of(skill)
        if st and st["level"] < lvl:
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
    """"At 75 Crafting you can make blue. Red unlocks at 77." or None."""
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
    line = f'At {cur} {skill_name} the best tier open to you is <b>{e(best[1])}</b>.'
    if nxt:
        line += f' Next: {e(nxt[1])} at {nxt[0]}.'
    return line


# XP-affecting gear, per skill. `pct` is the effective XP-rate change, `applies`
# limits it to certain methods, and `note` says what the item actually does,
# because several of these are speed or loot effects rather than XP multipliers.
BONUSES = {
    "Mining": [dict(name="Prospector kit", pct=2.5, applies=None,
                    note="Full set, +2.5% Mining XP.")],
    "Fishing": [dict(name="Angler's outfit", pct=2.5, applies=None,
                     note="Full set, +2.5% XP from all Fishing.")],
    "Woodcutting": [dict(name="Lumberjack outfit", pct=2.5, applies=None,
                         note="Full set, +2.5% Woodcutting XP.")],
    "Firemaking": [dict(name="Pyromancer outfit", pct=2.5, applies=None,
                        note="Full set, +2.5% Firemaking XP.")],
    "Construction": [dict(name="Carpenter's outfit", pct=2.5, applies=None,
                          note="Full set, +2.5% Construction XP.")],
    "Farming": [dict(name="Farmer's outfit", pct=2.5, applies=None,
                     note="Full set, +2.5% Farming XP.")],
    "Hunter": [dict(name="Guild hunter outfit", pct=2.5, applies=None,
                    note="Full set, +2.5% catch rate, which is close enough to +2.5% XP per hour.")],
    "Smithing": [
        dict(name="Smiths' uniform", pct=25, applies=["Anvil smithing (plates/darts)",
                                                      "Cannonballs", "Rune items (3-bar)"],
             note="Each piece is a 20% chance to cut an anvil action from 5 ticks to 4; "
                  "the full set is about a quarter faster at the anvil."),
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


def method_table(methods, pick, skill_name=None):
    rows = []
    rec = best_for_level(methods, skill_name)
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
            btn = (f'<button class="pickbtn" type="button" disabled '
                   f'title="Needs {e(blocker)}" aria-label="Locked: needs '
                   f'{e(blocker)}">{LOCK_SVG}</button>')
        else:
            btn = (f'<button class="pickbtn" type="button" title="Use this method" '
                   f'aria-label="Use {e(name)}">{CHECK_SVG}</button>')
        tag = ""
        if blocker:
            tag = f'<span class="rtag lock">needs {e(blocker)}</span>'
        elif name == rec:
            tag = '<span class="rtag rec">best at your level</span>'
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
    ("Nieve / Steve", "Tree Gnome Stronghold", "85 combat", "12", "90"),
    ("Duradel / Kuradal", "Shilo Village", "Shilo Village, 100 combat + 50 Slayer", "15", "100"),
    ("Krystilia", "Edgeville", "Any level, Wilderness tasks", "25", "100"),
    ("Mortimer", "Wyrmscraig caverns", "The Fallen From Grace, 100 combat + 70 Slayer", "varies", "120"),
]

POINT_ORDER = [
    ("Block slots", "The single biggest lever. Blocking costs 100 points at Duradel and you get seven slots, one per 50 quest points, with the seventh behind the elite Lumbridge and Draynor diary."),
    ("Bigger and Badder", "50 points. Superior encounters carry the imbued heart and eternal gem, and can be toggled off freely."),
    ("Slayer helmet", "400 points for the helm plus the components. The imbued version is the best melee and magic head slot on task."),
    ("Extensions", "Only on tasks that already pay. Araxytes go from 60-80 to 200-250, which is worth it; metal dragons are not."),
    ("Everything else", "Slayer rings, Task Storage at 500 points, Gargoyle Smasher if you keep gargoyle tasks."),
]

MORTIMER = dict(
    live="Launches 29 July 2026 with Wyrmscraig, so this is what Jagex have published rather than settled community practice.",
    unlock="Reach the Wyrmscraig caverns during The Fallen From Grace, then 100 combat and 70 Slayer, or 99 Slayer at any combat level.",
    points=[
        "He offers two tasks to choose from, and a third once you have done 100 tasks for him.",
        "Every task comes with a modifier: bonus points, changed quantity, better clue rate, bonus Slayer XP, or a better superior unique roll.",
        "Modifiers unlock as you go: points and quantity from the start, clues at 25 tasks, XP at 50, superior drop rate at 75, the third choice at 100.",
        "Skipping costs 100 points, Turael cannot reset a Mortimer task, and you only get two block slots at 120 points each.",
        "He only assigns creatures that have superior variants, which is the point: it is the intended route to an imbued heart.",
        "Venators are exclusive to him and need no unlock, only The Blood Moon Rises.",
        "Task extensions carry over, but master-specific task unlocks do not. Gryphons, aquanites and basilisks are available without paying to unlock them.",
    ],
    verdict="Jagex put Duradel and Mortimer extremely close on XP per hour, with Duradel pulling ahead as you unlock more block slots and keeping the boss tasks Mortimer cannot assign. Use Mortimer when you want superior drops or the choice between two known tasks; stay on Duradel for raw XP and bossing.",
)


OSRSGUIDE = "https://www.osrsguide.com/"

# Reference sites for the rail
SITE_LINKS = [
    ("OSRS Guide", OSRSGUIDE + "skilling-guides/"),
    ("Calculators", "https://07.gg/calculators"),
    ("Time to Max", OSRSGUIDE + "time-to-max-osrs/"),
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
        title="Shooting Star tracker",
        url="https://07.gg/trackers/shooting-star",
        host="07.gg",
        height=620,
        note="Crashed stars land about every 90 minutes per world. Mining stardust "
             "is the most AFK training in the skill and buys the celestial ring.",
    ),
}


def starmap_script(depth=0):
    """Crash-site maps plus the tracker icon path for the client."""
    path = os.path.join(OUT, "assets", "media", "starmaps", "manifest.json")
    try:
        with open(path, encoding="utf-8") as f:
            maps = json.load(f)
    except (OSError, ValueError):
        return ""
    slim = {k: {"f": v["file"]} for k, v in maps.items()}
    root = "../" if depth else ""
    return ("<script>window.STARMAPS=" + json.dumps(slim, separators=(",", ":"))
            + ";window.STARMAPROOT=" + json.dumps(root + "assets/media/starmaps/")
            + ";window.SRCICON=" + json.dumps(root + "assets/media/site/07gg.png")
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
    href = f"{WIKI}{page.replace(' ', '_')}" if page else wiki_search(name)
    label = title_case(name) if cased else name
    return (f'<a class="{cls}" href="{href}" target="_blank" rel="noopener">'
            f'{e(label)}</a>')


def slayer_summary():
    """Block / never-unlock / skip lists at a glance."""
    by = {}
    for t in SLAYER_TASKS:
        by.setdefault(t["tag"], []).append(t)

    def chips(tag):
        return "".join(
            f'<a class="tchip {tag}" href="{wiki_search(t["name"])}" target="_blank" '
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
        '<p class="vnote">Blocks are permanent and cost 100 points at Duradel; skips cost '
        '30 points each time. w is the task weight, so blocking a heavy task saves more '
        'rolls than blocking a rare one.</p>'
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
        rows.append(
            f'<tr class="tk {t["tag"]}">'
            f'<td class="tv"><span class="verdict {t["tag"]}">{label[t["tag"]]}</span></td>'
            f'<td class="tn">{wiki_link(t["name"])}<span class="tmeta">{meta}</span>'
            f'<span class="tmeta xp">{e(t["xp"])}</span></td>'
            f'<td class="notes"><b>{e(t["rec"])}</b> {e(why)}</td></tr>')

    counts = {k: sum(1 for t in SLAYER_TASKS if t["tag"] == k) for k in order}
    filters = "".join(
        f'<button class="tf" type="button" data-f="{k}">{label[k]}'
        f'<span>{counts[k]}</span></button>' for k in order if counts[k])
    controls = (
        '<div class="tcontrols">'
        f'<button class="tf on" type="button" data-f="all">all<span>{len(SLAYER_TASKS)}</span></button>'
        f'{filters}'
        '<span class="tspace"></span>'
        '<span class="tsortlbl">sort</span>'
        '<button class="ts on" type="button" data-s="verdict">verdict</button>'
        '<button class="ts" type="button" data-s="weight">how often</button>'
        '<button class="ts" type="button" data-s="xp">xp/hr</button>'
        '<button class="ts" type="button" data-s="level">level</button>'
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
    ("Mushroom Forest", "West of the ancient shroom, straight north of the magic mushtree."),
    ("Tar Swamp", "By the swamp entrance, south from the mushtree."),
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
        'of fishing. Set the houses before you dive, so the 50 minutes runs while '
        'you are underwater.</p>'
        '<ol class="bhstops">'
        '<li>Surface and climb out. You land on the small island, which has a '
        '<b>bank</b>: restock nets, seeds and logs here rather than teleporting.</li>'
        '<li>Row back to the Museum Camp, then run south to the '
        '<b>Verdant Valley</b> mushtree. Two houses sit right by it.</li>'
        '<li>Mushtree to <b>Mushroom Meadow</b>, third house is north of it.</li>'
        '<li>Mushtree to <b>Sticky Swamp</b>, fourth house is by the Tar Swamp '
        'entrance. Bring an axe and rake the first time you go.</li>'
        '<li>Mushtree back to <b>Verdant Valley</b>, run north to the camp, row out '
        'and dive.</li>'
        "</ol>"
        '<p class="gap">Two things that pay for themselves: <b>20,000 numulites</b> '
        'for permanent drift net access, so surfacing never costs you the daily fee, '
        'and <b>flippers</b> for sprinting underwater.</p>'
        "</div></div>"
    )


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
                + (f'<span class="goal">of {nxt}</span>' if nxt else
                   '<span class="goal done">target met</span>'))
        bar = (f'<span class="prog wide"><span class="fill lit" '
               f'style="width:{pct}%;--lc:{level_color(cur)}" data-skill-bar="{e(name)}" '
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
                     "Pick one with the circle at the end of any row below.</p></div>")

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
        parts.append('<p class="savednote" id="savednote">Tap the circle on any row to '
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

    return page(name, name, "\n".join(parts), active=slug(name), depth=1,
                skill_name=name)


PAIRS = {"Fishing": "Hunter", "Hunter": "Fishing"}

PAIR_NOTE = {
    frozenset({"Fishing", "Hunter"}):
        "Drift Net Fishing trains both at once, which is exactly why the plan "
        "pairs the 70/70 requirement.",
}


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
                 f'<span class="target{done_cls}" data-skill-goal="{e(s["name"])}">{nxt}</span>'
                 if not done else
                 f'<span class="lvl lit"{lstyle} data-skill-level="{e(s["name"])}">{cur}</span>')
        bar = (f'<span class="prog"><span class="fill lit" '
               f'style="width:{pct}%;--lc:{level_color(cur)}" data-skill-bar="{e(s["name"])}" '
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
    note = PAIR_NOTE.get(frozenset({a["name"], b["name"]}), "")
    halves = []
    for s in (a, b):
        halves.append(
            f'    <a class="half" href="skills/{slug(s["name"])}.html">'
            f'{card_head(s)}</a>'
        )
    del note
    return '  <div class="card pair">\n' + "\n".join(halves) + "\n  </div>"


def build_stars_page():
    cfg = EMBEDS["Mining"]
    body = [
        '<div class="kick">Live Tracker</div>',
        '<div class="page-head"><span class="comethead">' + COMET_SVG
        + '</span><h1 class="page">Shooting Stars</h1></div>',
        f'<p class="lede">{e(cfg["note"])}</p>',
        embed_panel("Mining", full=True),
        '<h2 id="how">How the Tiers Work</h2>',
        '<ul>'
        '<li>Star tier decides the Mining level you need: tier 1 at level 10, '
        'rising every ten levels to tier 9 at 90. A tier 9 star can be mined all '
        'the way down, so it lasts longest.</li>'
        '<li>Each layer takes seven minutes to deplete with at least one person '
        'mining, so a fresh star is worth travelling for and a nearly dead one is not.</li>'
        '<li>Stardust buys the celestial ring (an invisible +4 Mining boost), '
        'along with soft clay packs and bags of gems, at Dusuri\'s Star Shop by the '
        'Mining Guild entrance in Falador.</li>'
        '<li>A telescope in your house narrows the next landing to a 24, 9 or 2 minute '
        'window depending on the wood you build it from.</li>'
        '</ul>',
    ]
    return page("Shooting Stars", "Shooting Stars", "\n".join(body), depth=0)


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
         icon="angler", effect="+2.5% XP from all Fishing",
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
         source="Mahogany Homes contracts",
         pieces=["Carpenter's helmet", "Carpenter's shirt", "Carpenter's trousers",
                 "Carpenter's boots"]),
    dict(name="Smiths' Uniform", skill="Smithing", wiki="Smiths%27_Uniform", bonus=0,
         icon="worn-equipment",
         effect="Anvil actions 5 ticks to 4, about a quarter faster",
         source="15,000 Foundry Reputation at Giants' Foundry",
         pieces=["Smiths tunic", "Smiths trousers", "Smiths gloves", "Smiths boots"]),
    dict(name="Guild Hunter Outfit", skill="Hunter", wiki="Guild_hunter_outfit", bonus=0,
         icon="hunterguild", effect="+2.5% catch rate",
         source="1/50 from Hunters' Rumour loot sacks",
         pieces=["Guild hunter headwear", "Guild hunter top", "Guild hunter legs",
                 "Guild hunter boots"]),
    dict(name="Raiments of the Eye", skill="Runecraft", wiki="Raiments_of_the_Eye",
         bonus=0, icon="eye", effect="Up to 60% bonus runes, no extra XP",
         source="Guardians of the Rift",
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
    """Drop whatever the piece repeats from the set name, so the pill reads
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
        bonus_attr = (f' data-skill="{e(sk)}" data-bonus="{o["bonus"]}"'
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
    return ('<p class="lede2">Tick each piece as you get it. Completing a set switches '
            "on that skill's rate toggle, so the XP numbers match what you actually "
            'wear.</p>'
            f'<div class="outfits">{"".join(rows)}</div>')


# Sustained rate for the method the plan actually picks, and whether those
# hours pay you, break even, or cost gold. Used to estimate what is left.
SKILL_RATE = {
    "Slayer": (55_000, "pays"), "Attack": (60_000, "pays"),
    "Strength": (60_000, "pays"), "Defence": (60_000, "pays"),
    "Hitpoints": (0, "free"), "Ranged": (250_000, "costs"),
    "Magic": (250_000, "costs"), "Prayer": (300_000, "costs"),
    "Runecraft": (60_000, "pays"), "Agility": (70_000, "pays"),
    "Thieving": (200_000, "pays"), "Hunter": (150_000, "pays"),
    "Mining": (65_000, "neutral"), "Fishing": (60_000, "neutral"),
    "Woodcutting": (100_000, "neutral"), "Sailing": (120_000, "neutral"),
    "Firemaking": (250_000, "pays"), "Herblore": (250_000, "costs"),
    "Crafting": (250_000, "costs"), "Construction": (250_000, "costs"),
    "Smithing": (300_000, "costs"), "Cooking": (350_000, "costs"),
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
         why="Whatever Slayer did not already carry. Ranged and Magic go fast on "
             "chins and barrage, Prayer burns the bones you banked, Hitpoints "
             "arrives on its own.",
         caveat="Counted as if you trained each one alone. Most of it lands "
                "during the 235 hours above, so treat this as the ceiling, not "
                "the bill.",
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
             "the bank drains slowest.",
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


def max_order_block(phase, index):
    chips = []
    total = 0
    for name in phase["skills"]:
        sk = next((x for x in SKILLS if x["name"] == name), None)
        if not sk:
            continue
        st = stat_of(name)
        hrs = hours_left(name)
        done = st and st["level"] >= 99
        if hrs:
            total += hrs
        money = SKILL_RATE.get(name, (0, ""))[1]
        chips.append(
            f'<a class="mo {money}{" met" if done else ""}" '
            f'href="skills/{slug(name)}.html">{icon(name)}'
            f'<span class="mn">{e(name)}</span>'
            + (f'<span class="ml">{st["level"]}</span>' if st else "")
            + (f'<span class="mh">{hrs:.0f}h</span>' if hrs else
               '<span class="mh done">99</span>')
            + "</a>")
    head = (f'<b>{e(phase["title"])}</b>'
            + (f'<span class="mtot">{total:.0f} hours</span>' if total else ""))
    caveat = (f'<p class="mcaveat">{annotate(phase["caveat"])}</p>'
              if phase.get("caveat") else "")
    return (f'  <li>{head}'
            f'<p class="mwhy">{annotate(phase["why"])}</p>{caveat}'
            f'<div class="mochips">{"".join(chips)}</div></li>')


def h2(anchor, title, ico=None):
    """Section heading, with the matching game icon where there is one."""
    mark = (f'<img class="h2ico" src="{ico}" alt="" width="20" height="20">'
            if ico else "")
    return f'<h2 id="{anchor}">{mark}{e(title)}</h2>'


# The least-attention option for each skill. `every` is how long you can leave
# it between clicks, which is the thing that actually makes something AFK.
AFK = [
    dict(skill="Hunter", method="Birdhouse runs", level="5+", every=50 * 60,
         xp="4-5k", note="Four houses, then nothing for 50 minutes. Nothing else "
                         "in the game asks so little of you."),
    dict(skill="Mining", method="Shooting Stars", level="10+", every=7 * 60,
         xp="20-40k", note="One click per layer, seven minutes apart. Stardust "
                           "buys the celestial ring on the side."),
    dict(skill="Magic", method="Splashing", level="1+", every=20 * 60,
         xp="10-30k", note="Attack once and walk away until the runes run out. "
                           "The lowest attention in the game, and the rate shows it."),
    dict(skill="Attack", method="Nightmare Zone, absorptions", level="Quest reqs",
         every=15 * 60, xp="40-80k",
         note="Absorption potions and a rock cake. Top up every ten to fifteen "
              "minutes. Works for Strength, Defence and Hitpoints too."),
    dict(skill="Strength", method="Gemstone Crab", level="1+", every=10 * 60,
         xp="30-60k", note="Shared health pool in Varlamore, so it never dies on "
                           "you and never stops being aggressive."),
    dict(skill="Woodcutting", method="Redwoods", level="90", every=5 * 60,
         xp="~65k", note="Chops until the inventory fills, and the Woodcutting "
                         "Guild bank is right there."),
    dict(skill="Firemaking", method="Bonfires", level="1+", every=4 * 60,
         xp="200-300k", note="Add the whole inventory at once and it burns "
                             "through unattended. Slower per log than a line of "
                             "fires, but you are not clicking."),
    dict(skill="Smithing", method="Cannonballs", level="35", every=3 * 60,
         xp="~20k", note="A full inventory of steel bars smelts itself. Profitable, "
                         "and the rate is as bad as it looks."),
    dict(skill="Fishing", method="Anglerfish", level="82", every=3 * 60,
         xp="~30k", note="Fishes until the inventory fills. Dark crabs and monkfish "
                         "behave the same way if the level is not there yet."),
    dict(skill="Sailing", method="Shipwreck salvaging with crew", level="15 (42 better)",
         every=3 * 60, xp="7-8k",
         note="Put a crewmate on your hook and it keeps salvaging while you sort. "
              "The wiki's own figure for the idle version."),
    dict(skill="Crafting", method="Cutting amethyst", level="83", every=2 * 60,
         xp="~30k", note="Cuts through the inventory on its own. The only Crafting "
                         "worth calling AFK."),
    dict(skill="Runecraft", method="Blood runes at Arceuus", level="77", every=90,
         xp="~40k", note="Run essence, craft, repeat. Low attention and it pays, "
                         "which nothing else in Runecraft manages."),
    dict(skill="Cooking", method="Range cooking", level="1+", every=60,
         xp="150-250k", note="One click per inventory at a bank range. Not truly "
                            "idle, but you get a minute back each time."),
    dict(skill="Prayer", method="Bonecrusher and ash sanctifier", level="Passive",
         every=None, xp="passive",
         note="Zero clicks: bones and ashes convert while you are killing things "
              "for something else. The only free XP on this page."),
]

NO_AFK = [
    ("Agility", "Every course is a click every few seconds. There is no idle option."),
    ("Construction", "Butler cycles are five seconds apart from start to finish."),
    ("Thieving", "Pickpocketing is one click per attempt, whatever the target."),
    ("Herblore", "Potions are made an inventory at a time, by hand."),
    ("Slayer", "Individual tasks can be low effort, but the skill itself is not."),
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
        + f'<img class="icon lg" src="assets/media/site/skills-icon.png" alt="">'
        + '<h1 class="page">The AFK Path</h1></div>',
        '<p class="lede">Sorted by how long you can leave it alone, which is the '
        'only measure that matters here. XP rates are the price you pay for that.</p>',
        '<div class="tablewrap"><div class="tablescroll">'
        '<table class="afktable"><thead><tr>'
        '<th class="pic"><span class="sr">Image</span></th><th>Skill</th>'
        '<th>Method</th><th>Needs</th><th>Click every</th><th>XP/hr</th>'
        '<th>Why</th></tr></thead>'
        f'<tbody>{afk_rows()}</tbody></table></div></div>',
        '<h2 id="none">Skills With No AFK Option</h2>',
        '<p class="lede2">Being honest about these is more useful than pretending. '
        'If you want to idle, spend the time on the table above and come back to '
        'these when you can pay attention.</p>',
        '<ul>' + "".join(f'<li><b>{e(n)}</b>. {e(why)}</li>' for n, why in NO_AFK)
        + "</ul>",
        '<h2 id="stack">Stacking Them</h2>',
        '<ul>'
        '<li>Birdhouses run on a 50 minute timer that ignores what else you are '
        'doing, so they stack with everything on this page.</li>'
        '<li>A bonecrusher and ash sanctifier turn any combat into passive Prayer, '
        'including the Nightmare Zone and crab hours.</li>'
        '<li>Drift net fishing trains Fishing and Hunter at once, and the birdhouse '
        'run fits inside its downtime.</li>'
        "</ul>",
    ]
    return page("The AFK Path", "AFK", "\n".join(body), depth=0)


# Three ways to spend the remaining XP. Each entry is (method, sustained rate).
# "afk" is the lowest-attention option that still trains the skill; where a
# skill has none, it holds the least demanding thing available and says so.
PATHS = {
    "Slayer":       dict(fast=("Duradel, barrage tasks", 60_000),
                         afk=("Cannon on long tasks", 30_000),
                         hybrid=("Duradel, cannon and barrage", 50_000)),
    "Attack":       dict(fast=("Slayer with best gear", 70_000),
                         afk=("Nightmare Zone", 45_000),
                         hybrid=("Slayer", 60_000)),
    "Strength":     dict(fast=("Slayer with best gear", 70_000),
                         afk=("Nightmare Zone", 45_000),
                         hybrid=("Slayer", 60_000)),
    "Defence":      dict(fast=("Slayer with best gear", 70_000),
                         afk=("Nightmare Zone", 45_000),
                         hybrid=("Slayer", 60_000)),
    "Hitpoints":    dict(fast=("Arrives with combat", 0),
                         afk=("Arrives with combat", 0),
                         hybrid=("Arrives with combat", 0)),
    "Ranged":       dict(fast=("Chinning maniacal monkeys", 250_000),
                         afk=("Gemstone Crab", 45_000),
                         hybrid=("Cannon on Slayer tasks", 80_000)),
    "Magic":        dict(fast=("Bursting maniacal monkeys", 250_000),
                         afk=("Splashing", 20_000),
                         hybrid=("Barrage on Slayer tasks", 110_000)),
    "Prayer":       dict(fast=("Superior bones, gilded altar", 500_000),
                         afk=("Bonecrusher while you fight", 25_000),
                         hybrid=("Chaos altar, dragon bones", 300_000)),
    "Runecraft":    dict(fast=("Lava runes with runners", 110_000),
                         afk=("Blood runes at Arceuus", 40_000),
                         hybrid=("Guardians of the Rift", 60_000)),
    "Agility":      dict(fast=("Hallowed Sepulchre, top floors", 90_000),
                         afk=("Rooftops, nothing is idle here", 55_000),
                         hybrid=("Hallowed Sepulchre", 70_000)),
    "Thieving":     dict(fast=("Blackjacking", 250_000),
                         afk=("Stealing artefacts", 70_000),
                         hybrid=("Pyramid Plunder", 200_000)),
    "Mining":       dict(fast=("Volcanic Mine, 3-tick iron", 90_000),
                         afk=("Shooting Stars", 30_000),
                         hybrid=("Motherlode Mine", 60_000)),
    "Fishing":      dict(fast=("2-tick harpooning", 100_000),
                         afk=("Anglerfish", 30_000),
                         hybrid=("Drift Net Fishing", 55_000)),
    "Woodcutting":  dict(fast=("2-tick teaks", 130_000),
                         afk=("Redwoods", 65_000),
                         hybrid=("Forestry teaks", 95_000)),
    "Firemaking":   dict(fast=("Burning logs at a bank", 350_000),
                         afk=("Bonfires", 250_000),
                         hybrid=("Wintertodt", 250_000)),
    "Cooking":      dict(fast=("1-tick karambwans", 700_000),
                         afk=("Range cooking", 200_000),
                         hybrid=("Jugs of wine", 400_000)),
    "Crafting":     dict(fast=("Black d'hide bodies", 300_000),
                         afk=("Cutting amethyst", 30_000),
                         hybrid=("Battlestaves", 250_000)),
    "Smithing":     dict(fast=("Blast Furnace gold bars", 350_000),
                         afk=("Cannonballs", 20_000),
                         hybrid=("Giants' Foundry", 250_000)),
    "Herblore":     dict(fast=("Unfinished potions", 300_000),
                         afk=("Potions, nothing is idle here", 250_000),
                         hybrid=("Super combats", 250_000)),
    "Construction": dict(fast=("Mahogany tables", 350_000),
                         afk=("Mahogany Homes, nothing is idle here", 120_000),
                         hybrid=("Mahogany Homes", 120_000)),
    "Hunter":       dict(fast=("Letvek and stymphikes", 145_000),
                         afk=("Birdhouse runs", 5_000),
                         hybrid=("Hunter Rumours", 90_000)),
    "Sailing":      dict(fast=("Barracuda Trials", 200_000),
                         afk=("Shipwreck salvaging", 8_000),
                         hybrid=("Courier tasks", 120_000)),
}

PATH_META = [
    ("fast", "Fastest", "Every hour is the best rate available, tick manipulation "
                        "included. The shortest route to the cape and the one that "
                        "asks the most of you."),
    ("hybrid", "Hybrid", "The fast method where the gap is worth it, the calm one "
                         "where it barely is. What most people actually do."),
    ("afk", "AFK", "The lowest attention that still trains the skill. Five skills "
                   "have no idle option, so they hold the least demanding thing "
                   "available."),
]


def path_hours(key):
    """Hours to 99 per skill on one path, from live XP."""
    out, total = [], 0
    for name, opts in PATHS.items():
        st = stat_of(name)
        if not st:
            continue
        left = max(0, xp_for_level(99) - (st["xp"] or 0))
        method, rate = opts[key]
        hrs = (left / rate) if (rate and left) else 0
        total += hrs
        out.append(dict(skill=name, level=st["level"], method=method,
                        rate=rate, hours=hrs, left=left))
    out.sort(key=lambda x: -x["hours"])
    return out, total


def paths_page():
    cards, totals = [], {}
    for key, label, blurb in PATH_META:
        rows, total = path_hours(key)
        totals[key] = total
        cells = []
        for r in rows:
            if not r["left"]:
                continue
            rate = f'{r["rate"] // 1000}k' if r["rate"] else "free"
            hrs = f'{r["hours"]:.0f}h' if r["hours"] else "free"
            cells.append(
                f'<tr><td class="tn"><a href="skills/{slug(r["skill"])}.html">'
                f'{icon(r["skill"])}{e(r["skill"])}</a></td>'
                f'<td>{e(r["method"])}</td>'
                f'<td class="rate">{rate}</td>'
                f'<td class="rate afkgap">{hrs}</td></tr>')
        body = "".join(cells)
        cards.append(
            f'<section class="pathcard" id="path-{key}">'
            f'<div class="phead"><h2 id="{key}">{e(label)}</h2>'
            f'<span class="ptot">{total:,.0f} hours</span></div>'
            f'<p class="lede2">{e(blurb)}</p>'
            '<div class="tablewrap"><div class="tablescroll">'
            '<table class="pathtable"><thead><tr><th>Skill</th><th>Method</th>'
            '<th>XP/hr</th><th>Hours</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div></div></section>')

    fast, hybrid, afk = totals["fast"], totals["hybrid"], totals["afk"]
    summary = (
        '<div class="stats">'
        f'<div class="stat"><div class="l">Fastest</div>'
        f'<div class="v">{fast:,.0f}<small>h</small></div></div>'
        f'<div class="stat"><div class="l">Hybrid</div>'
        f'<div class="v">{hybrid:,.0f}<small>h</small></div>'
        f'</div>'
        f'<div class="stat"><div class="l">AFK</div>'
        f'<div class="v">{afk:,.0f}<small>h</small></div></div>'
        f'<div class="stat"><div class="l">AFK costs you</div>'
        f'<div class="v">+{afk - fast:,.0f}<small>h</small></div></div>'
        "</div>")

    body = [
        '<div class="kick">Three routes, same cape</div>',
        '<div class="page-head">'
        '<img class="icon lg" src="assets/media/max-cape.png" alt="">'
        '<h1 class="page">Which Path</h1></div>',
        f'<p class="lede">You have {sum(r["left"] for r in path_hours("fast")[0]):,} '
        'XP left. What that costs in hours depends entirely on how much attention '
        'you are willing to pay.</p>',
        summary,
        '<p class="lede2">Hitpoints is missing from every table because it arrives '
        'with combat. Fletching and Farming are already done.</p>',
    ] + cards
    return page("Which Path", "Paths", "\n".join(body), depth=0)


def build_index():
    parts = []
    art = focus_panel()
    parts.append('<section class="hero">')
    parts.append(art)
    parts.append("</section>")


    parts.append(h2("progression", "Main Progression", "assets/media/site/combat-achievements.png"))
    parts.append('<ol class="phases">')
    for i, ph in enumerate(PLAN_PHASES, 1):
        body = phase_meter(ph.get("track", ""))
        if ph.get("reqs"):
            chips = "".join(req_chip(n, lv) for n, lv in ph["reqs"])
            if ph.get("combat"):
                chips += combat_chip(ph["combat"])
            body += f'<div class="reqgrid">{chips}</div>'
        if ph.get("subs"):
            body += "<ul>" + "".join(f"<li>{annotate(x)}</li>" for x in ph["subs"]) + "</ul>"
        parts.append(f'  <li id="phase-{i}"><b>{annotate(ph["title"])}</b>{body}</li>')
    parts.append("</ol>")

    parts.append(h2("quests", "Quest Cape Progress", "assets/media/quest-point-cape.png"))
    parts.append(quest_panel())

    parts.append(h2("diaries", "Diary Progress", "assets/icons/Diaries.png"))
    parts.append(diary_panel())

    parts.append(h2("approach", "Slayer", "assets/icons/Slayer.png"))
    parts.append('<div class="panel"><div class="k">Standing Rules</div><ul>' +
                 "".join(f"<li>{annotate(c)}</li>" for c in COMBAT_APPROACH) +
                 "</ul></div>")

    parts.append(h2("max-order", "Post-Diary-Cape Maxing Order",
                    "assets/media/max-cape.png"))
    parts.append('<p class="lede2">Ordered so the hours that pay come before the '
                 'hours that cost, and so nothing waits on something later. '
                 'Estimates use your live XP at the rates on each skill page.</p>')
    parts.append('<ol class="phases maxorder">')
    for i, phase in enumerate(MAX_ORDER, 1):
        parts.append(max_order_block(phase, i))
    parts.append("</ol>")
    parts.append('<div class="panel"><div class="k">Gaps Worth Noting</div>'
                 '<p>Fletching and Farming are already 99, so they sit outside the order above. '
                 'Thieving and Hunter are not listed in either block, so decide where they land: '
                 'Thieving fits with the faster skills, Hunter with the slow gathering ones.</p></div>')

    parts.append(h2("outfits", "Gear", "assets/media/site/gear-icon.png"))
    parts.append(outfit_section())

    parts.append(h2("skills", "All Skills", "assets/media/site/skills-icon.png"))
    for group in GROUP_ORDER:
        members = [s for s in SKILLS if s["group"] == group]
        if not members:
            continue
        parts.append(f'<div class="group-title">{e(group)}</div>')
        parts.append('<div class="grid">')
        skipped = set()
        for s in members:
            if s["name"] in skipped:
                continue
            partner = PAIRS.get(s["name"])
            twin = next((m for m in members if m["name"] == partner), None)
            if twin:
                skipped.add(twin["name"])
                parts.append(pair_card(s, twin))
                continue
            parts.append(skill_card(s))
        parts.append("</div>")

    return page("OSRS max time wasting plan", "Overview", "\n".join(parts))


def main():
    os.makedirs(os.path.join(OUT, "skills"), exist_ok=True)

    ordered = [s for g in GROUP_ORDER for s in SKILLS if s["group"] == g]
    for i, s in enumerate(ordered):
        prev_s = ordered[i - 1] if i else None
        next_s = ordered[i + 1] if i + 1 < len(ordered) else None
        path = os.path.join(OUT, "skills", slug(s["name"]) + ".html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(build_skill_page(s, prev_s, next_s))

    with open(os.path.join(OUT, "stars.html"), "w", encoding="utf-8") as f:
        f.write(build_stars_page())

    with open(os.path.join(OUT, "afk.html"), "w", encoding="utf-8") as f:
        f.write(build_afk_page())

    with open(os.path.join(OUT, "paths.html"), "w", encoding="utf-8") as f:
        f.write(paths_page())

    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_index())

    print(f"wrote index.html + {len(ordered)} pages")


if __name__ == "__main__":
    main()
