#!/usr/bin/env python3
"""
Fix duplicate stat counting caused by players in multiple divisions per season
Only count each (player_id, season_id, team_name) once, using the first (highest level) division
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "skahl_historical.db"

print("\n" + "="*80)
print("FIXING DUPLICATE STATS FROM MULTI-DIVISION PLAYERS")
print("="*80)

try:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Step 1: Find players with multiple divisions in the same season/team
    print("\n[1] Finding duplicate entries...")
    cursor.execute("""
        SELECT id, season_id, team_name, COUNT(DISTINCT division_id) as div_count
        FROM players
        WHERE division_level IS NOT NULL
        GROUP BY id, season_id, team_name
        HAVING div_count > 1
    """)

    duplicates = cursor.fetchall()
    print(f"✓ Found {len(duplicates)} cases of players in multiple divisions per season")

    if duplicates:
        print("\nExamples:")
        for player_id, season_id, team_name, div_count in duplicates[:5]:
            cursor.execute("SELECT name FROM seasons WHERE id = ?", (season_id,))
            season_name = cursor.fetchone()[0]
            cursor.execute("SELECT first_name, last_name FROM players WHERE id = ? LIMIT 1", (player_id,))
            fname, lname = cursor.fetchone()
            print(f"  {fname} {lname}: Season {season_name}, Team {team_name}, {div_count} divisions")

    # Step 2: For each player/season/team with multiple divisions, keep only the highest division level
    print("\n[2] Removing duplicate divisions (keeping highest level: B > C > D > E)...")

    division_priority = {'B': 1, 'C': 2, 'D': 3, 'E': 4}

    removed_count = 0
    for player_id, season_id, team_name, div_count in duplicates:
        # Get all division_ids for this player/season/team, ordered by priority
        cursor.execute("""
            SELECT division_id, division_level
            FROM players
            WHERE id = ? AND season_id = ? AND team_name = ?
            ORDER BY division_level
        """, (player_id, season_id, team_name))

        divisions = cursor.fetchall()
        # Keep the first (highest priority), delete the rest
        if len(divisions) > 1:
            for div_id, _ in divisions[1:]:
                cursor.execute("DELETE FROM players WHERE id = ? AND season_id = ? AND division_id = ?",
                             (player_id, season_id, div_id))
                removed_count += 1

    conn.commit()
    print(f"✓ Removed {removed_count} duplicate player rows")

    # Step 3: Recalculate primary team with corrected data
    print("\n[3] Recalculating primary team with corrected stats...")

    cursor.execute("SELECT DISTINCT id FROM players WHERE division_level IS NOT NULL")
    player_ids = [row[0] for row in cursor.fetchall()]

    recalc_count = 0
    for player_id in player_ids:
        # Find the team this player played the most games for
        cursor.execute("""
            SELECT p.team_name, SUM(COALESCE(ps.gp, 0)) as total_games
            FROM players p
            LEFT JOIN player_stats ps ON p.id = ps.player_id AND p.season_id = ps.season_id
            WHERE p.id = ? AND p.division_level IS NOT NULL
            GROUP BY p.team_name
            ORDER BY total_games DESC
            LIMIT 1
        """, (player_id,))

        result = cursor.fetchone()
        if result:
            primary_team, total_games = result
            cursor.execute(
                "UPDATE players SET primary_team_name = ? WHERE id = ?",
                (primary_team, player_id)
            )
            recalc_count += 1

    conn.commit()
    print(f"✓ Recalculated primary team for {recalc_count} players")

    # Step 4: Verify the fix
    print("\n[4] Verification - checking player 12390...")
    cursor.execute("""
        SELECT
            p.team_name,
            COUNT(DISTINCT p.season_id) as seasons,
            SUM(COALESCE(ps.gp, 0)) as total_games
        FROM players p
        LEFT JOIN player_stats ps ON p.id = ps.player_id AND p.season_id = ps.season_id
        WHERE p.id = 12390 AND p.division_level IS NOT NULL
        GROUP BY p.team_name
        ORDER BY total_games DESC
    """)

    print("\nPlayer 12390 stats (corrected):")
    print(f"{'Team':<25} {'Seasons':<10} {'Games':<10}")
    print("-" * 45)

    total_games = 0
    for team_name, seasons, games in cursor.fetchall():
        games_int = int(games) if games else 0
        total_games += games_int
        print(f"{team_name:<25} {seasons:<10} {games_int:<10}")

    print(f"\nTotal games across all teams: {total_games}")

    conn.close()

    print("\n" + "="*80)
    print("✓ DUPLICATE STATS FIXED!")
    print("="*80)
    print("\nPlayers no longer counted multiple times for playing in multiple")
    print("divisions within the same season. Primary teams recalculated correctly.")
    print("="*80 + "\n")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
