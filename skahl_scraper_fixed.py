#!/usr/bin/env python3
"""
SKAHL Historical Data Scraper - FIXED VERSION
Uses correct API endpoint: /api/player/statsByDiv/{seasonId}/{divisionId}
This fetches complete player rosters per division (not incomplete season aggregates)
"""

import requests
import sqlite3
import time
from pathlib import Path

BASE_URL = "https://snokinghockeyleague.com"
DB_PATH = Path.home() / "Documents" / "Claude" / "Projects" / "SKAHL Dashboard" / "skahl_historical.db"

print("\n" + "="*80)
print("SKAHL DATA SCRAPER - FIXED VERSION")
print("Using /api/player/statsByDiv endpoint for complete division data")
print("="*80)

# Get all seasons
print("\n[1] Fetching season list...")
try:
    response = requests.get(f"{BASE_URL}/api/season/all/0", timeout=10)
    all_seasons = response.json().get('seasons', [])
    print(f"✓ Found {len(all_seasons)} seasons")
except Exception as e:
    print(f"✗ Error: {e}")
    exit(1)

# Get all divisions
print("[2] Fetching all divisions...")
try:
    all_divisions = {}
    for season in all_seasons:
        season_id = season.get('id')
        response = requests.get(f"{BASE_URL}/api/division/list/{season_id}", timeout=10)
        divs = response.json() if isinstance(response.json(), list) else []
        all_divisions[season_id] = divs
    total_divs = sum(len(divs) for divs in all_divisions.values())
    print(f"✓ Found {total_divs} divisions across all seasons")
except Exception as e:
    print(f"✗ Error: {e}")
    exit(1)

# Connect once for all inserts
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Clear existing data to start fresh
print("\n[3] Clearing existing data...")
cursor.execute("DELETE FROM player_stats")
cursor.execute("DELETE FROM players")
cursor.execute("DELETE FROM divisions")
cursor.execute("DELETE FROM seasons")
print("✓ Cleared previous data")

# Load season metadata
print("[4] Loading season metadata...")
for season in all_seasons:
    cursor.execute(
        "INSERT INTO seasons VALUES (?, ?, ?, ?, ?, ?, ?)",
        (season.get('id'), season.get('leagueId'), season.get('name'),
         season.get('format'), season.get('toDisplay'),
         season.get('isArchived'), season.get('isRegistering')))
conn.commit()
print(f"✓ Loaded {len(all_seasons)} seasons")

# Fetch and insert data for each division
print(f"\n[5] Fetching complete player data for all divisions...\n")

total_divs_processed = 0
total_players = 0
total_stats = 0
total_divisions_with_data = 0

for season_idx, season in enumerate(all_seasons, 1):
    season_id = season.get('id')
    season_name = season.get('name')
    divisions = all_divisions.get(season_id, [])

    if not divisions:
        continue

    for div_idx, division in enumerate(divisions, 1):
        div_id = division.get('id')
        div_name = division.get('name')

        try:
            # Fetch player data for this specific division
            response = requests.get(
                f"{BASE_URL}/api/player/statsByDiv/{season_id}/{div_id}",
                timeout=10
            )
            response.raise_for_status()
            div_data = response.json()

            if not isinstance(div_data, dict):
                continue

            # Insert division
            cursor.execute(
                "INSERT OR IGNORE INTO divisions VALUES (?, ?, ?)",
                (div_id, season_id, div_name)
            )

            div_players = 0
            div_stats = 0

            # Process skaters
            for skater in div_data.get('skaters', []):
                player_id = skater.get('playerId')
                cursor.execute(
                    "INSERT OR IGNORE INTO players VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (player_id, season_id, div_id, skater.get('teamId'),
                     skater.get('teamName'), skater.get('first'), skater.get('last'),
                     skater.get('number'), skater.get('position'),
                     skater.get('positionStr'), skater.get('status'),
                     skater.get('statusStr')))

                st = skater.get('stats', {})
                cursor.execute(
                    """INSERT INTO player_stats
                    (player_id, season_id, gp, goals, assists, points, pim, ppg, shg, gwg,
                     gpg, apg, ptpg, ggp, ggls, gass, gpts, gpim, gpp, spg, sag, spt,
                     spim, min, w, l, otl, so, gaa, sv, svp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (player_id, season_id, st.get('GP'), st.get('G'),
                     st.get('A'), st.get('P'), st.get('PIM'),
                     st.get('PPG'), st.get('SHG'), st.get('GWG'),
                     st.get('GPG'), st.get('APG'), st.get('PTPG'), st.get('GGP'),
                     st.get('GGLS'), st.get('GASS'), st.get('GPTS'), st.get('GPIM'),
                     st.get('GPP'), st.get('SPG'), st.get('SAG'), st.get('SPT'),
                     st.get('SPIM'), st.get('MIN'), st.get('W'), st.get('L'),
                     st.get('OTL'), st.get('SO'), st.get('GAA'), st.get('SV'), st.get('SVP')))
                div_players += 1
                div_stats += 1

            # Process goalies
            for goalie in div_data.get('goalies', []):
                player_id = goalie.get('playerId')
                cursor.execute(
                    "INSERT OR IGNORE INTO players VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (player_id, season_id, div_id, goalie.get('teamId'),
                     goalie.get('teamName'), goalie.get('first'), goalie.get('last'),
                     goalie.get('number'), goalie.get('position'),
                     goalie.get('positionStr'), goalie.get('status'),
                     goalie.get('statusStr')))

                st = goalie.get('stats', {})
                cursor.execute(
                    """INSERT INTO player_stats
                    (player_id, season_id, gp, goals, assists, points, pim, ppg, shg, gwg,
                     gpg, apg, ptpg, ggp, ggls, gass, gpts, gpim, gpp, spg, sag, spt,
                     spim, min, w, l, otl, so, gaa, sv, svp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (player_id, season_id, st.get('GP'), st.get('G'),
                     st.get('A'), st.get('P'), st.get('PIM'),
                     st.get('PPG'), st.get('SHG'), st.get('GWG'),
                     st.get('GPG'), st.get('APG'), st.get('PTPG'), st.get('GGP'),
                     st.get('GGLS'), st.get('GASS'), st.get('GPTS'), st.get('GPIM'),
                     st.get('GPP'), st.get('SPG'), st.get('SAG'), st.get('SPT'),
                     st.get('SPIM'), st.get('MIN'), st.get('W'), st.get('L'),
                     st.get('OTL'), st.get('SO'), st.get('GAA'), st.get('SV'), st.get('SVP')))
                div_players += 1
                div_stats += 1

            if div_players > 0:
                total_divisions_with_data += 1
                total_players += div_players
                total_stats += div_stats

            conn.commit()
            total_divs_processed += 1

            # Progress indicator
            progress = f"[{season_idx}/{len(all_seasons)}] {season_name:40s} {div_idx:2d}/{len(divisions):2d}"
            if div_players > 0:
                print(f"{progress} ✓ {div_players:3d} players")
            else:
                print(f"{progress} - no data")

            time.sleep(0.2)  # Respectful rate limiting

        except Exception as e:
            print(f"[{season_idx}/{len(all_seasons)}] {season_name:40s} {div_idx:2d}/{len(divisions):2d} ✗ {str(e)[:40]}")
            time.sleep(0.5)

conn.close()

# Final summary
print("\n" + "="*80)
print("✓ COMPLETE!")
print("="*80)
print(f"Seasons processed:     {len(all_seasons)}")
print(f"Divisions processed:   {total_divs_processed}")
print(f"Divisions with data:   {total_divisions_with_data}")
print(f"Total players:         {total_players}")
print(f"Total stat records:    {total_stats}")
print("="*80 + "\n")
