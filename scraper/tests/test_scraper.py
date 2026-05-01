"""Replay the captured HAR data through the scraper to validate parsing."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from skahl_scraper import (  # noqa: E402
    HistoricalSource,
    HttpClient,
    PlayerSeasonRecord,
    SportNinjaSource,
    scrape_historical,
)

PROJECT_ROOT = HERE.parent.parent
CURRENT_HAR = PROJECT_ROOT / "current.har"
HISTORICAL_HAR = PROJECT_ROOT / "historical.har"


def load_har_responses(har_path):
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)
    out = {}
    for entry in har["log"]["entries"]:
        status = entry["response"].get("status", 0)
        if not (200 <= status < 300):
            continue
        text = entry["response"]["content"].get("text")
        if text is None:
            continue
        out[entry["request"]["url"]] = text.encode("utf-8")
    return out


def make_fixture_transport(responses):
    def normalize(url):
        u = urlparse(url)
        q = [(k, v) for k, v in parse_qsl(u.query) if k != "v"]
        q_str = urlencode(q)
        return f"{u.scheme}://{u.netloc}{u.path}" + (f"?{q_str}" if q_str else "")

    indexed = {normalize(k): v for k, v in responses.items()}

    def transport(req):
        url = normalize(req.full_url)
        if url not in indexed:
            raise AssertionError(f"No fixture for {url!r}")
        return indexed[url]

    return transport


class SportNinjaParserTests(unittest.TestCase):
    def setUp(self):
        with open(CURRENT_HAR, encoding="utf-8") as f:
            har = json.load(f)
        self.raw = None
        for e in har["log"]["entries"]:
            url = e["request"]["url"]
            if "/stats?" in url and "/leaderboard" not in url:
                payload = json.loads(e["response"]["content"]["text"])
                self.raw = payload["data"][0]
                break
        self.assertIsNotNone(self.raw)

    def test_round_trip_to_unified(self):
        rec = SportNinjaSource.to_unified(self.raw, season_name="Winter 2025-26")
        self.assertIsInstance(rec, PlayerSeasonRecord)
        self.assertEqual(rec.source, "snokingahl_sportninja")
        self.assertEqual(rec.league, "SKAHL")
        self.assertEqual(rec.player_id, "LJdbhmchVVDf0kzo")
        self.assertEqual(rec.name, "Phin Mallon")
        self.assertEqual(rec.team, "Ale Storm")
        self.assertEqual(rec.team_id, "1HJ5cSiEVNSjXUWC")
        self.assertEqual(rec.division, "C-Wednesday")
        self.assertEqual(rec.games_played, 24)
        self.assertEqual(rec.goals, 28)
        self.assertEqual(rec.assists, 37)
        self.assertEqual(rec.points, 65)
        self.assertEqual(rec.pim, 4)
        self.assertAlmostEqual(rec.points_per_game, 2.71, places=2)
        self.assertAlmostEqual(rec.goals_per_game, round(28 / 24, 3), places=3)
        self.assertAlmostEqual(rec.assists_per_game, round(37 / 24, 3), places=3)

    def test_handles_zero_games_played(self):
        rec = dict(self.raw)
        rec["stats"] = [
            {"id": "2", "abbr": "GP", "value": "0"},
            {"id": "1", "abbr": "G", "value": "0"},
            {"id": "3", "abbr": "A", "value": "0"},
            {"id": "4", "abbr": "P", "value": "0"},
            {"id": "5", "abbr": "PiM", "value": "0"},
            {"id": "6", "abbr": "PTS/G", "value": "0"},
        ]
        out = SportNinjaSource.to_unified(rec, "Winter 2025-26")
        self.assertEqual(out.games_played, 0)
        self.assertEqual(out.goals_per_game, 0.0)
        self.assertEqual(out.assists_per_game, 0.0)
        self.assertEqual(out.points_per_game, 0.0)


class SportNinjaPaginationTests(unittest.TestCase):
    def test_iter_uses_pagination_meta(self):
        responses = load_har_responses(CURRENT_HAR)
        page1_url = None
        for url in responses:
            if "/stats?" in url and "page=1" in url and "sortBy=4" in url:
                page1_url = url
                break
        self.assertIsNotNone(page1_url)
        body = responses[page1_url]

        def transport(req):
            return body

        http = HttpClient(transport=transport, sleep_seconds=0)
        src = SportNinjaSource(http=http)
        records = list(src.iter_stats_records("66UWZ4oxEb0HOsP5", max_pages=3))
        self.assertEqual(len(records), 150)


class SportNinjaPageOneEndToEnd(unittest.TestCase):
    def test_first_page_via_iter_and_unify(self):
        responses = load_har_responses(CURRENT_HAR)
        transport = make_fixture_transport(responses)
        http = HttpClient(transport=transport, sleep_seconds=0)
        src = SportNinjaSource(http=http)

        records = [
            SportNinjaSource.to_unified(raw, "Winter 2025-26")
            for raw in src.iter_stats_records("66UWZ4oxEb0HOsP5", max_pages=1)
        ]
        self.assertEqual(len(records), 50)
        ids = {r.player_id for r in records}
        self.assertEqual(len(ids), 50)
        for r in records:
            self.assertTrue(r.name)
            self.assertTrue(r.team)
            self.assertEqual(r.source, "snokingahl_sportninja")
            self.assertEqual(r.points, r.goals + r.assists)


class HistoricalParserTests(unittest.TestCase):
    def setUp(self):
        with open(HISTORICAL_HAR, encoding="utf-8") as f:
            har = json.load(f)
        for e in har["log"]["entries"]:
            if "/api/player/statsBySeason" in e["request"]["url"]:
                payload = json.loads(e["response"]["content"]["text"])
                self.first_div_block = payload[0]
                break
        self.assertTrue(self.first_div_block)

    def test_round_trip_to_unified(self):
        div = self.first_div_block["division"]
        skater = self.first_div_block["skaters"][0]
        rec = HistoricalSource.to_unified(div, skater, season_name="2024 SKAHL Summer Playoffs")
        self.assertEqual(rec.source, "snokinghockeyleague")
        self.assertEqual(rec.player_id, "4093")
        self.assertEqual(rec.name, "Hiron Redman")
        self.assertEqual(rec.team, "Sasquatch")
        self.assertEqual(rec.team_id, "2742")
        self.assertEqual(rec.division, "Division-B1")
        self.assertEqual(rec.games_played, 2)
        self.assertEqual(rec.goals, 2)
        self.assertEqual(rec.assists, 4)
        self.assertEqual(rec.points, 6)
        self.assertEqual(rec.pim, 2)
        self.assertEqual(rec.goals_per_game, 1.0)
        self.assertEqual(rec.assists_per_game, 2.0)
        self.assertEqual(rec.points_per_game, 3.0)

    def test_uses_PTPG_not_PPG_for_points_per_game(self):
        div = self.first_div_block["division"]
        skater = dict(self.first_div_block["skaters"][0])
        skater["stats"] = dict(skater["stats"])
        skater["stats"]["PPG"] = 99
        skater["stats"]["PTPG"] = 1.5
        rec = HistoricalSource.to_unified(div, skater, "x")
        self.assertEqual(rec.points_per_game, 1.5)


class HistoricalEndToEndTest(unittest.TestCase):
    def test_scrape_historical_yields_all_skaters(self):
        responses = load_har_responses(HISTORICAL_HAR)
        transport = make_fixture_transport(responses)
        http = HttpClient(transport=transport, sleep_seconds=0)
        src = HistoricalSource(http=http)

        records = list(scrape_historical(1099, season_name="2024 SKAHL Summer Playoffs", source=src))
        self.assertEqual(len(records), 65)
        for r in records:
            self.assertEqual(r.source, "snokinghockeyleague")
            self.assertTrue(r.name)
            self.assertTrue(r.division)
            self.assertEqual(r.points, r.goals + r.assists)


class UnifiedSchemaTests(unittest.TestCase):
    def test_both_sources_produce_same_field_set(self):
        with open(CURRENT_HAR) as f:
            cur_har = json.load(f)
        sn_raw = None
        for e in cur_har["log"]["entries"]:
            if "/stats?" in e["request"]["url"] and "/leaderboard" not in e["request"]["url"]:
                sn_raw = json.loads(e["response"]["content"]["text"])["data"][0]
                break
        sn = SportNinjaSource.to_unified(sn_raw, "Winter 2025-26").as_dict()

        with open(HISTORICAL_HAR) as f:
            hist_har = json.load(f)
        for e in hist_har["log"]["entries"]:
            if "/api/player/statsBySeason" in e["request"]["url"]:
                payload = json.loads(e["response"]["content"]["text"])
                div_block = payload[0]
                break
        hist = HistoricalSource.to_unified(
            div_block["division"], div_block["skaters"][0], "2024 SKAHL Summer Playoffs"
        ).as_dict()

        self.assertEqual(set(sn.keys()), set(hist.keys()))
        for k in sn:
            self.assertEqual(
                type(sn[k]).__name__, type(hist[k]).__name__,
                f"type mismatch for field {k!r}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
