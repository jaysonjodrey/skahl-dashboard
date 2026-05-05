#!/usr/bin/env python3
"""
SKAHL Scraper - Simplified Version
Much simpler and more reliable for local Windows use
"""

import requests
import sqlite3
import time
from pathlib import Path

BASE_URL = "https://snokinghockeyleague.com"
DB_PATH = Path.home() / "Documents" / "Claude" / "Projects" / "SKAHL Dashboard" / "skahl_historical.db"

print("\n" + "="*80)
print("SKAHL DATA SCRAPER")
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

# Get seasons with player data
print("[2] Checking which seasons have data...")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT DISTINCT season_id FROM players")
seasons_with_data = {row[0] for row in cursor.fetchall()}
conn.close()

missing_seasons = [s for s in all_seasons if s.get('id') not in seasons_with_data]
print(f"✓ {len(seasons_with_data)} seasons have data, {len(missing_seasons)} missing")

if not missing_seasons:
    print("\n✓ Database is complete!")
    print("="*80)
    exit(0)

print(f"\n[3] Fetching {len(missing_seasons)} missing season(s)...\n")

# Connect once for all inserts
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Update season metadata first
for season in all_seasons:
    cursor.execute(
        "INSERT OR IGNORE INTO seasons VALUES (?, ?, ?, ?, ?, ?, ?)",
        (season.get('id'), season.get('leagueId'), season.get('name'),
         season.get('format'), season.get('toDisplay'),
         season.get('isArchived'), season.get('isRegistering')))
conn.commit()

# Fetch and insert data for each missing season
total_divs = 0
total_players = 0
total_stats = 0
inserted_players = set()

for i, season in enumerate(missing_seasons, 1):
    season_id = season.get('id')
    season_name = season.get('name')

    print(f"[{i:2d}/{len(missing_seasons)}] {season_name[:50]:50s} ", end="", flush=True)

    try:
        response = requests.get(f"{BASE_URL}/api/player/statsBySeason/{season_id}", timeout=10)
        response.raise_for_status()
        player_stats = response.json()

        if not isinstance(player_stats, list):
            print("✗ Invalid response")
            time.sleep(1)
            continue

        divs = 0
        players = 0
        stats = 0

        for div_data in player_stats:
            div = div_data.get('division', {})
            div_id = div.get('id')

            cursor.execute("INSERT OR IGNORE INTO divisions VALUES (?, ?, ?)",
                (div_id, season_id, div.get('name')))
            divs += 1

            # Skaters
            for skater in div_data.get('skaters', []):
                pid = skater.get('playerId')
                cursor.execute(
                    "INSERT OR IGNORE INTO players VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (pid, season_id, div_id, skater.get('teamId'), skater.get('teamName'),
                     skater.get('first'), skater.get('last'), skater.get('number'),
                     skater.get('position'), skater.get('positionStr'),
                     skater.get('status'), skater.get('statusStr')))
                if cursor.rowcount > 0:
                    players += 1

                st = skater.get('stats', {})
                cursor.execute(
                    "INSERT INTO player_stats (player_id, season_id, gp, goals, assists, points, pim, ppg, shg, gwg, gpg, apg, ptpg, ggp, ggls, gass, gpts, gpim, gpp, spg, sag, spt, spim, min, w, l, otl, so, gaa, sv, svp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (pid, season_id, st.get('GP'), st.get('G'), st.get('A'), st.get('P'),
                     st.get('PIM'), st.get('PPG'), st.get('SHG'), st.get('GWG'),
                     st.get('GPG'), st.get('APG'), st.get('PTPG'), st.get('GGP'),
                     st.get('GGLS'), st.get('GASS'), st.get('GPTS'), st.get('GPIM'),
                     st.get('GPP'), st.get('SPG'), st.get('SAG'), st.get('SPT'),
                     st.get('SPIM'), st.get('MIN'), st.get('W'), st.get('L'),
                     st.get('OTL'), st.get('SO'), st.get('GAA'), st.get('SV'), st.get('SVP')))
                stats += 1

            # Goalies
            for goalie in div_data.get('goalies', []):
                pid = goalie.get('playerId')
                cursor.execute(
                    "INSERT OR IGNORE INTO players VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (pid, season_id, div_id, goalie.get('teamId'), goalie.get('teamName'),
                     goalie.get('first'), goalie.get('last'), goalie.get('number'),
                     goalie.get('position'), goalie.get('positionStr'),
                     goalie.get('status'), goalie.get('statusStr')))
                if cursor.rowcount > 0:
                    players += 1

                st = goalie.get('stats', {})
                cursor.execute(
                    "INSERT INTO player_stats (player_id, season_id, gp, goals, assists, points, pim, ppg, shg, gwg, gpg, apg, ptpg, ggp, ggls, gass, gpts, gpim, gpp, spg, sag, spt, spim, min, w, l, otl, so, gaa, sv, svp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (pid, season_id, st.get('GP'), st.get('G'), st.get('A'), st.get('P'),
                     st.get('PIM'), st.get('PPG'), st.get('SHG'), st.get('GWG'),
                     st.get('GPG'), st.get('APG'), st.get('PTPG'), st.get('GGP'),
                     st.get('GGLS'), st.get('GASS'), st.get('GPTS'), st.get('GPIM'),
                     st.get('GPP'), st.get('SPG'), st.get('SAG'), st.get('SPT'),
                     st.get('SPIM'), st.get('MIN'), st.get('W'), st.get('L'),
                     st.get('OTL'), st.get('SO'), st.get('GAA'), st.get('SV'), st.get('SVP')))
                stats += 1

        conn.commit()
        print(f"✓ {divs} divs | {players} players | {stats} stats")
        total_divs += divs
        total_players += players
        total_stats += stats

    except Exception as e:
        print(f"✗ {str(e)[:40]}")

    time.sleep(1)

conn.close()

# Final summary
print("\n" + "="*80)
print("✓ COMPLETE!")
print("="*80)
print(f"Divisions added:   {total_divs}")
print(f"Players added:     {total_players}")
print(f"Stats added:       {total_stats}")
print("="*80 + "\n")