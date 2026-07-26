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
import urllib.error

from hiscores import fetch

HERE = os.path.dirname(os.path.abspath(__file__))
STATS = os.path.join(HERE, "data", "stats.json")
PICKS = os.path.join(HERE, "data", "picks.json")
FOCUS = os.path.join(HERE, "data", "focus.json")


def remembered_name():
    try:
        with open(STATS, encoding="utf-8") as f:
            return json.load(f).get("name")
    except (OSError, ValueError):
        return None


STAR_URL = "https://07.gg/trackers/shooting-star"
STAR_UA = "mudkip-osrs-plan/1.0 (personal planning page)"
_star_cache = {"at": 0.0, "data": None}


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
            "location": loc.replace("\\\\", ""),
            "caller": caller,
            "calledAt": int(called),
            "endsAt": int(end),
        })

    stars.sort(key=lambda x: (-x["tier"], x["endsAt"]))
    _star_cache.update(at=now, data=stars)
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
                return self.json({"stars": shooting_stars(),
                                  "source": STAR_URL, "at": int(time.time() * 1000)})
            except Exception as exc:                              # noqa: BLE001
                return self.json({"error": str(exc)}, 502)
        return super().do_GET()

    def do_POST(self):                                            # noqa: N802
        route = self.path.split("?")[0]
        if route not in ("/api/pick", "/api/focus"):
            return self.json({"error": "unknown endpoint"}, 404)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            skill = str(body["skill"])[:40]
            method = str(body["method"])[:120] if route == "/api/pick" else None
        except (ValueError, KeyError, TypeError):
            return self.json({"error": "bad request"}, 400)

        if route == "/api/focus":
            try:
                os.makedirs(os.path.dirname(FOCUS), exist_ok=True)
                with open(FOCUS, "w", encoding="utf-8") as f:
                    json.dump({"skill": skill}, f, indent=1)
            except OSError as exc:
                return self.json({"error": str(exc)}, 500)
            print(f"focus: {skill}")
            return self.json({"ok": True, "skill": skill})

        try:
            with open(PICKS, encoding="utf-8") as f:
                picks = json.load(f)
            if not isinstance(picks, dict):
                picks = {}
        except (OSError, ValueError):
            picks = {}

        picks[skill] = method
        try:
            os.makedirs(os.path.dirname(PICKS), exist_ok=True)
            with open(PICKS, "w", encoding="utf-8") as f:
                json.dump(picks, f, indent=1, sort_keys=True)
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
            os.makedirs(os.path.dirname(STATS), exist_ok=True)
            with open(STATS, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1, sort_keys=True)
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
