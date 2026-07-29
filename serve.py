#!/usr/bin/env python3
"""Serves the site with local character sync and recommendation APIs.

    python3 serve.py            # http://localhost:8412
    python3 serve.py 9000       # different port

Plain `python3 -m http.server` also works, but it cannot refresh Hiscores and
WikiSync snapshots or write regenerated pages.
"""

import datetime
import http.server
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from guidance import recommend
from hiscores import SKILL_ORDER, fetch
from quests import collect, collect_diaries, quest_cape_requirements, sync_state
from storage import atomic_json_dump

HERE = os.path.dirname(os.path.abspath(__file__))
STATS = os.path.join(HERE, "data", "stats.json")
QUESTS = os.path.join(HERE, "data", "quests.json")
DIARIES = os.path.join(HERE, "data", "diaries.json")
PICKS = os.path.join(HERE, "data", "picks.json")
FOCUS = os.path.join(HERE, "data", "focus.json")
MAX_BODY = 8 * 1024
VALID_SKILLS = set(SKILL_ORDER) | {"Diaries"}
_write_lock = threading.Lock()
_sync_lock = threading.Lock()


def remembered_name():
    try:
        with open(STATS, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("name") if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def sync_character():
    """Refresh all character snapshots, then regenerate the static pages.

    Fetch everything before writing anything so a failed upstream leaves the
    previous valid snapshot intact.
    """
    player = (remembered_name() or "").strip()
    if not player:
        raise ValueError("no player linked yet")
    if not re.fullmatch(r"[A-Za-z0-9 _-]{1,12}", player):
        raise ValueError("invalid player name")

    with _sync_lock:
        stats = fetch(player)
        raw = sync_state(player)
        quests = collect(player, raw)
        quests["requirements"] = quest_cape_requirements()
        diaries = collect_diaries(raw, player)
        stamp = datetime.datetime.now().astimezone().isoformat(timespec="minutes")
        stats["fetched"] = stamp
        quests["fetched"] = stamp
        diaries["fetched"] = stamp

        with _write_lock:
            atomic_json_dump(STATS, stats, sort_keys=True)
            atomic_json_dump(QUESTS, quests)
            atomic_json_dump(DIARIES, diaries)

        build = subprocess.run(
            [sys.executable, os.path.join(HERE, "build.py")],
            cwd=HERE, capture_output=True, text=True, timeout=120, check=False,
        )
        if build.returncode:
            detail = (build.stderr or build.stdout or "unknown build error").strip()
            raise RuntimeError(f"character synced, but site rebuild failed: {detail[:200]}")

    return stats, quests, diaries


STAR_URL = "https://07.gg/trackers/shooting-star"
STAR_UA = "mudkip-osrs-plan/1.0 (personal planning page)"
_star_cache = {"at": 0.0, "data": None}
_star_lock = threading.Lock()


def clean_star_text(text, limit=60):
    """Keep crowd-sourced fields plain and bounded before storing them."""
    text = re.sub(r"[<>&\"'\\\\]", "", text or "")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def shooting_stars(max_age=45, require_snapshot=False):
    """Serialize refreshes so simultaneous tabs do not duplicate the scrape."""
    with _star_lock:
        return _shooting_stars(max_age, require_snapshot)


def _shooting_stars(max_age=45, require_snapshot=False):
    """Active stars from 07.gg, parsed out of their server-rendered payload.

    They publish no JSON API, so this reads the `initialCalls` array the page
    ships with. The result is cached so opening a page does not hammer their
    site. If they
    change the page shape this returns an empty list rather than breaking.
    """
    now = time.time()
    if _star_cache["data"] is not None and now - _star_cache["at"] < max_age:
        return _star_cache["data"]

    req = urllib.request.Request(STAR_URL, headers={"User-Agent": STAR_UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        page = r.read().decode("utf-8", "replace")

    stars, seen = [], set()
    for m in re.finditer(
            r'calledAt\\?":(\d+),\\?"caller\\?":\\?"(.*?)\\?",\\?"world\\?":(\d+),'
            r'\\?"tier\\?":(\d+),\\?"locationKey\\?":\\?"(.*?)\\?",'
            r'\\?"rawLocation\\?":\\?"(.*?)\\?",\\?"estimatedEnd\\?":(\d+)', page):
        called, _caller, world, tier, _key, loc, end = m.groups()
        if world in seen:
            continue
        seen.add(world)
        stars.append({
            "world": int(world),
            "tier": int(tier),
            "location": clean_star_text(loc),
            "calledAt": int(called),
            "endsAt": int(end),
        })

    stars.sort(key=lambda x: (-x["tier"], x["endsAt"]))
    refreshed = time.time()
    _star_cache.update(at=refreshed, data=stars)

    # keep a snapshot on disk: the published copy on GitHub Pages reads this,
    # since Pages has no server to proxy with
    if stars:
        try:
            atomic_json_dump(os.path.join(HERE, "data", "stars.json"),
                             {"stars": stars, "at": int(refreshed * 1000),
                              "source": STAR_URL})
        except OSError:
            if require_snapshot:
                raise

    return stars


def valid_method(skill, method):
    """Only persist choices the generator can actually render."""
    from build import SKILLS

    return any(row["name"] == skill and any(m[0] == method for m in row["methods"])
               for row in SKILLS)


class Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"          # keep-alive: one connection, not one per icon

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def do_GET(self):                                             # noqa: N802
        route = self.path.split("?")[0]
        if route == "/api/stats":
            return self.hiscores()
        if route == "/api/stars":
            try:
                stars = shooting_stars()
                return self.json({"stars": stars, "source": STAR_URL,
                                  "at": int(_star_cache["at"] * 1000)})
            except Exception as exc:                              # noqa: BLE001
                return self.json({"error": str(exc)}, 502)
        return super().do_GET()

    def do_POST(self):                                            # noqa: N802
        route = self.path.split("?")[0]
        if route not in ("/api/pick", "/api/focus", "/api/sync", "/api/advice"):
            return self.json({"error": "unknown endpoint"}, 404)
        content_type = self.headers.get_content_type()
        if content_type != "application/json":
            return self.json({"error": "Content-Type must be application/json"}, 415)
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlparse(origin).hostname not in {
                "127.0.0.1", "localhost", "::1"}:
            return self.json({"error": "cross-origin request refused"}, 403)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self.json({"error": "bad content length"}, 400)
        if not 0 < length <= MAX_BODY:
            return self.json({"error": "request body must be between 1 and 8,192 bytes"}, 413)
        try:
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            return self.json({"error": "bad request"}, 400)

        if route in ("/api/sync", "/api/advice"):
            try:
                stats, quests, diaries = sync_character()
            except ValueError as exc:
                return self.json({"error": str(exc)}, 400)
            except urllib.error.HTTPError as exc:
                return self.json({"error": f"upstream refresh failed ({exc.code})"}, 502)
            except Exception as exc:                              # noqa: BLE001
                return self.json({"error": str(exc)}, 502)

            synced = {
                "name": stats.get("name"),
                "total": (stats.get("overall") or {}).get("level"),
                "combat": stats.get("combat"),
                "quests_done": quests.get("done"),
                "quests_total": quests.get("total"),
            }
            if route == "/api/advice":
                return self.json({"ok": True, "synced": synced,
                                  "advice": recommend(stats, quests, diaries)})
            return self.json({"ok": True, "synced": synced})

        try:
            if not isinstance(body.get("skill"), str):
                raise ValueError
            skill = body["skill"].strip()
            if skill not in VALID_SKILLS:
                raise ValueError
            method = None
            if route == "/api/pick":
                if not isinstance(body.get("method"), str):
                    raise ValueError
                method = body["method"].strip()
                if not valid_method(skill, method):
                    raise ValueError
        except ValueError:
            return self.json({"error": "bad request"}, 400)

        if route == "/api/focus":
            try:
                with _write_lock:
                    atomic_json_dump(FOCUS, {"skill": skill})
            except OSError as exc:
                return self.json({"error": str(exc)}, 500)
            print(f"focus: {skill}")
            return self.json({"ok": True, "skill": skill})

        try:
            with _write_lock:
                try:
                    with open(PICKS, encoding="utf-8") as f:
                        picks = json.load(f)
                    if not isinstance(picks, dict):
                        picks = {}
                except (OSError, ValueError):
                    picks = {}
                picks[skill] = method
                atomic_json_dump(PICKS, picks, sort_keys=True)
        except OSError as exc:
            return self.json({"error": str(exc)}, 500)

        print(f"pick: {skill} -> {method}")
        return self.json({"ok": True, "skill": skill, "method": method})

    def hiscores(self):
        player = (remembered_name() or "").strip()
        if not player:
            return self.json({"error": "no player linked yet"}, 400)
        if not re.fullmatch(r"[A-Za-z0-9 _-]{1,12}", player):
            return self.json({"error": "invalid player name"}, 400)

        try:
            data = fetch(player)
        except urllib.error.HTTPError as exc:
            msg = "not on the Hiscores" if exc.code == 404 else f"Hiscores error {exc.code}"
            return self.json({"error": msg}, 502)
        except Exception as exc:                                  # noqa: BLE001
            return self.json({"error": str(exc)}, 502)

        # keep the snapshot fresh so a later rebuild uses these numbers
        try:
            data["fetched"] = datetime.datetime.now().astimezone().isoformat(timespec="minutes")
            with _write_lock:
                atomic_json_dump(STATS, data, sort_keys=True)
        except OSError:
            pass

        return self.json(data)

    def json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            super().log_message(fmt, *args)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8412
    # threaded, because HTTP/1.1 keep-alive holds a connection open per tab;
    # a single-threaded server would block every other request behind it
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler) as httpd:
        who = remembered_name()
        print(f"serving on http://localhost:{port}"
              + (f" — live stats for {who}" if who else " — no player linked yet"))
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()
