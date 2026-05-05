#!/usr/bin/env python3
"""
SKAHL Historical Data Scraper - Windows Version
Run locally on your Windows machine to pull SKAHL data without sandbox restrictions
Incrementally adds seasons to your existing database

Usage:
    python skahl_scraper_windows.py                    # Fetch all missing seasons
    python skahl_scraper_windows.py --seasons 1090     # Fetch specific season ID
    python skahl_scraper_windows.py --help             # Show options
"""

import requests
import sqlite3
import time
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

BASE_URL = "https://snokinghockeyleague.com"
DEFAULT_DB = Path.home() / "Documents" / "Claude" / "Projects" / "SKAHL Dashboard" / "skahl_historical.db"

class SkahlScraper:
    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def init_db(self):
        """Create database schema if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""CREATE TABLE IF NOT EXISTS seasons (
            id INT PRIMARY KEY,
            league_id INT,
            name TEXT,
            format INT,
            to_display INT,
            is_archived INT,
            is_registering INT
        )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS divisions (
            id INT PRIMARY KEY,
            season_id INT,
            name TEXT
        )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS players (
            id INT PRIMARY KEY,
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
            status_str TEXT
        )""")

        cursor.execute("""CREATE TABLE IF NOT EXISTS player_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INT,
            season_id INT,
            gp INT, goals INT, assists INT, points INT, pim INT,
            ppg INT, shg INT, gwg INT, gpg REAL, apg REAL, ptpg REAL,
            ggp INT, ggls INT, gass INT, gpts INT, gpim INT, gpp REAL,
            spg REAL, sag REAL, spt REAL, spim REAL, min INT,
            w INT, l INT, otl INT, so INT, gaa REAL, sv REAL, svp REAL
        )""")

        conn.commit()
        conn.close()

    def get_json(self, endpoint):
        """Fetch JSON from API with error handling"""
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.Timeout:
            print(f"  ⚠️  Timeout: {endpoint}")
            return None
        except Exception as e:
            print(f"  ❌ Error: {endpoint} - {str(e)[:50]}")
            return None

    def get_all_seasons(self):
        """Get list of all seasons"""
        data = self.get_json("/api/season/all/0")
        return data.get('seasons', []) if data else []

    def get_existing_seasons(self):
        """Get seasons that already have player data in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Check for seasons that have actual player data, not just metadata
        cursor.execute("SELECT DISTINCT season_id FROM players")
        seasons = {row[0] for row in cursor.fetchall()}
        conn.close()
        return seasons

    def get_missing_seasons(self):
        """Get seasons not yet in database"""
        all_seasons = self.get_all_seasons()
        existing = self.get_existing_seasons()
        return [s for s in all_seasons if s.get('id') not in existing]

    def fetch_season(self, season_id, season_name):
        """Fetch and load a single season"""
        player_stats = self.get_json(f"/api/player/statsBySeason/{season_id}")
        if not player_stats or not isinstance(player_stats, list):
            return 0, 0, 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        div_count = 0
        player_count = 0
        stat_count = 0
        inserted_players = set()

        for division_data in player_stats:
            division = division_data.get('division', {})
            division_id = division.get('id')

            cursor.execute("INSERT OR IGNORE INTO divisions VALUES (?, ?, ?)",
                (division_id, season_id, division.get('name')))
            div_count += 1

            # Process skaters and goalies
            for person_list in [division_data.get('skaters', []), division_data.get('goalies', [])]:
                for person in person_list:
                    player_id = person.get('playerId')
                    if player_id not in inserted_players:
                        cursor.execute(
                            """INSERT INTO players
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (player_id, season_id, division_id, person.get('teamId'),
                             person.get('teamName'), person.get('first'), person.get('last'),
                             person.get('number'), person.get('position'),
                             person.get('positionStr'), person.get('status'),
                             person.get('statusStr')))
                        inserted_players.add(player_id)
                        player_count += 1

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
                    stat_count += 1

        conn.commit()
        conn.close()
        return div_count, player_count, stat_count

    def scrape_seasons(self, season_ids=None):
        """Scrape specified seasons or all missing seasons"""
        print("\n" + "="*80)
        print("SKAHL HISTORICAL DATA SCRAPER - Windows Version")
        print("="*80)

        # Get seasons to fetch
        all_seasons = self.get_all_seasons()
        if not all_seasons:
            print("❌ Failed to fetch season list from API")
            return False

        if season_ids:
            # Fetch specific seasons
            seasons_to_fetch = [s for s in all_seasons if s.get('id') in season_ids]
        else:
            # Fetch all missing seasons
            existing = self.get_existing_seasons()
            seasons_to_fetch = [s for s in all_seasons if s.get('id') not in existing]

        if not seasons_to_fetch:
            print("✓ Database is up to date - no missing seasons")
            print("="*80)
            return True

        # Load season metadata
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for season in all_seasons:
            cursor.execute(
                "INSERT OR IGNORE INTO seasons VALUES (?, ?, ?, ?, ?, ?, ?)",
                (season.get('id'), season.get('leagueId'), season.get('name'),
                 season.get('format'), season.get('toDisplay'),
                 season.get('isArchived'), season.get('isRegistering')))
        conn.commit()
        conn.close()

        print(f"\n📡 Fetching player data for {len(seasons_to_fetch)} season(s)...")
        print(f"   Database: {self.db_path}\n")

        total_divs = 0
        total_players = 0
        total_stats = 0
        failed = []

        for i, season in enumerate(seasons_to_fetch, 1):
            season_id = season.get('id')
            season_name = season.get('name')

            print(f"[{i:2d}/{len(seasons_to_fetch)}] {season_name:45s} ", end="", flush=True)

            divs, players, stats = self.fetch_season(season_id, season_name)

            if divs > 0:
                print(f"✓ {divs} divs | {players} players | {stats} stats")
                total_divs += divs
                total_players += players
                total_stats += stats
            else:
                print("⚠️  No data")
                failed.append(season_name)

            time.sleep(1)  # Respectful rate limiting

        # Summary
        print("\n" + "="*80)
        print("✓ SCRAPE COMPLETE")
        print("="*80)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT id) FROM seasons WHERE id IN (SELECT season_id FROM players)")
        seasons_with_data = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM seasons")
        total_seasons = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT id) FROM players")
        total_unique_players = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM player_stats")
        total_stat_records = cursor.fetchone()[0]
        conn.close()

        print(f"Seasons in DB:       {total_seasons}")
        print(f"Seasons with data:   {seasons_with_data}")
        print(f"Unique players:      {total_unique_players}")
        print(f"Total stat records:  {total_stat_records}")
        print(f"Database size:       {self.db_path.stat().st_size / 1024 / 1024:.2f} MB")

        if failed:
            print(f"\n⚠️  {len(failed)} season(s) had no data:")
            for name in failed:
                print(f"   - {name}")

        print("="*80 + "\n")
        return True

def main():
    parser = argparse.ArgumentParser(
        description="SKAHL Historical Data Scraper for Windows",
        epilog="Examples:\n"
               "  python skahl_scraper_windows.py              # Fetch all missing seasons\n"
               "  python skahl_scraper_windows.py --seasons 1090 1091  # Specific seasons\n",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                       help=f"Database path (default: {DEFAULT_DB})")
    parser.add_argument("--seasons", type=int, nargs="+",
                       help="Specific season IDs to fetch")

    args = parser.parse_args()

    scraper = SkahlScraper(args.db)
    success