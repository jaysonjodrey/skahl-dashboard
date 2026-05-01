# SKAHL Dashboard — API Endpoint Map

Reverse-engineered from `current.har` and `historical.har`. Both sites are SPAs that hit clean JSON APIs. **Neither HAR shows an `Authorization` header on the data-read endpoints**, so scraping should not require auth. Trimmed sample payloads live in `samples.json`.

---

## 1. Current season — snokingahl.com (SportNinja platform)

Base host: `https://metal-api.sportninja.net`

The site is a SportNinja-hosted league portal. The page calls a public REST API. Static, well-known IDs are baked into the front end:

- **Organization ID (SKAHL):** `77NV8cZJ8xzsgvjL`
- **Current season schedule ID (Winter 2025-26):** `66UWZ4oxEb0HOsP5`

A SportNinja "schedule" is a hierarchy: a top-level Season schedule contains child Division schedules (e.g. "C-Wednesday", "C3"). Player records on stats endpoints carry both `team` and `schedule` (the division they played in).

### Required headers (data reads)

```
Origin:  https://snokingahl.com
Referer: https://snokingahl.com/
Accept:  application/json
User-Agent: Mozilla/5.0 ...
```

No `Authorization` header was sent. (The HAR contains a `POST /v1/auth/refresh` for some background feature, but the stats GETs do not use the resulting token.)

### Endpoints

| Purpose | Method + Path | Notes |
|---|---|---|
| List seasons under SKAHL | `GET /v1/organizations/77NV8cZJ8xzsgvjL/schedules?sort=starts_at&direction=desc` | Returns top-level "Season" schedules. Use this to discover the current season's `id`. 6 entries seen, including playoffs. |
| Children (divisions) of a season | `GET /v1/schedules/{seasonId}/children/dropdown` | Returns groups: Season / Tournament / Division. Each has `schedules[]` with `id`, `name`. |
| Season settings (stat-type config) | `GET /v1/schedules/{seasonId}/settings` | `data.settings.stats.player.displayed` is the array of stat IDs the league shows: `[2,1,3,4,5,46,6]` → GP, G, A, P, PiM, ?, PTS/G |
| **Paginated player stats (the main one)** | `GET /v1/schedules/{seasonId}/stats?page=N&sortBy=4&sort=desc&goalie=0&global=1` | 50 records/page. Winter 2025-26 has 1465 skaters → 30 pages. `global=1` means aggregated across child divisions. `goalie=0` means skaters only. |
| Top-N leaderboard | `GET /v1/schedules/{seasonId}/stats/leaderboard?global=1&goalie=0` | Returns 5 leaders per stat type. Useful as a sanity check, but the paginated endpoint above gives you everything you need to build your own leaderboards. |

### `sortBy` values (stat IDs)

These map cleanly to the values inside each stats record's `stats[]`:

| `sortBy` | abbr | meaning |
|---|---|---|
| 1 | G | Goals |
| 2 | GP | Games played |
| 3 | A | Assists |
| 4 | P | Points |
| 5 | PiM | Penalty minutes |
| 6 | PTS/G | Points per game |

For your dashboard you don't actually need to vary `sortBy` — sorting client-side is fine. Pick any value (e.g. `sortBy=4`) and just paginate.

### Response shape — `/stats?page=1&...`

```json
{
  "data": [
    {
      "player":   { "id": "LJdbhmchVVDf0kzo", "name_first": "Phin", "name_last": "Mallon", "player_number": 6, "player_type_id": 4 },
      "schedule": { "id": "bDq9teKQDRFZCNWZ", "name": "C-Wednesday" },
      "team":     { "id": "1HJ5cSiEVNSjXUWC", "name_full": "Ale Storm", "abbreviation": "ALS" },
      "stats": [
        { "id": "2", "abbr": "GP",    "value": "24" },
        { "id": "1", "abbr": "G",     "value": "28" },
        { "id": "3", "abbr": "A",     "value": "37" },
        { "id": "4", "abbr": "P",     "value": "65" },
        { "id": "5", "abbr": "PiM",   "value": "4"  },
        { "id": "6", "abbr": "PTS/G", "value": "2.71" }
      ]
    }
    // ... 49 more
  ],
  "meta": { "pagination": { "total": 30, "count": 1465, "per_page": 50, "current_page": "1", "total_pages": 30 } }
}
```

`meta.pagination.total` is **total pages**, `count` is **total records** (counter-intuitive naming, mirrors Laravel/Fractal). All `value` fields are strings — cast on ingest.

### Pulling a full season

```
for page in 1..meta.total_pages:
    GET /v1/schedules/{seasonId}/stats?page={page}&sortBy=4&sort=desc&goalie=0&global=1
    yield from response.data
```

30 pages × 50 records = ~1465 skaters for Winter 2025-26. The same loop works for any season — just swap `{seasonId}` (discovered via the org-schedules endpoint).

---

## 2. Historical — snokinghockeyleague.com

Base host: `https://snokinghockeyleague.com` (custom CMS, not SportNinja)

This is the older site. The data model is flatter: seasons → divisions → players. There's a cache-busting `?v=12700` on every request which you can ignore (or just hard-code).

### Required headers

```
Referer: https://snokinghockeyleague.com/
Accept:  application/json, text/plain, */*
User-Agent: Mozilla/5.0 ...
```

No auth.

### Endpoints

| Purpose | Method + Path | Notes |
|---|---|---|
| List all seasons | `GET /api/season/all/0?v=12700` | Returns `{ seasons[], archivedSeasons[] }`. 23 active + 0 archived in HAR. Each season has `id`, `name` (e.g. "2023-2024 Fall-Winter"), `leagueId`. |
| List divisions in a season | `GET /api/division/list/{seasonId}?v=12700` | Plain array of `{ id, name, seasonId }`. Useful but not required if you just want stats — `statsBySeason` already groups by division. |
| **Player stats by season** | `GET /api/player/statsBySeason/{seasonId}?v=12700` | Returns an array of divisions, each with a `skaters[]` array. This is your main scrape endpoint. |

### Response shape — `statsBySeason/{seasonId}`

```json
[
  {
    "division": { "id": 375, "divisionId": 375, "seasonId": 1099, "name": "Division-B1" },
    "skaters": [
      {
        "playerId": 4093, "first": "Hiron", "last": "Redman", "number": 63,
        "teamId": 2742, "teamName": "Sasquatch",
        "positionStr": "Skater", "isSkaterGoaltender": false,
        "stats": {
          "GP": 2, "G": 2, "A": 4, "P": 6, "PIM": 2,
          "PPG": 0, "SHG": 0, "GWG": 0,
          "GPG": 1.0, "APG": 2.0, "PTPG": 3.0,
          "W": 0, "L": 0, "T": 0, "OTL": 0,
          "GA": 0, "GAA": 0.0, "SV": 0, "SVP": 0.0, "SO": 0, "EGA": 0, "TOI": null, "SA": 0
          // goalie fields are zero for skaters; skater fields are zero for goalies
        },
        "Profile": { /* duplicate of "stats" — ignore */ }
      }
    ]
  }
  // ... next division
]
```

Note: `stats.PPG` here is **power-play goals**, not points-per-game. Points-per-game is `stats.PTPG` (and `GPG` = goals-per-game, `APG` = assists-per-game). Different naming convention than the SportNinja site — watch out when unifying.

> ⚠️ **Caveat on completeness:** The HAR was captured against season `1099` (2024 SKAHL Summer Playoffs) and shows only 5 skaters per division. That's plausible for a small playoff bracket but suspicious if it's *every* division. Worth running the scraper against a fuller season (e.g. `1091` = 2023-2024 Fall-Winter) and eyeballing the count. If the site truncates by default, there may be a `top=` or `limit=` query param to override — re-capture with the "show all" UI affordance toggled if you find one.

### Pulling all historical data

```
seasons = GET /api/season/all/0
for s in seasons:
    divisions = GET /api/player/statsBySeason/{s.id}
    for d in divisions:
        for skater in d.skaters:
            yield record(season=s, division=d.division, skater=skater)
```

---

## 3. Unified player-season schema mapping

Your target schema:

```
player_id, name, team, season, league, games_played, goals, assists, points,
pim, goals_per_game, assists_per_game, points_per_game, source
```

| Unified field | SportNinja (current) | Historical site |
|---|---|---|
| `player_id` | `player.id` (string, e.g. `LJdbhmchVVDf0kzo`) | `playerId` (int, e.g. `4093`) |
| `name` | `player.name_first + " " + player.name_last` | `first + " " + last` |
| `team` | `team.name_full` (with `abbreviation` available) | `teamName` |
| `season` | discovered via `/organizations/.../schedules` → `name` (e.g. "Winter 2025-26") | `season.name` from `/api/season/all/0` |
| `league` | hard-code `"SKAHL"` (or use `organization.name`) | hard-code `"SKAHL"` |
| `games_played` | `stats[id=2].value` (cast int) | `stats.GP` |
| `goals` | `stats[id=1].value` (cast int) | `stats.G` |
| `assists` | `stats[id=3].value` (cast int) | `stats.A` |
| `points` | `stats[id=4].value` (cast int) | `stats.P` |
| `pim` | `stats[id=5].value` (cast int) | `stats.PIM` |
| `goals_per_game` | derive: `goals / games_played` (server's `id=6` is PTS/G, not GPG) | `stats.GPG` |
| `assists_per_game` | derive | `stats.APG` |
| `points_per_game` | `stats[id=6].value` (cast float) | `stats.PTPG` |
| `source` | `"snokingahl_sportninja"` | `"snokinghockeyleague"` |
| (extra) `division` | `schedule.name` (e.g. "C-Wednesday") | `division.name` |
| (extra) `team_id` | `team.id` | `teamId` |

### Composite key for cross-season player linking

`player_id` is **not** comparable across the two sources — SportNinja uses opaque 16-char strings, the historical site uses ints. For roster continuity (e.g. a player who appears in both eras), a fallback composite key `lower(name) + lower(team)` is the practical option. The dashboard probably doesn't need this on day one; revisit if you build career-totals views.

### Goalies

Both APIs surface goalies separately:
- SportNinja: pass `goalie=1` in the query (different stat_type IDs).
- Historical: same response — `isSkaterGoaltender: true` and the W/L/GAA/SV/SVP/SO/SA fields populate.

Skip goalies for v1 of the dashboard — your stat list (G, A, P, PPG, GP, PIM) is skater-only. The PPG in your spec presumably means "points-per-game", in which case it's `points_per_game` above.

---

## 4. Scraper feasibility

- **No auth, no captcha, no rate-limit headers seen.** Straight `requests` + `User-Agent` + `Origin/Referer` should work. No need for Playwright on either site.
- **Sandbox couldn't verify live** — my egress proxy returns 403. You should be able to `curl` any of these from your laptop or GitHub Actions runner without issue.
- **Polite scraping:** sleep 0.5–1.0s between page hits. ~30 pages on the current site + ~23 seasons × 1 call each on the historical site = under 60 requests per weekly run. Negligible load.
- **One-time discovery:** the org ID and current season ID change rarely. Hard-code them, but resolve the *current* season ID from `/organizations/.../schedules` each run so you don't have to update code in March.
- **What can break:** SportNinja could rotate the org ID (won't happen — it's stable), or change the meaning of stat IDs (unlikely). Historical site's `?v=12700` is a build cache-buster — if they redeploy and your version becomes too stale, you may get a 304/redirect; in practice you can just drop the `?v=` param entirely and it should still work.

---

## Files in this folder

- `current.har`, `historical.har` — your captures
- `samples.json` — trimmed sample payloads from each endpoint, ready to feed into a scraper unit test
- `endpoint_map.md` — this document
