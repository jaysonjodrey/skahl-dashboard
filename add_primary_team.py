#!/usr/bin/env python3
"""
Add Primary Team metadata to players
Determines each player's primary team based on total games played across all seasons
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "skahl_historical.db"

print("\n" + "="*80)
print("ADDING PRIMARY TEAM METADATA")
print("="*80)

try:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Step 1: Add primary_team_name column if it doesn't exist
    print("\n[1] Creating primary_team_name column...")
    try:
        cursor.execute("ALTER TABLE players ADD COLUMN primary_team_name TEXT")
        print("✓ Column added")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("✓ Column already exists, updating...")
        else:
            raise

    # Step 2: Calculate primary team for each player
    print("[2] Calculating primary team for each player...")

    cursor.execute("""
        SELECT DISTINCT id FROM players
    """)

    player_ids = [row[0] for row in cursor.fetchall()]
    print(f"   Processing {len(player_ids)} unique players...")

    updated_count = 0

    for player_id in player_ids:
        # Find the team this player played the most games for
        cursor.execute("""
            SELECT team_name, SUM(COALESCE(gp, 0)) as total_games
            FROM players p
            LEFT JOIN player_stats ps ON p.id = ps.player_id
            WHERE p.id = ?
            GROUP BY team_name
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
            updated_count += 1

    conn.commit()
    print(f"✓ Updated {updated_count} players with primary team")

    # Step 3: Verify the results
    print("\n[3] Verifying results...")

    cursor.execute("""
        SELECT COUNT(DISTINCT id) FROM players WHERE primary_team_name IS NOT NULL
    """)
    players_with_team = cursor.fetchone()[0]
    print(f"✓ {players_with_team} players now have primary team assigned")

    # Show some examples
    print("\n[4] Sample of players with primary teams:")
    print(f"{'Player':<30} {'Primary Team':<30} {'Total GP':>8}")
    print("-" * 70)

    cursor.execute("""
        SELECT
            p.first_name || ' ' || p.last_name as name,
            p.primary_team_name,
            SUM(COALESCE(ps.gp, 0)) as total_gp
        FROM players p
        LEFT JOIN player_stats ps ON p.id = ps.player_id
        WHERE p.primary_team_name IS NOT NULL
        GROUP BY p.id
        ORDER BY total_gp DESC
        LIMIT 10
    """)

    for name, primary_team, total_gp in cursor.fetchall():
        print(f"{name:<30} {primary_team:<30} {total_gp:>8}")

    conn.close()

    print("\n" + "="*80)
    print("✓ PRIMARY TEAM METADATA ADDED SUCCESSFULLY")
    print("="*80)
    print("\nYou can now query by primary team:")
    print("""
    SELECT first_name, last_name, primary_team_name
    FROM players
    WHERE primary_team_name = 'Cascadiens'
    GROUP BY id
    ORDER BY last_name;
    """)
    print("="*80 + "\n")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
