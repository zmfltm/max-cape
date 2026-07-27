import http.client
import http.server
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import build
import quests
import serve
from hiscores import xp_for_level
from storage import atomic_json_dump


class FormulaTests(unittest.TestCase):
    def test_known_xp_values(self):
        self.assertEqual(xp_for_level(2), 83)
        self.assertEqual(xp_for_level(50), 101_333)
        self.assertEqual(xp_for_level(99), 13_034_431)


class RequirementTests(unittest.TestCase):
    def setUp(self):
        self.old = build.STATS, build.QUESTS, build.DIARIES
        build.STATS = {
            "combat": 89,
            "overall": {},
            "skills": {"Magic": {"level": 70}, "Ranged": {"level": 56}},
        }
        build.QUESTS = {
            "states": {"Monkey Madness II": 0, "Desert Treasure I": 2}
        }
        build.DIARIES = None

    def tearDown(self):
        build.STATS, build.QUESTS, build.DIARIES = self.old

    def test_quest_abbreviation_is_not_parsed_as_a_level(self):
        self.assertEqual(build.parse_reqs("MM2, 70 Magic", "Ranged"), [("Magic", 70)])
        self.assertEqual(build.unmet("MM2, 70 Magic", "Ranged"), "Monkey Madness II")

    def test_named_completed_quest_is_open(self):
        self.assertIsNone(build.unmet("Desert Treasure I", "Magic"))

    def test_missing_skill_snapshot_is_not_treated_as_unlocked(self):
        self.assertEqual(build.unmet("60 Sailing", "Mining"), "60 Sailing")


class QuestTests(unittest.TestCase):
    def test_collect_fetches_the_guide_once(self):
        raw = {
            "username": "test",
            "quests": {"Cook's Assistant": 0},
            "achievement_diaries": {},
        }
        with mock.patch.object(quests, "guide_route", return_value=["Cook's Assistant"]) as route:
            result = quests.collect("test", raw)
        self.assertEqual(route.call_count, 1)
        self.assertEqual(result["next"], "Cook's Assistant")

    def test_quest_panel_escapes_upstream_names_and_urls(self):
        old = build.QUESTS
        build.QUESTS = {
            "done": 0,
            "total": 1,
            "route": [{
                "kind": "quest", "name": '<img src=x onerror="alert(1)">',
                "state": 0, "wiki": 'x" onclick="alert(1)',
            }],
            "route_next": {
                "name": '<img src=x onerror="alert(1)">',
                "wiki": 'x" onclick="alert(1)',
            },
            "name": "test",
            "synced": "",
        }
        try:
            panel = build.quest_panel()
        finally:
            build.QUESTS = old
        self.assertNotIn("<img src=x", panel)
        self.assertNotIn(' onclick="', panel)
        self.assertIn("%22%20onclick%3D%22alert%281%29", panel)


class ServerTests(unittest.TestCase):
    def test_crowd_sourced_caller_is_strictly_sanitized(self):
        self.assertEqual(serve.clean_caller("valid name"), "valid name")
        self.assertEqual(serve.clean_caller("name,world:622,tier:8"), "anonymous")
        self.assertEqual(serve.clean_caller("<script>"), "anonymous")

    def test_post_validation_and_atomic_focus_write(self):
        with tempfile.TemporaryDirectory() as directory:
            focus = str(Path(directory) / "focus.json")
            with mock.patch.object(serve, "FOCUS", focus), \
                    mock.patch.object(serve.Handler, "log_message", lambda *args: None), \
                    mock.patch("builtins.print"):
                server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
                    conn.request("POST", "/api/focus", body=b'{"skill":"not real"}',
                                 headers={"Content-Type": "application/json"})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 400)
                    response.read()
                    conn.close()

                    conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
                    conn.request("POST", "/api/focus", body=b'{"skill":"Fishing"}',
                                 headers={"Content-Type": "application/json"})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    response.read()
                    conn.close()
                    self.assertEqual(json.loads(Path(focus).read_text()), {"skill": "Fishing"})
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join()


class StorageTests(unittest.TestCase):
    def test_atomic_json_dump_replaces_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text('{"old": true}', encoding="utf-8")
            atomic_json_dump(path, {"new": True}, sort_keys=True)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"new": True})
            self.assertEqual(list(Path(directory).glob(".tmp-*")), [])


if __name__ == "__main__":
    unittest.main()
