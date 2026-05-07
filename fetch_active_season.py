#!/usr/bin/env python3
"""
Fetch active season data from SportNinja API → write active_seasons_data.json.

This is Step 1 of the weekly refresh pipeline. It hits snokingahl.com's
SportNinja API and outputs the JSON format expected by skahl_update_active.py.

Usage:
    python fetch_active_season.py [workspace_path]

IMPORTANT: When a new season starts, update ACTIVE_SEASON_MAP below.
To find the new season's SportNinja ID, uncomment and run list_all_seasons().
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse

# ── Paths ─────────────────────────────────────────────────────────────────────
WORKSPACE = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
OUT_PATH  = os.path.join(WORKSPACE, 'active_seasons_data.json')

# ── SportNinja config ─────────────────────────────────────────────────────────
SPORTNINJA_BASE    = "https://metal-api.sportninja.net"
SPORTNINJA_HEADERS = {
    "Origin":     "https://snokingahl.com",
    "Referer":    "https://snokingahl.com/",
    "Accept":     "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; SKAHL-Dashboard-Scraper/1.0)",
}
SKAHL_ORG_ID = "77NV8cZJ8xzsgvjL"

# ── Active seasons ─────────────────────────────────────────────────────────────
# sportninja_id → metadata used downstream by skahl_update_active.py
# UPDATE THIS when a new season begins (run list_all_seasons() to find the new ID).
ACTIVE_SEASON_MAP = {
    'SA6WRBsAXR2e6mtV': {'db_id': 1106, 'season_type': 'Regular Season'},
}

# ── Skater stat ID → field name mapping ──────────────────────────────────────
# IDs come from HAR capture of snokingahl.com — stable across seasons.
SKATER_STAT_IDS = {
    '1': 'G',
    '2': 'GP',
    '3': 'A',
    '4': 'P',
    '5': 'PiM',
    '6': 'PTS/G',
}

# ── HTTP helper ───────────────────────────────────────────────────────────────
_last_request = 0.0

def get_json(url, sleep_secs=0.75):
    """Fetch JSON with polite rate limiting (0.75s between requests)."""
    global _last_request
    elapsed = time.monotonic() - _last_request
    if elapsed < sleep_secs:
        time.sleep(sleep_secs - elapsed)
    req = urllib.request.Request(url, headers=SPORTNINJA_HEADERS, method='GET')
    with urllib.request.urlopen(req, timeout=20) as resp:
        _last_request = time.monotonic()
        return json.loads(resp.read())

# ── Season discovery ──────────────────────────────────────────────────────────
def get_season_name(season_id):
    """Look up display name from the org's schedule list."""
    url = (f"{SPORTNINJA_BASE}/v1/organizations/{SKAHL_ORG_ID}/schedules"
           "?sort=starts_at&direction=desc")
    data = get_json(url)
    for s in data.get('data', []):
        if s.get('id') == season_id:
            return s.get('name', 'Unknown Season')
    return 'Unknown Season'

def list_all_seasons():
    """Helper to print all known seasons — useful when a new season starts."""
    url = (f"{SPORTNINJA_BASE}/v1/organizations/{SKAHL_ORG_ID}/schedules"
           "?sort=starts_at&direction=desc")
    data = get_json(url)
    print("\nAll seasons on SportNinja:")
    for s in data.get('data', []):
        print(f"  id={s.get('id')}  name={s.get('name')}")

# ── Pagination ────────────────────────────────────────────────────────────────
def fetch_all_stats(season_id, goalie=0):
    """Page through /stats for one season. Returns raw SportNinja records."""
    records = []
    page = 1
    while True:
        qs = urllib.parse.urlencode({
            'page': page, 'sortBy': 4, 'sort': 'desc',
            'goalie': goalie, 'global': 1,
        })
        url = f"{SPORTNINJA_BASE}/v1/schedules/{season_id}/stats?{qs}"
        payload = get_json(url)
        page_data = payload.get('data') or []
        records.extend(page_data)

        pagination  = (payload.get('meta') or {}).get('pagination') or {}
        total_pages = int(pagination.get('total') or 1)
        label = 'goalie' if goalie else 'skater'
        print(f"    [{label}] page {page}/{total_pages}  ({len(page_data)} records)")

        if page >= total_pages:
            break
        page += 1
    return records

# ── Record parsers ────────────────────────────────────────────────────────────
def parse_skater(record):
    player   = record.get('player')   or {}
    team     = record.get('team')     or {}
    schedule = record.get('schedule') or {}

    # Map stats by ID
    stats = {}
    for entry in record.get('stats') or []:
        field = SKATER_STAT_IDS.get(str(entry.get('id', '')))
        if field:
            stats[field] = entry.get('value')

    return {
        'fn':    (player.get('name_first') or '').strip(),
        'ln':    (player.get('name_last')  or '').strip(),
        'num':   player.get('player_number'),
        'team':  (team.get('name_full') or '').strip(),
        'divId': schedule.get('id', ''),
        'div':   schedule.get('name', ''),  # div_level() in skahl_update_active.py handles full names
        'stats': stats,
    }

def parse_goalie(record):
    player   = record.get('player')   or {}
    team     = record.get('team')     or {}
    schedule = record.get('schedule') or {}

    # Goalie stat IDs aren't in the public docs — map by abbr instead
    stats = {}
    for entry in record.get('stats') or []:
        abbr = (entry.get('abbr') or '').strip()
        if abbr:
            stats[abbr] = entry.get('value')

    return {
        'fn':    (player.get('name_first') or '').strip(),
        'ln':    (player.get('name_last')  or '').strip(),
        'num':   player.get('player_number'),
        'team':  (team.get('name_full') or '').strip(),
        'divId': schedule.get('id', ''),
        'div':   schedule.get('name', ''),
        'stats': stats,
    }

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("FETCH ACTIVE SEASON — SportNinja API")
    print("=" * 60)

    result = {}

    for season_id, meta in ACTIVE_SEASON_MAP.items():
        print(f"\n[Season] {season_id}")

        season_name = get_season_name(season_id)
        print(f"  Name: {season_name}")

        print("  Fetching skaters...")
        raw_skaters = fetch_all_stats(season_id, goalie=0)
        skaters = [parse_skater(r) for r in raw_skaters]
        skaters = [s for s in skaters if s['fn'] or s['ln']]
        print(f"  → {len(skaters)} skaters")

        print("  Fetching goalies...")
        raw_goalies = fetch_all_stats(season_id, goalie=1)
        goalies = [parse_goalie(r) for r in raw_goalies]
        goalies = [g for g in goalies if g['fn'] or g['ln']]
        print(f"  → {len(goalies)} goalies")

        result[season_id] = {
            'name':    season_name,
            'skaters': skaters,
            'goalies': goalies,
        }

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)

    total_skaters = sum(len(v['skaters']) for v in result.values())
    total_goalies = sum(len(v['goalies']) for v in result.values())

    print(f"\n{'=' * 60}")
    print("FETCH COMPLETE")
    print(f"{'=' * 60}")
    print(f"Seasons written : {len(result)}")
    print(f"Total skaters   : {total_skaters}")
    print(f"Total goalies   : {total_goalies}")
    print(f"Output          : {OUT_PATH}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
