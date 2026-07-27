# OSRS max time wasting plan

Static site for a Slayer-first route to the Max Cape. It includes an overview,
a page per skill, route comparisons, an AFK reference, and a shooting-star
tracker.

## Viewing it

```bash
python3 serve.py
```

Then open <http://localhost:8412>. `serve.py` also exposes `/api/stats`, which
proxies the OSRS hiscores so the refresh button in the sidebar works (the
hiscores send no CORS headers, so the page cannot call them directly).

`python3 -m http.server 8412` works too; you just lose the live API features.
The generated site itself has no Python dependencies. To regenerate shooting-star
map images, install Pillow with `python3 -m pip install -r requirements.txt`.

## Live stats

```bash
python3 fetch_stats.py "gxexe"   # snapshot the hiscores into data/stats.json
python3 build.py                 # bake current levels into the pages
```

After the first run the username is remembered, so `python3 fetch_stats.py`
alone refreshes it. Every skill card and skill page then shows your current
level, progress toward the next target in the plan, XP to go and rank, and the
sidebar shows total level and combat. Without `data/stats.json` the site simply
shows plan targets instead.

## Editing it

Most plan content lives in `build.py` as plain data. Slayer task verdicts live
in `slayer.py`, media mappings in `media.py`, and fetched snapshots in `data/`.
Edit the appropriate source, then regenerate:

```bash
python3 build.py
```

Do not hand-edit the generated HTML; it gets overwritten.

## Quest progress

```bash
python3 fetch_quests.py          # uses the linked account
python3 build.py
```

Quest completion comes from WikiSync (`sync.runescape.wiki`), which the RuneLite
WikiSync plugin uploads. The hiscores do not carry quest state, so the plugin
has to have run on the account at least once. Order comes from the wiki's
optimal quest guide, parsed at fetch time.

The overview then shows how many quests are done, which one is next in the
guide, and a scrollable list of everything still outstanding.

## Colour scale

Levels are coloured on a hue ramp: ember at low levels, amber through the
middle, green at 99 (matching the "done" green exactly). The stops live in
`_HUE_STOPS` in `build.py`. The same colour drives progress bars, so a skill
reads at a glance.

## Choosing a method

Methods you cannot use yet are locked: the requirement column is parsed
(including cross-skill, combat, named quest, and supported diary requirements)
against your snapshots, and those rows are dimmed with a padlock. The highest-rate method you *can* use is
tagged "best at your level" and named in the line above the table.

Every method table has a circle at the end of each row. Clicking it makes that
method your pick: the panel at the top of the page updates, the choice is
POSTed to `serve.py`, which writes `data/picks.json`, and the next
`python3 build.py` bakes it into the generated pages. Without the server it
still saves to localStorage for that browser.

`data/picks.json` overrides the defaults in `build.py`, so it survives rebuilds
and you can edit it by hand.

## Pictures

`media.py` maps method rows and prose names to OSRS Wiki pages. `fetch_media.py`
downloads each page's image into `assets/media/` and writes `manifest.json`;
`build.py` reads that manifest and adds mapped method thumbnails plus inline
pictures for selected skill, NPC, location, and unlock mentions.

After adding entries to `media.py`:

```bash
python3 fetch_media.py && python3 build.py
```

Titles the wiki has no image for are printed at the end of the fetch and simply
render without a picture.

## Other fetched data

```bash
python3 fetch_potions.py      # Herblore recipe/item IDs
python3 fetch_diary_reqs.py   # diary skill requirements
python3 fetch_star_maps.py    # local crash-site maps (needs Pillow)
python3 fetch_stars.py        # current 07.gg calls for static hosting
python3 build.py
```

`fetch_media.py` and the map fetcher make network requests and only need to run
when their registries or upstream data change. The other snapshots can be
refreshed regularly. `.github/workflows/refresh.yml` refreshes live snapshots,
rebuilds, runs the checks, and commits changes every six hours.

## Checks

```bash
ruff check . --exclude skills --exclude assets
python3 -m unittest discover -s tests -v
```

The tests cover formulas, requirement gating, API validation, atomic snapshots,
generator drift, duplicate IDs, and local links/anchors.

## Layout

- `index.html` — plan overview, generated
- `skills/*.html` — one page per skill, generated
- `stars.html`, `afk.html`, `paths.html` — reference pages, generated
- `build.py` — primary plan data and site generator
- `media.py`, `slayer.py` — media registry and Slayer task data
- `fetch_*.py` — snapshot/media refresh commands
- `data/*.json` — fetched and user-selected state
- `assets/style.css` — theme
- `assets/fonts/` — Geist Sans and Geist Mono (OFL, licence included)
- `assets/icons/` — skill icons from the OSRS Wiki

Skill icons come from the OSRS Wiki. Old School RuneScape is a trademark of
Jagex Ltd; this is a personal, non-commercial planning page.

## Credits

Skill icons, method images, crash-site maps and the guide data come from the
[OSRS Wiki](https://oldschool.runescape.wiki/), used under CC BY-NC-SA 3.0.
Shooting star calls come from [07.gg](https://07.gg/). Old School RuneScape is
a trademark of Jagex Ltd; this is a personal, non-commercial planning page.
