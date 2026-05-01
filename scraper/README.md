# SKAHL Stats Scraper

Pulls player-season records from both SKAHL data sources into one unified schema.

- **Current seasons** (`snokingahl.com`, SportNinja) — paginated `/v1/schedules/{id}/stats`
- **Historical seasons** (`snokinghockeyleague.com`) — `/api/player/statsBySeason/{id}`

No auth, no Playwright — just `urllib`. Standard library only, Python 3.10+.

## Quick start

```bash
cd scraper

# List all seasons available on each source
python skahl_scraper.py list-seasons

# Scrape the current SportNinja season (auto-detects latest non-playoff)
python skahl_scraper.py current --out current.json

# Scrape one specific historical season
python skahl_scraper.py historical --season-id 1091 --out historical_2023_24_fw.json

# Scrape every historical season (one record per player-season)
python skahl_scraper.py historical-all --out historical_all.json
```

Add `--out <file>.csv` to write CSV instead of JSON.

## Verifying historical completeness — seasonId 1091

The HAR we worked from was for season `1099` (2024 SKAHL Summer Playoffs), which
returned 5 skaters per division. To confirm the endpoint returns full rosters
(not just leaders), run:

```bash
python skahl_scraper.py historical --season-id 1091 --out _check_1091.json -v
python -c "import json; d = json.load(open('_check_1091.json')); print(f'{len(d)} records'); from collections import Counter; print(Counter(r['division'] for r in d))"
```

A regular-season Fall-Winter division with 8–10 teams should yield 100+ skaters
each. If the per-division counts look truncated, the API is rate-limiting or
filtering — re-capture a HAR with the "show all" UI affordance toggled.

## Use as a library

```python
from skahl_scraper import (
    SportNinjaSource, HistoricalSource,
    scrape_current, scrape_historical,
    write_json, write_csv,
)

# Streaming use — yields PlayerSeasonRecord objects
for rec in scrape_current():
    print(rec.name, rec.points_per_game)

# Bulk dump
records = list(scrape_historical(1091))
write_csv(records, "out.csv")

# Inject a custom HTTP client for testing or rate-limiting
from skahl_scraper import HttpClient
src = SportNinjaSource(http=HttpClient(sleep_seconds=2.0))
```

## Unified record schema

Every record has these fields (`PlayerSeasonRecord`):

| Field | Type | Notes |
|---|---|---|
| `player_id` | str | Opaque ID. SportNinja uses 16-char strings; historical uses ints (cast to str). Not comparable across sources. |
| `name` | str | "First Last" |
| `team` | str | Full team name |
| `season` | str | Display name, e.g. `"Winter 2025-26"` |
| `league` | str | Always `"SKAHL"` |
| `games_played` | int | |
| `goals` | int | |
| `assists` | int | |
| `points` | int | Hockey invariant: `points == goals + assists` |
| `pim` | int | Penalty minutes |
| `goals_per_game` | float | |
| `assists_per_game` | float | |
| `points_per_game` | float | SportNinja serves this directly (`PTS/G`); historical uses `PTPG` (NOT `PPG`, which is power-play goals on that site) |
| `source` | str | `"snokingahl_sportninja"` or `"snokinghockeyleague"` |
| `division` | str \| None | e.g. `"C-Wednesday"` |
| `team_id` | str \| None | |

## Tests

```bash
python -m unittest tests.test_scraper -v
```

Tests replay the captured HAR data through the scraper via a mock transport, so
they validate the parsing pipeline end-to-end without needing network access.
8 tests, ~0.1s.

## Architecture

The module is one file (`skahl_scraper.py`) with two `Source` classes that each
expose three layers:

```
list_seasons()          ─┐
list_*_records()         │ ── streams raw JSON records from the API
to_unified(record, name) ┘── converts one raw record to PlayerSeasonRecord
```

`HttpClient` is the thin transport layer — pluggable via `transport=callable`
for tests, with built-in throttling and JSON decoding. Replace it with
`requests` if you want connection pooling, but stdlib `urllib` is plenty for
~60 requests/week.

## Sample output

See `../sample_output/` for JSON/CSV files generated from the captured HARs:
- `current_winter_2025_26_page1.{json,csv}` — 50 records (one page; full
  season is 30 pages × 50 = 1465 records when run live)
- `historical_2024_summer_playoffs.{json,csv}` — 65 records, all 13 divisions

## Known caveats

1. **Goalies are excluded** by default on both sources. Pass `--include-goalies`
   to the historical CLI; for SportNinja you'd need to also pass `goalie=1` to
   the API (not wired into the CLI — the dashboard only cares about skaters).
2. **Network access required from the runner.** This sandbox can't reach the
   APIs (egress allowlist), so I validated parsing against HAR fixtures only.
   Run from your laptop or a GitHub Actions runner — both should work.
3. **Polite throttling** is 0.5s between requests by default. Tweak via
   `HttpClient(sleep_seconds=...)`.
4. **No retry/backoff** built in. Add it if the site flakes; weekly load is
   negligible enough that it probably won't.
