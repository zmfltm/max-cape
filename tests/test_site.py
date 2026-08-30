import collections
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import build


ROOT = Path(__file__).resolve().parents[1]


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.refs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        for key in ("href", "src"):
            if attrs.get(key):
                self.refs.append(attrs[key])


class GeneratedSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = list(ROOT.glob("*.html")) + list((ROOT / "skills").glob("*.html"))
        cls.parsed = {}
        for page in cls.pages:
            parser = PageParser()
            parser.feed(page.read_text(encoding="utf-8"))
            cls.parsed[page] = parser

    def test_expected_page_count(self):
        self.assertEqual(len(self.pages), 31)

    def test_no_duplicate_ids(self):
        for page, parser in self.parsed.items():
            duplicates = [key for key, count in collections.Counter(parser.ids).items()
                          if count > 1]
            self.assertEqual(duplicates, [], page)

    def test_local_references_and_fragments_exist(self):
        ids = {page.resolve(): set(parser.ids) for page, parser in self.parsed.items()}
        for page, parser in self.parsed.items():
            for ref in parser.refs:
                split = urlsplit(ref)
                if split.scheme or split.netloc or ref.startswith(("data:", "mailto:")):
                    continue
                target = (page.parent / unquote(split.path or page.name)).resolve()
                self.assertTrue(target.exists(), f"{page}: missing {ref}")
                if split.fragment and target.suffix == ".html":
                    self.assertIn(unquote(split.fragment), ids.get(target, set()),
                                  f"{page}: missing anchor {ref}")

    def test_url_attributes_escape_ampersands(self):
        attr = re.compile(r'\b(?:href|src)="([^"]*)"')
        raw_amp = re.compile(r'&(?!#\d+;|#x[\da-fA-F]+;|[A-Za-z][A-Za-z0-9]+;)')
        for page in self.pages:
            for value in attr.findall(page.read_text(encoding="utf-8")):
                self.assertIsNone(raw_amp.search(value), f"{page}: unescaped &: {value}")

    def test_character_coach_has_local_and_pages_actions(self):
        source = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertEqual(source.count('id="refresh-character-pages"'), 1)
        self.assertEqual(source.count('id="sync-character"'), 1)
        self.assertEqual(source.count('id="ask-character"'), 1)
        self.assertIn(
            'href="https://github.com/zmfltm/max-cape/actions/workflows/refresh.yml"',
            source,
        )
        self.assertIn("request('/api/sync')", source)
        self.assertIn("request('/api/advice')", source)
        self.assertIn("hostname.endsWith('.github.io')", source)
        self.assertIn("pagesRefresh.hidden = false", source)
        self.assertIn("sync.hidden = true", source)
        self.assertIn("ask.hidden = true", source)

    def test_generator_matches_tracked_html(self):
        ordered = [s for group in build.GROUP_ORDER
                   for s in build.SKILLS if s["group"] == group]
        expected = {}
        for i, skill in enumerate(ordered):
            previous = ordered[i - 1] if i else None
            following = ordered[i + 1] if i + 1 < len(ordered) else None
            expected[ROOT / "skills" / f"{build.slug(skill['name'])}.html"] = (
                build.build_skill_page(skill, previous, following)
            )
        expected.update({
            ROOT / "index.html": build.build_index(),
            ROOT / "stars.html": build.build_stars_page(),
            ROOT / "afk.html": build.build_afk_page(),
            ROOT / "paths.html": build.paths_page(),
            ROOT / "calculators.html": build.calculators_page(),
            ROOT / "gear.html": build.gear_page(),
        })
        for path, content in expected.items():
            self.assertEqual(path.read_text(encoding="utf-8"), content,
                             f"{path} is stale; run python3 build.py")


if __name__ == "__main__":
    unittest.main()
