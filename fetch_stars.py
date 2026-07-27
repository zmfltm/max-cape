#!/usr/bin/env python3
"""Refresh data/stars.json for static hosting.

The parser and cache live in serve.py because the local API uses the same data.
This command forces a network refresh and lets scheduled builds update the
snapshot without starting the server.
"""

from serve import shooting_stars


def main():
    stars = shooting_stars(max_age=0, require_snapshot=True)
    if not stars:
        print("no active stars parsed; keeping the previous snapshot")
        return 1
    print(f"wrote data/stars.json with {len(stars)} active stars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
