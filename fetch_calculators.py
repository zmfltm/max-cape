#!/usr/bin/env python3
"""Builds data/calculators.json: every trainable action, per skill.

The wiki drives its own skill calculators from Module:Skill calc/<Skill>, a Lua
table of every action with its level, XP and materials. That is the same shape
a calculator needs, so this reads those modules directly rather than scraping
anyone's rendered output.

Material names are matched to Grand Exchange ids where one exists, so the page
can price a plan live. Anything untradeable simply has no id.

    python3 fetch_calculators.py
"""

import json
import os
import re
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "calculators.json")
API = "https://oldschool.runescape.wiki/api.php"
MAPPING = "https://prices.runescape.wiki/api/v1/osrs/mapping"
UA = "mudkip-osrs-plan/1.0 (personal planning page)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def modules():
    q = urllib.parse.urlencode({
        "action": "query", "list": "allpages", "apprefix": "Skill calc/",
        "apnamespace": "828", "aplimit": "500", "format": "json",
        "formatversion": "2",
    })
    pages = [p["title"] for p in json.loads(get(f"{API}?{q}"))["query"]["allpages"]]
    return [p for p in pages
            if p.count("/") == 1 and not p.endswith("/doc")
            and not p.endswith("/Helpers")]


def wikitext(page):
    q = urllib.parse.urlencode({
        "action": "parse", "page": page, "prop": "wikitext",
        "format": "json", "formatversion": "2",
    })
    return json.loads(get(f"{API}?{q}"))["parse"]["wikitext"]


# --------------------------------------------------------------- lua reading

TOKEN = re.compile(r"""
    (?P<space>\s+|--\[\[.*?\]\]|--[^\n]*)
  | (?P<string>'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")
  | (?P<number>-?\d+(?:\.\d+)?)
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<punct>[{}=,;\[\]()+*/%-])
""", re.X | re.S)


def tokens(text):
    pos, out = 0, []
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            raise ValueError(f"cannot read Lua at {text[pos:pos + 40]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind != "space":
            out.append((kind, m.group()))
    return out


def unquote(raw):
    body = raw[1:-1]
    return re.sub(r"\\(.)", r"\1", body)


class Reader:
    """Just enough Lua for these data modules: tables, keys, strings, numbers."""

    def __init__(self, toks):
        self.toks, self.i = toks, 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self, want=None):
        kind, text = self.peek()
        if want and text != want:
            raise ValueError(f"expected {want!r}, found {text!r}")
        self.i += 1
        return text

    def value(self):
        kind, text = self.peek()
        if text == "{":
            return self.table()
        if kind == "string":
            self.i += 1
            return unquote(text)
        if text in ("true", "false", "nil"):
            self.i += 1
            return None if text == "nil" else text == "true"
        return self.expr()

    # some quantities are written as arithmetic, e.g. (2/16 / 45)
    def expr(self):
        value = self.term()
        while self.peek()[1] in ("+", "-"):
            op = self.take()
            other = self.term()
            value = value + other if op == "+" else value - other
        return value

    def term(self):
        value = self.factor()
        while self.peek()[1] in ("*", "/", "%"):
            op = self.take()
            other = self.factor()
            if op == "*":
                value *= other
            elif op == "/":
                value = value / other if other else 0
            else:
                value = value % other if other else 0
        return value

    def factor(self):
        kind, text = self.peek()
        if text == "-":
            self.take()
            return -self.factor()
        if text == "(":
            self.take()
            inner = self.expr()
            self.take(")")
            return inner
        if kind == "number":
            self.i += 1
            return float(text) if "." in text else int(text)
        raise ValueError(f"unexpected value {text!r}")

    def table(self):
        self.take("{")
        items, fields = [], {}
        while True:
            kind, text = self.peek()
            if text == "}":
                self.take()
                return fields if fields and not items else items
            if kind == "name" and self.toks[self.i + 1][1] == "=":
                key = self.take()
                self.take("=")
                fields[key] = self.value()
            elif text == "[":
                self.take("[")
                key = self.value()
                self.take("]")
                self.take("=")
                fields[str(key)] = self.value()
            else:
                items.append(self.value())
            if self.peek()[1] in (",", ";"):
                self.take()


def parse_module(text):
    body = text[text.index("return"):] if "return" in text else text
    reader = Reader(tokens(body.split("return", 1)[1]))
    got = reader.table()
    return got if isinstance(got, list) else []


# ------------------------------------------------------------------- output

def price_ids():
    return {item["name"]: item["id"] for item in json.loads(get(MAPPING))}


def clean(entry, ids):
    """One action, with its materials priced where the GE knows them."""
    name = entry.get("title") or entry.get("name")
    if not name or not entry.get("level"):
        return None

    materials = []
    for mat in entry.get("materials") or []:
        if not isinstance(mat, dict):
            continue
        label = mat.get("title") or mat.get("name")
        if not label:
            continue
        materials.append({
            "name": label,
            "qty": mat.get("quantity") or 1,
            "id": ids.get(label) or ids.get(mat.get("name", "")),
        })

    return {
        "name": name,
        "level": int(entry["level"]),
        "xp": float(entry.get("xp") or 0),
        "type": entry.get("type") or "Other",
        "members": entry.get("members") != "No",
        "materials": materials,
        "made": ids.get(entry.get("name", "")) or ids.get(name),
    }


def main():
    ids = price_ids()
    print(f"{len(ids)} tradeable items")

    out, empty = {}, []
    for page in modules():
        skill = page.split("/", 1)[1]
        try:
            rows = parse_module(wikitext(page))
        except Exception as err:                                  # noqa: BLE001
            print(f"{skill:<14} could not read: {err}")
            empty.append(skill)
            continue

        actions = [a for a in (clean(r, ids) for r in rows if isinstance(r, dict))
                   if a and a["xp"] > 0]
        actions.sort(key=lambda a: (a["level"], a["name"]))
        if not actions:
            empty.append(skill)
            continue

        out[skill] = actions
        priced = sum(1 for a in actions if all(m["id"] for m in a["materials"]))
        kinds = len({a["type"] for a in actions})
        print(f"{skill:<14} {len(actions):>4} actions  {kinds:>2} groups  "
              f"{priced:>4} fully priceable")
        time.sleep(0.3)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"), sort_keys=True)

    total = sum(len(v) for v in out.values())
    size = os.path.getsize(OUT) // 1024
    print(f"\n{len(out)} skills, {total} actions, {size} KB")
    if empty:
        print("nothing usable from: " + ", ".join(empty))


if __name__ == "__main__":
    main()
