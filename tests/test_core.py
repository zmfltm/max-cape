import http.client
import http.server
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import build
import fetch_calculators
import guidance
import quests
import serve
from hiscores import XP_TABLE, combat_level, xp_for_level
from storage import atomic_binary_dump, atomic_json_dump


class FormulaTests(unittest.TestCase):
    def test_known_xp_values(self):
        self.assertEqual(xp_for_level(2), 83)
        self.assertEqual(xp_for_level(50), 101_333)
        self.assertEqual(xp_for_level(99), 13_034_431)


class FetcherTests(unittest.TestCase):
    def test_calculator_labels_remove_wiki_line_break_markup(self):
        self.assertEqual(fetch_calculators.clean_label("Mist rune<br>(Air altar)"),
                         "Mist rune (Air altar)")
        self.assertEqual(fetch_calculators.clean_label("Baby<br /> impling"),
                         "Baby impling")


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


class QuestCapeRequirementTests(unittest.TestCase):
    def test_regular_cape_table_is_not_confused_with_master_cape(self):
        source = """==Minimum skill levels==
{{DiarySkillStats
|Attack = 50
|Hitpoints = 50
|Mining = 70
|Strength = 60
|Agility = 70
|Smithing = 72
|Defence = 65
|Herblore = 70
|Fishing = 60
|Ranged = 62
|Thieving = 72
|Cooking = 72
|Prayer = 50
|Crafting = 70
|Firemaking = 75
|Magic = 75
|Fletching = 70
|Woodcutting = 74
|Runecraft = 60
|Slayer = 74
|Farming = 70
|Construction = 70
|Hunter = 70
|Sailing = 62
|Combat = 85
|MiningNotes=(72)|FishingNotes=(62)}}}

Two skills can be boosted.
{{DiarySkillStats
|Attack = 99
|Hitpoints = 99
|Mining = 99
|Strength = 99
|Agility = 99
|Smithing = 99
|Defence = 99
|Herblore = 99
|Fishing = 99
|Ranged = 99
|Thieving = 99
|Cooking = 99
|Prayer = 99
|Crafting = 99
|Firemaking = 99
|Magic = 99
|Fletching = 99
|Woodcutting = 99
|Runecraft = 99
|Slayer = 95
|Farming = 99
|Construction = 99
|Hunter = 99
|Sailing = 99
|Combat = 100}}
"""
        result = quests._parse_quest_cape_requirements(source)
        self.assertEqual(result["combat"], 85)
        self.assertEqual(result["skills"]["Slayer"], 74)
        self.assertEqual(result["skills"]["Smithing"], 72)
        self.assertEqual(result["boostable"], {"Mining": 72, "Fishing": 62})

    def test_plan_uses_current_quest_cape_targets(self):
        self.assertEqual(build.QUEST_CAPE_COMBAT, 85)
        self.assertEqual(build.QUEST_CAPE_REQUIREMENTS["Slayer"], 74)
        self.assertEqual(build.QUEST_CAPE_REQUIREMENTS["Ranged"], 62)
        self.assertEqual(build.QUEST_CAPE_REQUIREMENTS["Runecraft"], 60)
        self.assertEqual(build.QUEST_CAPE_REQUIREMENTS["Sailing"], 62)
        self.assertEqual(build.QUEST_CAPE_REQUIREMENTS,
                         build.QUESTS["requirements"]["skills"])

    def test_boostable_fishing_step_is_not_a_training_goal(self):
        fishing = next(s for s in build.SKILLS if s["name"] == "Fishing")
        self.assertEqual(build.milestones(fishing), [60, 99])
        self.assertNotIn(("Fishing", 62), build.PLAN_PHASES[0]["reqs"])


class RouteTests(unittest.TestCase):
    def test_staged_routes_are_contiguous_and_ordered(self):
        for skill, choices in build.PATHS.items():
            for name, route in choices.items():
                levels = [leg[0] for leg in route]
                self.assertEqual(levels[0], 1, (skill, name))
                self.assertEqual(levels, sorted(set(levels)), (skill, name))
                self.assertTrue(all(rate >= 0 for _, _, rate in route), (skill, name))

    def test_barbarian_fishing_carries_strength_and_agility(self):
        _, carried = build.climb(
            build.PATHS["Fishing"]["fast"], xp_for_level(61), xp_for_level(71)
        )
        self.assertGreater(carried.get("Strength", 0), 0)
        self.assertGreater(carried.get("Agility", 0), 0)

    def test_slayer_starts_on_nieve_before_duradel(self):
        route = build.PATHS["Slayer"]["hybrid"]
        self.assertIn("Nieve", route[0][1])
        self.assertEqual(route[0][2], 30_000)
        self.assertEqual(route[1][0], 85)
        self.assertIn("Duradel", route[1][1])

    def test_slayer_routes_reach_100_combat_before_duradel(self):
        base = {name: (build.stat_of(name) or {}).get("xp", 0)
                for name in build.SKILL_NAMES}
        slayer = build.stat_of("Slayer")
        for route in build.PATHS["Slayer"].values():
            switch = route[1][0]
            _, carried = build.climb(route, slayer["xp"], XP_TABLE[switch])
            projected = dict(base)
            projected["Slayer"] = XP_TABLE[switch]
            for name, amount in carried.items():
                projected[name] += amount
            levels = {name: build.level_at(xp) for name, xp in projected.items()}
            self.assertGreaterEqual(combat_level(levels), 100, route)

    def test_smiths_uniform_models_both_speedups(self):
        foundry, anvil = build.BONUSES["Smithing"][:2]
        self.assertEqual(foundry["pct"], 20)
        self.assertIn("Giants' Foundry", foundry["applies"])
        self.assertEqual(anvil["pct"], 25)
        self.assertIn("Cannonballs", anvil["applies"])


class QuestTests(unittest.TestCase):
    def test_guide_route_keeps_training_rows_in_order(self):
        parsed = {
            "parse": {"text": (
                '<table><tr data-rowid="First Quest"><td>First Quest</td></tr>'
                '<tr><th>Train Ranged from level 43 to level 60</th></tr>'
                '<tr data-rowid="Second Quest"><td>Second Quest</td></tr></table>'
            )}
        }
        with mock.patch.object(quests, "_get", return_value=json.dumps(parsed).encode()):
            route = quests.guide_route()
        self.assertEqual(route, ["First Quest", "Train Ranged from level 43 to level 60",
                                 "Second Quest"])

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

    def test_new_quest_is_counted_while_wikisync_lags(self):
        raw = {
            "username": "test",
            "quests": {"Cook's Assistant": 2},
            "achievement_diaries": {},
        }
        with mock.patch.object(quests, "guide_route", return_value=["Cook's Assistant"]):
            result = quests.collect("test", raw)
        self.assertEqual(result["done"], 1)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["unreported"], ["Fallen From Grace"])
        self.assertIsNone(result["states"]["Fallen From Grace"])
        self.assertEqual(result["quest_requirements"]["Fallen From Grace"]["skills"], {
            "Sailing": 62, "Crafting": 60, "Runecraft": 47, "Mining": 53,
        })
        self.assertEqual(result["quest_requirements"]["Fallen From Grace"]["quests"],
                         ["Pandemonium"])

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
        self.assertIn("1</b><span>quests to go", panel)


class GuidanceTests(unittest.TestCase):
    def test_quest_batch_points_to_the_next_training_overlap(self):
        stats = {
            "combat": 89,
            "skills": {"Ranged": {"level": 56}, "Slayer": {"level": 50}},
        }
        route = [
            {"kind": "quest", "name": f"Quest {n}", "state": 0}
            for n in range(1, 7)
        ] + [
            {"kind": "task", "name": "Varrock Museum", "state": None},
            {"kind": "task", "name": "Train Ranged from level 43 to level 60",
             "state": None},
            {"kind": "quest", "name": "Later Quest", "state": 0},
        ]
        advice = guidance.recommend(stats, {"route": route})
        self.assertEqual(advice["headline"], "Quest now: Quest 1")
        self.assertIn("Then do the guide action: Varrock Museum.", advice["actions"])
        self.assertEqual(advice["checkpoint"], "Train Ranged to 60 through Slayer")

    def test_immediate_training_gate_wins_over_the_next_quest(self):
        stats = {
            "combat": 89,
            "skills": {"Ranged": {"level": 56}, "Slayer": {"level": 50}},
        }
        route = [
            {"kind": "quest", "name": "Done", "state": 2},
            {"kind": "task", "name": "Train Ranged from level 43 to level 60",
             "state": None},
            {"kind": "quest", "name": "Blocked", "state": 0},
        ]
        advice = guidance.recommend(stats, {"route": route})
        self.assertEqual(advice["headline"], "Train Ranged to 60 through Slayer")
        self.assertEqual(advice["next_quest"], "Blocked")


class ServerTests(unittest.TestCase):
    def test_crowd_sourced_star_text_is_sanitized(self):
        self.assertEqual(serve.clean_star_text("  two\n words  "), "two words")
        self.assertEqual(serve.clean_star_text("<script> & text"), "script text")

    def test_method_choices_must_exist_for_the_skill(self):
        self.assertTrue(serve.valid_method("Fishing", "Drift Net Fishing"))
        self.assertFalse(serve.valid_method("Fishing", "not a real method"))
        self.assertFalse(serve.valid_method("not a skill", "Drift Net Fishing"))

    def test_sync_failure_preserves_previous_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            stats_path = Path(directory) / "stats.json"
            quests_path = Path(directory) / "quests.json"
            diaries_path = Path(directory) / "diaries.json"
            stats_path.write_text('{"name":"test","old":true}', encoding="utf-8")
            quests_path.write_text('{"old":true}', encoding="utf-8")
            diaries_path.write_text('{"old":true}', encoding="utf-8")
            with mock.patch.object(serve, "STATS", str(stats_path)), \
                    mock.patch.object(serve, "QUESTS", str(quests_path)), \
                    mock.patch.object(serve, "DIARIES", str(diaries_path)), \
                    mock.patch.object(serve, "fetch", return_value={"name": "test"}), \
                    mock.patch.object(serve, "sync_state", side_effect=RuntimeError("offline")):
                with self.assertRaisesRegex(RuntimeError, "offline"):
                    serve.sync_character()
            self.assertEqual(json.loads(stats_path.read_text()), {"name": "test", "old": True})
            self.assertEqual(json.loads(quests_path.read_text()), {"old": True})
            self.assertEqual(json.loads(diaries_path.read_text()), {"old": True})

    def test_advice_endpoint_syncs_before_recommending(self):
        stats = {"name": "test", "combat": 89, "overall": {"level": 1600}}
        quest_data = {"done": 10, "total": 20, "route": []}
        diaries = {"done": 0}
        advice = {"headline": "Quest now"}
        with mock.patch.object(serve, "sync_character",
                               return_value=(stats, quest_data, diaries)) as sync, \
                mock.patch.object(serve, "recommend", return_value=advice) as choose, \
                mock.patch.object(serve.Handler, "log_message", lambda *args: None):
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
                conn.request("POST", "/api/advice", body=b"{}",
                             headers={"Content-Type": "application/json"})
                response = conn.getresponse()
                payload = json.loads(response.read())
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["advice"], advice)
        sync.assert_called_once_with()
        choose.assert_called_once_with(stats, quest_data, diaries)

    def test_post_validation_and_atomic_focus_write(self):
        with tempfile.TemporaryDirectory() as directory:
            focus = str(Path(directory) / "focus.json")
            picks = str(Path(directory) / "picks.json")
            with mock.patch.object(serve, "FOCUS", focus), \
                    mock.patch.object(serve, "PICKS", picks), \
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
                                 headers={"Content-Type": "text/plain"})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 415)
                    response.read()
                    conn.close()

                    conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
                    conn.request("POST", "/api/pick",
                                 body=b'{"skill":"Fishing","method":"not real"}',
                                 headers={"Content-Type": "application/json"})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 400)
                    response.read()
                    conn.close()
                    self.assertFalse(Path(picks).exists())

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
            binary = Path(directory) / "image.bin"
            atomic_binary_dump(binary, b"\x00\xffpayload")
            self.assertEqual(binary.read_bytes(), b"\x00\xffpayload")
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o777, 0o644)
                self.assertEqual(binary.stat().st_mode & 0o777, 0o644)
            self.assertEqual(list(Path(directory).glob(".tmp-*")), [])


if __name__ == "__main__":
    unittest.main()
