"""SKAHL Hockey League stats scraper.

Pulls player-season records from two sources and emits a single unified schema:

  - Current seasons:    snokingahl.com (SportNinja platform)
  - Historical seasons: snokinghockeyleague.com (custom CMS)

Public API
----------
    SportNinjaSource     — client + parser for the current SportNinja API
    HistoricalSource     — client + parser for the legacy snokinghockeyleague.com API
    PlayerSeasonRecord   — dataclass representing one row in the unified output
    scrape_current()     — convenience: pull every player from one SportNinja season
    scrape_historical()  — convenience: pull every player from one historical season
    main()               — CLI entry point (see __main__ block at bottom)

Design notes
------------
- HTTP I/O is encapsulated in HttpClient and accepted as a constructor arg on
  each Source, so tests can inject a fake transport that returns HAR fixtures.
- Both Source classes expose two layers:
    * `iter_*_records(season_id)`  → yields raw JSON records straight from the API
    * `to_unified(record, season)` → converts one raw record into PlayerSeasonRecord
  This lets callers stream records without buffering, while keeping the field
  mapping in one obvious place.
- Numeric values arrive as strings on the SportNinja side and as numbers on the
  historical side; we coerce defensively in both directions.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import logging
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator, Optional

log = logging.getLogger("skahl_scraper")

# ---------------------------------------------------------------------------
# Unified output schema
# ---------------------------------------------------------------------------

@dataclass
class PlayerSeasonRecord:
    """One row of the unified output schema.

    Stable fields match the schema agreed in the project plan; `division` and
    `team_id` are extras that come for free from both APIs and are useful for
    dashboard filtering.
    """
    player_id: str
    name: str
    team: str
    season: str
    league: str
    games_played: int
    goals: int
    assists: int
    points: int
    pim: int
    goals_per_game: float
    assists_per_game: float
    points_per_game: float
    source: str
    division: Optional[str] = None
    team_id: Optional[str] = None

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# HTTP transport
# ---------------------------------------------------------------------------

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; SKAHL-Dashboard-Scraper/1.0; +https://github.com/)"
)


class HttpClient:
    """Tiny urllib wrapper with rate limiting and JSON decoding.

    Replaceable for tests via the `transport` callback (a callable that takes
    a urllib.request.Request and returns the decoded body bytes).
    """

    def __init__(
        self,
        headers: Optional[dict] = None,
        sleep_seconds: float = 0.5,
        timeout_seconds: float = 20.0,
        transport: Optional[Callable[[urllib.request.Request], bytes]] = None,
    ) -> None:
        self.headers = {"User-Agent": DEFAULT_USER_AGENT, **(headers or {})}
        self.sleep_seconds = sleep_seconds
        self.timeout_seconds = timeout_seconds
        self._transport = transport
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.sleep_seconds:
            time.sleep(self.sleep_seconds - elapsed)

    def get_json(self, url: str) -> Any:
        self._throttle()
        req = urllib.request.Request(url, headers=self.headers, method="GET")
        log.debug("GET %s", url)
        if self._transport is not None:
            body = self._transport(req)
        else:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read()
        self._last_request_at = time.monotonic()
        return json.loads(body)


# ---------------------------------------------------------------------------
# SportNinja (current seasons) — snokingahl.com
# ---------------------------------------------------------------------------

SPORTNINJA_BASE = "https://metal-api.sportninja.net"
SPORTNINJA_HEADERS = {
    "Origin": "https://snokingahl.com",
    "Referer": "https://snokingahl.com/",
    "Accept": "application/json",
}
SPORTNINJA_SKAHL_ORG_ID = "77NV8cZJ8xzsgvjL"

# stat-id → unified-field. Determined from HAR; consistent across pages.
_SN_STAT_BY_ID = {
    "1": "goals",
    "2": "games_played",
    "3": "assists",
    "4": "points",
    "5": "pim",
    "6": "points_per_game",
}


class SportNinjaSource:
    """Reads from the SportNinja public API used by snokingahl.com."""

    def __init__(
        self,
        org_id: str = SPORTNINJA_SKAHL_ORG_ID,
        http: Optional[HttpClient] = None,
    ) -> None:
        self.org_id = org_id
        self.http = http or HttpClient(headers=SPORTNINJA_HEADERS)

    # ---- discovery ------------------------------------------------------

    def list_seasons(self) -> list[dict]:
        """Return the org's top-level Season schedules, newest first."""
        url = (
            f"{SPORTNINJA_BASE}/v1/organizations/{self.org_id}/schedules"
            "?sort=starts_at&direction=desc"
        )
        return self.http.get_json(url).get("data", []) or []

    def latest_season(self, include_playoffs: bool = False) -> dict:
        """Return the most recent season schedule (excludes playoffs by default).

        SportNinja models playoffs as separate Season schedules whose name
        contains "Playoffs"; we usually want the regular-season parent. Pass
        include_playoffs=True to get whichever is newest by start date.
        """
        seasons = self.list_seasons()
        if not include_playoffs:
            seasons = [s for s in seasons if "playoff" not in (s.get("name", "")).lower()]
        if not seasons:
            raise ValueError("No seasons returned from SportNinja API")
        return seasons[0]

    # ---- data pull ------------------------------------------------------

    def iter_stats_records(
        self,
        season_id: str,
        sort_by: int = 4,    # 4 = Points; sort doesn't change the records returned
        page_size: int = 50, # server-controlled, kept for documentation
        max_pages: Optional[int] = None,
    ) -> Iterator[dict]:
        """Yield raw player-stats records for one season, across all pages."""
        page = 1
        while True:
            qs = urllib.parse.urlencode(
                {"page": page, "sortBy": sort_by, "sort": "desc", "goalie": 0, "global": 1}
            )
            url = f"{SPORTNINJA_BASE}/v1/schedules/{season_id}/stats?{qs}"
            payload = self.http.get_json(url)
            records = payload.get("data") or []
            for rec in records:
                yield rec
            pagination = (payload.get("meta") or {}).get("pagination") or {}
            total_pages = int(pagination.get("total") or 1)
            if max_pages is not None and page >= max_pages:
                return
            if page >= total_pages:
                return
            page += 1

    # ---- parsing --------------------------------------------------------

    @staticmethod
    def to_unified(record: dict, season_name: str) -> PlayerSeasonRecord:
        """Convert one /stats record into a PlayerSeasonRecord."""
        player = record.get("player") or {}
        team = record.get("team") or {}
        schedule = record.get("schedule") or {}

        # Build a canonical {field_name: numeric_value} from stats[]
        values: dict[str, float] = {}
        for entry in record.get("stats") or []:
            field_name = _SN_STAT_BY_ID.get(str(entry.get("id")))
            if not field_name:
                continue
            values[field_name] = _to_float(entry.get("value"))

        gp = int(values.get("games_played", 0) or 0)
        g = int(values.get("goals", 0) or 0)
        a = int(values.get("assists", 0) or 0)
        p = int(values.get("points", 0) or 0)
        pim = int(values.get("pim", 0) or 0)
        # SportNinja serves points-per-game (id=6) directly; goals/assists per
        # game must be derived. Use the server's value when available so we
        # don't disagree with what the league site shows.
        ppg = values.get("points_per_game")
        if ppg is None:
            ppg = round(p / gp, 3) if gp else 0.0

        full_name = (player.get("full_name") or "").strip()
        if not full_name:
            full_name = " ".join(
                part for part in (player.get("name_first"), player.get("name_last")) if part
            ).strip()

        return PlayerSeasonRecord(
            player_id=str(player.get("id") or ""),
            name=full_name,
            team=team.get("name_full") or team.get("abbreviation") or "",
            season=season_name,
            league="SKAHL",
            games_played=gp,
            goals=g,
            assists=a,
            points=p,
            pim=pim,
            goals_per_game=round(g / gp, 3) if gp else 0.0,
            assists_per_game=round(a / gp, 3) if gp else 0.0,
            points_per_game=float(ppg),
            source="snokingahl_sportninja",
            division=schedule.get("name"),
            team_id=str(team.get("id") or "") or None,
        )


# ---------------------------------------------------------------------------
# Historical site — snokinghockeyleague.com
# ---------------------------------------------------------------------------

HISTORICAL_BASE = "https://snokinghockeyleague.com"
HISTORICAL_HEADERS = {
    "Referer": "https://snokinghockeyleague.com/",
    "Accept": "application/json, text/plain, */*",
}


class HistoricalSource:
    """Reads from the legacy snokinghockeyleague.com JSON API."""

    def __init__(self, http: Optional[HttpClient] = None) -> None:
        self.http = http or HttpClient(headers=HISTORICAL_HEADERS)

    # ---- discovery ------------------------------------------------------

    def list_seasons(self, include_archived: bool = True) -> list[dict]:
        """Return all seasons (active + archived). Each entry has id, name, leagueId."""
        url = f"{HISTORICAL_BASE}/api/season/all/0"
        d = self.http.get_json(url)
        seasons = list(d.get("seasons") or [])
        if include_archived:
            seasons.extend(d.get("archivedSeasons") or [])
        return seasons

    # ---- data pull ------------------------------------------------------

    def fetch_season_stats(self, season_id: int | str) -> list[dict]:
        """Return the raw `[{division, skaters[]}, ...]` array for one season."""
        url = f"{HISTORICAL_BASE}/api/player/statsBySeason/{season_id}"
        return self.http.get_json(url) or []

    def iter_skater_records(
        self,
        season_id: int | str,
        include_goalies: bool = False,
    ) -> Iterator[tuple[dict, dict]]:
        """Yield (division, skater) pairs for one season."""
        for div_block in self.fetch_season_stats(season_id):
            div = div_block.get("division") or {}
            for sk in div_block.get("skaters") or []:
                if not include_goalies and sk.get("isSkaterGoaltender"):
                    continue
                yield div, sk

    # ---- parsing --------------------------------------------------------

    @staticmethod
    def to_unified(division: dict, skater: dict, season_name: str) -> PlayerSeasonRecord:
        """Convert one historical skater record into a PlayerSeasonRecord."""
        stats = skater.get("stats") or {}

        gp = int(stats.get("GP") or 0)
        g = int(stats.get("G") or 0)
        a = int(stats.get("A") or 0)
        p = int(stats.get("P") or 0)
        pim = int(stats.get("PIM") or 0)

        # Historical site exposes per-game stats directly. Note: PPG here is
        # power-play goals (not points-per-game); the per-game stat is PTPG.
        gpg = _to_float(stats.get("GPG"))
        apg = _to_float(stats.get("APG"))
        ptpg = _to_float(stats.get("PTPG"))
        # If the server didn't compute them, derive.
        if gpg == 0.0 and gp:
            gpg = round(g / gp, 3)
        if apg == 0.0 and gp:
            apg = round(a / gp, 3)
        if ptpg == 0.0 and gp:
            ptpg = round(p / gp, 3)

        first = (skater.get("first") or "").strip()
        last = (skater.get("last") or "").strip()
        full_name = f"{first} {last}".strip()

        return PlayerSeasonRecord(
            player_id=str(skater.get("playerId") or ""),
            name=full_name,
            team=skater.get("teamName") or "",
            season=season_name,
            league="SKAHL",
            games_played=gp,
            goals=g,
            assists=a,
            points=p,
            pim=pim,
            goals_per_game=gpg,
            assists_per_game=apg,
            points_per_game=ptpg,
            source="snokinghockeyleague",
            division=division.get("name"),
            team_id=(str(skater.get("teamId")) if skater.get("teamId") is not None else None),
        )


# ---------------------------------------------------------------------------
# Convenience top-level functions
# ---------------------------------------------------------------------------

def scrape_current(
    season_id: Optional[str] = None,
    season_name: Optional[str] = None,
    source: Optional[SportNinjaSource] = None,
    include_playoffs: bool = False,
) -> Iterator[PlayerSeasonRecord]:
    """Scrape one current SportNinja season. If `season_id` is None, picks latest.

    Yields PlayerSeasonRecord objects; the caller decides what to do with them
    (write to JSON/CSV, push to a database, etc.).
    """
    src = source or SportNinjaSource()
    if season_id is None:
        season = src.latest_season(include_playoffs=include_playoffs)
        season_id = season["id"]
        season_name = season_name or season.get("name") or season_id
    else:
        # Look up the season's display name if we can; fall back to the id.
        if season_name is None:
            try:
                seasons = src.list_seasons()
                match = next((s for s in seasons if s.get("id") == season_id), None)
                season_name = (match or {}).get("name") or season_id
            except Exception:
                season_name = season_id

    log.info("scrape_current: season_id=%s name=%r", season_id, season_name)
    for rec in src.iter_stats_records(season_id):
        yield SportNinjaSource.to_unified(rec, season_name)


def scrape_historical(
    season_id: int | str,
    season_name: Optional[str] = None,
    source: Optional[HistoricalSource] = None,
    include_goalies: bool = False,
) -> Iterator[PlayerSeasonRecord]:
    """Scrape one historical season."""
    src = source or HistoricalSource()
    if season_name is None:
        try:
            seasons = src.list_seasons()
            match = next((s for s in seasons if s.get("id") == int(season_id)), None)
            season_name = (match or {}).get("name") or str(season_id)
        except Exception:
            season_name = str(season_id)

    log.info("scrape_historical: season_id=%s name=%r", season_id, season_name)
    for div, skater in src.iter_skater_records(season_id, include_goalies=include_goalies):
        yield HistoricalSource.to_unified(div, skater, season_name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_float(value) -> float:
    """Coerce a value to float, treating None / '' / non-numeric as 0.0."""
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def write_json(records: Iterable[PlayerSeasonRecord], path: str) -> int:
    rows = [r.as_dict() for r in records]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    return len(rows)


def write_csv(records: Iterable[PlayerSeasonRecord], path: str) -> int:
    rows = [r.as_dict() for r in records]
    if not rows:
        with open(path, "w", encoding="utf-8") as f:
            pass
        return 0
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scrape SKAHL player-season stats into a unified JSON/CSV.",
    )
    parser.add_argument("--out", default="players.json", help="Output file (.json or .csv)")
    parser.add_argument("-v", "--verbose", action="store_true")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_current = sub.add_parser("current", help="Scrape the current SportNinja season")
    p_current.add_argument("--season-id", help="SportNinja season schedule ID (default: latest)")
    p_current.add_argument("--include-playoffs", action="store_true")

    p_hist = sub.add_parser("historical", help="Scrape one historical season")
    p_hist.add_argument("--season-id", required=True, type=int)
    p_hist.add_argument("--include-goalies", action="store_true")

    p_all_hist = sub.add_parser(
        "historical-all", help="Scrape every historical season (one record per player-season)"
    )
    p_all_hist.add_argument("--include-goalies", action="store_true")
    p_all_hist.add_argument("--limit", type=int, help="Max number of seasons (debugging)")

    p_seasons = sub.add_parser(
        "list-seasons", help="List seasons available on each source (no stats fetched)"
    )
    p_seasons.add_argument("--source", choices=["current", "historical", "both"], default="both")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.cmd == "list-seasons":
        if args.source in ("current", "both"):
            print("# SportNinja (snokingahl.com)")
            for s in SportNinjaSource().list_seasons():
                print(f"  {s.get('id')}\t{s.get('starts_at','')[:10]}\t{s.get('name')}")
        if args.source in ("historical", "both"):
            print("# Historical (snokinghockeyleague.com)")
            for s in HistoricalSource().list_seasons():
                print(f"  {s.get('id')}\t{s.get('name')}")
        return 0

    if args.cmd == "current":
        records = list(scrape_current(season_id=args.season_id, include_playoffs=args.include_playoffs))
    elif args.cmd == "historical":
        records = list(scrape_historical(args.season_id))
    elif args.cmd == "historical-all":
        src = HistoricalSource()
        seasons = src.list_seasons()
        if args.limit:
            seasons = seasons[: args.limit]
        records: list[PlayerSeasonRecord] = []
        for s in seasons:
            try:
                for r in scrape_historical(s["id"], season_name=s.get("name"), source=src, include_goalies=args.include_goalies):
                    records.append(r)
            except Exception as e:
                log.warning("Skipping season %s (%s): %s", s.get("id"), s.get("name"), e)
    else:
        parser.error(f"unknown command {args.cmd!r}")
        return 2

    if args.out.endswith(".csv"):
        n = write_csv(records, args.out)
    else:
        n = write_json(records, args.out)
    print(f"Wrote {n} records to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
