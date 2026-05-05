#!/usr/bin/env python3
"""
Add Primary Division Level metadata to players
Determines each player's primary division (B, C, D, or E) based on most games played
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "skahl_historical.db"

print("\n" + "="*80)
print("ADDING PRIMARY DIVISION LEVEL METADATA")
print("="*80)

try:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Step 1: Add primary_division_level column if it doesn't exist
    print("\n[1] Creating primary_division_level column...")
    try:
        cursor.execute("ALTER TABLE players ADD COLUMN primary_division_level TEXT")
        print("✓ Column added")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("✓ Column already exists, updating...")
        else:
            raise

    # Step 2: Calculate primary division for each player
    print("[2] Calculating primary division level for each player...")

    cursor.execute("SELECT DISTINCT id FROM players WHERE division_level IS NOT NULL")
    player_ids = [row[0] for row in cursor.fetchall()]
    print(f"   Processing {len(player_ids)} unique players...")

    updated_count = 0

    for player_id in player_ids:
        # Find the division level this player played the most games in
        cursor.execute("""
            SELECT division_level, SUM(COALESCE(ps.gp, 0)) as total_games
            FROM players p
            LEFT JOIN player_stats ps ON p.id = ps.player_id AND p.season_id = ps.season_id
            WHERE p.id = ? AND p.division_level IS NOT NULL
            GROUP BY division_level
            ORDER BY total_games DESC
            LIMIT 1
        """, (player_id,))

        result = cursor.fetchone()
        if result:
            primary_div, total_games = result
            cursor.execute(
                "UPDATE players SET primary_division_level = ? WHERE id = ?",
                (primary_div, player_id)
            )
            updated_count += 1

    conn.commit()
    print(f"✓ Updated {updated_count} players with primary division")

    # Step 3: Verify the results
    print("\n[3] Verifying results...")

    cursor.execute("""
        SELECT COUNT(DISTINCT id) FROM players WHERE primary_division_level IS NOT NULL
    """)
    players_with_div = cursor.fetchone()[0]
    print(f"✓ {players_with_div} players now have primary division assigned")

    # Distribution of players by primary division
    print("\n[4] Distribution of players by primary division:")
    cursor.execute("""
        SELECT primary_division_level, COUNT(DISTINCT id) as player_count
        FROM players
        WHERE primary_division_level IS NOT NULL
        GROUP BY primary_division_level
        ORDER BY primary_division_level
    """)

    print(f"{'Division':<10} {'Player Count':>15}")
    print("-" * 25)
    for div_level, count in cursor.fetchall():
        print(f"{div_level:<10} {count:>15}")

    # Show some examples
    print("\n[5] Sample of players with primary divisions:")
    print(f"{'Player':<30} {'Primary Team':<25} {'Primary Div':<12} {'Total GP':>8}")
    print("-" * 80)

    cursor.execute("""
        SELECT
            p.first_name || ' ' || p.last_name as name,
            p.primary_team_name,
            p.primary_division_level,
            SUM(COALESCE(ps.gp, 0)) as total_gp
        FROM players p
        LEFT JOIN player_stats ps ON p.id = ps.player_id AND p.season_id = ps.season_id
        WHERE p.division_level IS NOT NULL
        GROUP BY p.id
        ORDER BY total_gp DESC
        LIMIT 15
    """)

    for name, team, div, gp in cursor.fetchall():
        gp_str = str(int(gp)) if gp else "0"
        print(f"{name:<30} {team:<25} {div:<12} {gp_str:>8}")

    conn.close()

    print("\n" + "="*80)
    print("✓ PRIMARY DIVISION LEVEL ADDED SUCCESSFULLY")
    print("="*80)
    print("\nNow you can query by division level:")
    print("""
    -- Top scorers in Division B
    SELECT first_name, last_name, primary_team_name
    FROM players
    WHERE primary_division_level = 'B'
    GROUP BY id
    ORDER BY (SELECT SUM(points) FROM player_stats
              WHERE player_id = players.id) DESC
    LIMIT 10;
    """)
    print("="*80 + "\n")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
