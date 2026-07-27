#!/usr/bin/env python3
"""Serves the site and proxies the OSRS hiscores so the page can refresh live.

    python3 serve.py            # http://localhost:8412
    python3 serve.py 9000       # different port

Plain `python3 -m http.server` also works; you just lose the live refresh
button and see the levels as of the last `fetch_stats.py` run. The proxy exists
because the hiscores send no CORS headers, so a browser cannot call them
directly from a file:// or static page.
"""

import http.server
import json
import os
import re
import time
import urllib.request
import sys
import threading
import urllib.error

from hiscores import SKILL_ORDER, fetch
from storage import atomic_json_dump

HERE = os.path.dirname(os.path.abspath(__file__))
STATS = os.path.join(HERE, "data", "stats.json")
PICKS = os.path.join(HERE, "data", "picks.json")
FOCUS = os.path.join(HERE, "data", "focus.json")
MAX_BODY = 8 * 1024
VALID_SKILLS = set(SKILL_ORDER) | {"Diaries"}
_write_lock = threading.Lock()


def remembered_name():
    try:
        with open(STATS, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("name") if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


STAR_URL = "https://07.gg/trackers/shooting-star"
STAR_UA = "mudkip-osrs-plan/1.0 (personal planning page)"
_star_cache = {"at": 0.0, "data": None}


def clean_star_text(text, limit=60):
    """Keep crowd-sourced fields plain and bounded before storing them."""
    text = re.sub(r"[<>&\"'\\\\]", "", text or "")
    return re.sub(r"\\s+", " ", text).strip()[:limit]


def clean_caller(text):
    if re.search(r"[^A-Za-z0-9 _-]", text or ""):
        return "anonymous"
    caller = clean_star_text(text, 12)
    return caller if re.fullmatch(r"[A-Za-z0-9 _-]{1,12}", caller) else "anonymous"


def shooting_stars(max_age=45):
    """Active stars from 07.gg, parsed out of their server-rendered payload.

    They publish no JSON API, so this reads the `initialCalls` array the page
    ships with. Cached, so a page open does not hammer their site. If they
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
        called, caller, world, tier, _key, loc, end = m.groups()
        if world in seen:
            continue
        seen.add(world)
        stars.append({
            "world": int(world),
            "tier": int(tier),
            "location": clean_star_text(loc),
            "caller": clean_caller(caller),
            "calledAt": int(called),
            "endsAt": int(end),
        })

    stars.sort(key=lambda x: (-x["tier"], x["endsAt"]))
    _star_cache.update(at=now, data=stars)

    # keep a snapshot on disk: the published copy on GitHub Pages reads this,
    # since Pages has no server to proxy with
    try:
        atomic_json_dump(os.path.join(HERE, "data", "stars.json"),
                         {"stars": stars, "at": int(now * 1000), "source": STAR_URL})
    except OSError:
        pass

    return stars


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
        if route not in ("/api/pick", "/api/focus"):
            return self.json({"error": "unknown endpoint"}, 404)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self.json({"error": "bad content length"}, 400)
        if not 0 < length <= MAX_BODY:
            return self.json({"error": "request body must be 1-8192 bytes"}, 413)
        try:
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or not isinstance(body.get("skill"), str):
                raise ValueError
            skill = body["skill"].strip()
            if skill not in VALID_SKILLS:
                raise ValueError
            method = None
            if route == "/api/pick":
                if not isinstance(body.get("method"), str):
                    raise ValueError
                method = body["method"].strip()
                if not method or len(method) > 120:
                    raise ValueError
        except (ValueError, json.JSONDecodeError):
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
        from urllib.parse import parse_qs, urlparse

        q = parse_qs(urlparse(self.path).query)
        player = (q.get("player", [None])[0] or remembered_name() or "").strip()
        if not player:
            return self.json({"error": "no player linked yet"}, 400)

        try:
            data = fetch(player)
        except urllib.error.HTTPError as exc:
            msg = "not on the hiscores" if exc.code == 404 else f"hiscores error {exc.code}"
            return self.json({"error": msg}, 502)
        except Exception as exc:                                  # noqa: BLE001
            return self.json({"error": str(exc)}, 502)

        # keep the snapshot fresh so a later rebuild uses these numbers
        try:
            import datetime
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
