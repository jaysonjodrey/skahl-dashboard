#!/usr/bin/env python3
"""
SKAHL Historical Data Scraper - CORRECTED VERSION
Uses correct schema with composite PRIMARY KEY to allow players in multiple seasons/teams
"""

import requests
import sqlite3
import time
import sys
from pathlib import Path

BASE_URL = "https://snokinghockeyleague.com"
DB_PATH = Path(__file__).parent / "skahl_historical.db"

print("\n" + "="*80)
print("SKAHL DATA SCRAPER - CORRECTED VERSION")
print("Correct schema: allows same player across multiple seasons/teams")
print(f"Database: {DB_PATH}\n")

# Step 1: Fetch season list
print("[1] Fetching season list...")
try:
    response = requests.get(f"{BASE_URL}/api/season/all/0", timeout=10)
    all_seasons = response.json().get('seasons', [])
    print(f"✓ Found {len(all_seasons)} seasons")
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)

# Step 2: Fetch all divisions
print("[2] Fetching all divisions...")
try:
    all_divisions = {}
    for season in all_seasons:
        season_id = season.get('id')
        response = requests.get(f"{BASE_URL}/api/division/list/{season_id}", timeout=10)
        divs = response.json() if isinstance(response.json(), list) else []
        all_divisions[season_id] = divs
    total_divs = sum(len(divs) for divs in all_divisions.values())
    print(f"✓ Found {total_divs} divisions")
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)

# Step 3: Initialize database with CORRECT schema
print("[3] Initializing database with corrected schema...")
try:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Create tables with correct schema
    cursor.execute("""CREATE TABLE IF NOT EXISTS seasons (
        id INT PRIMARY KEY, league_id INT, name TEXT, format INT,
        to_display INT, is_archived INT, is_registering INT)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS divisions (
        id INT PRIMARY KEY, season_id INT, name TEXT)""")

    # CORRECTED: Composite PRIMARY KEY (id, season_id, division_id)
    # This allows same player to appear in multiple seasons with different teams
    cursor.execute("""CREATE TABLE IF NOT EXISTS players (
        id INT,
        season_id INT,
        division_id INT,
        team_id INT,
        team_name TEXT,
        first_name TEXT,
        last_name TEXT,
        jersey_number INT,
        position INT,
        position_str TEXT,
        status INT,
        status_str TEXT,
        primary_team_name TEXT,
        PRIMARY KEY (id, season_id, division_id)
    )""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS player_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT, player_id INT, season_id INT,
        gp INT, goals INT, assists INT, points INT, pim INT, ppg INT, shg INT,
        gwg INT, gpg REAL, apg REAL, ptpg REAL, ggp INT, ggls INT, gass INT,
        gpts INT, gpim INT, gpp REAL, spg REAL, sag REAL, spt REAL, spim REAL,
        min INT, w INT, l INT, otl INT, so INT, gaa REAL, sv REAL, svp REAL)""")

    # Clear existing data
    cursor.execute("DELETE FROM player_stats")
    cursor.execute("DELETE FROM players")
    cursor.execute("DELETE FROM divisions")
    cursor.execute("DELETE FROM seasons")
    conn.commit()
    print("✓ Database ready with corrected schema")
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)

# Step 4: Load season metadata
print("[4] Loading season metadata...")
try:
    for season in all_seasons:
        cursor.execute(
            "INSERT INTO seasons VALUES (?, ?, ?, ?, ?, ?, ?)",
            (season.get('id'), season.get('leagueId'), season.get('name'),
             season.get('format'), season.get('toDisplay'),
             season.get('isArchived'), season.get('isRegistering')))
    conn.commit()
    print(f"✓ Loaded {len(all_seasons)} seasons")
except Exception as e:
    print(f"✗ Error: {e}")
    conn.close()
    sys.exit(1)

# Step 5: Fetch division data
print(f"\n[5] Fetching player data for all divisions...\n")

total_players = 0
total_stats = 0
total_divs_with_data = 0

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
            response = requests.get(
                f"{BASE_URL}/api/player/statsByDiv/{season_id}/{div_id}",
                timeout=10
            )
            response.raise_for_status()
            div_data = response.json()

            if not isinstance(div_data, dict):
                continue

            cursor.execute("INSERT OR IGNORE INTO divisions VALUES (?, ?, ?)",
                          (div_id, season_id, div_name))

            div_players = 0

            # Process skaters and goalies
            # CORRECTED: Use INSERT (not INSERT OR IGNORE) since composite KEY allows same player in different divisions
            for person_type in ['skaters', 'goalies']:
                for person in div_data.get(person_type, []):
                    player_id = person.get('playerId')
                    try:
                        cursor.execute(
                            "INSERT INTO players VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (player_id, season_id, div_id, person.get('teamId'),
                             person.get('teamName'), person.get('first'), person.get('last'),
                             person.get('number'), person.get('position'),
                             person.get('positionStr'), person.get('status'),
                             person.get('statusStr'), None))  # primary_team_name will be filled later

                        stats = person.get('stats', {})
                        cursor.execute(
                            """INSERT INTO player_stats
                            (player_id, season_id, gp, goals, assists, points, pim, ppg, shg, gwg,
                             gpg, apg, ptpg, ggp, ggls, gass, gpts, gpim, gpp, spg, sag, spt,
                             spim, min, w, l, otl, so, gaa, sv, svp)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (player_id, season_id, stats.get('GP'), stats.get('G'),
                             stats.get('A'), stats.get('P'), stats.get('PIM'),
                             stats.get('PPG'), stats.get('SHG'), stats.get('GWG'),
                             stats.get('GPG'), stats.get('APG'), stats.get('PTPG'),
                             stats.get('GGP'), stats.get('GGLS'), stats.get('GASS'),
                             stats.get('GPTS'), stats.get('GPIM'), stats.get('GPP'),
                             stats.get('SPG'), stats.get('SAG'), stats.get('SPT'),
                             stats.get('SPIM'), stats.get('MIN'), stats.get('W'),
                             stats.get('L'), stats.get('OTL'), stats.get('SO'),
                             stats.get('GAA'), stats.get('SV'), stats.get('SVP')))
                        div_players += 1
                        total_stats += 1
                    except sqlite3.IntegrityError:
                        # Duplicate in same division (shouldn't happen, but handle gracefully)
                        pass

            if div_players > 0:
                total_divs_with_data += 1
                total_players += div_players
                conn.commit()
                progress = f"[{season_idx}/{len(all_seasons)}] {season_name:<40} {div_idx:2}/{len(divisions):2}"
                print(f"{progress} ✓ {div_players:3} players")
            else:
                print(f"[{season_idx}/{len(all_seasons)}] {season_name:<40} {div_idx:2}/{len(divisions):2} - empty")

            time.sleep(0.2)

        except Exception as e:
            print(f"[{season_idx}/{len(all_seasons)}] {season_name:<40} {div_idx:2}/{len(divisions):2} ✗ {str(e)[:30]}")
            time.sleep(0.5)

conn.close()

# Summary
print("\n" + "="*80)
print(f"✓ SCRAPE COMPLETE")
print("="*80)
print(f"Total players loaded: {total_players}")
print(f"Total stat records:   {total_stats}")
print(f"Divisions with data:  {total_divs_with_data}")
db_size = DB_PATH.stat().st_size / 1024 / 1024 if DB_PATH.exists() else 0
print(f"Database size:        {db_size:.2f} MB")
print("\n✓ Schema now allows same player in multiple seasons with different teams!")
print("="*80 + "\n")
