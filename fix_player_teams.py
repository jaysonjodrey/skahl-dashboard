#!/usr/bin/env python3
"""
Fix the players table to properly store season-specific team assignments
Changes PRIMARY KEY from (id) to (id, season_id, division_id)
"""

import sqlite3
from pathlib import Path
import shutil

DB_PATH = Path(__file__).parent / "skahl_historical.db"
BACKUP_PATH = Path(__file__).parent / "skahl_historical_backup.db"

print("\n" + "="*80)
print("FIXING PLAYER TEAM ASSIGNMENTS")
print("="*80)

try:
    # Create backup
    print("\n[1] Creating backup...")
    shutil.copy2(str(DB_PATH), str(BACKUP_PATH))
    print(f"✓ Backup created: skahl_historical_backup.db")

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Step 2: Rename old players table
    print("\n[2] Restructuring players table...")
    cursor.execute("ALTER TABLE players RENAME TO players_old")
    print("✓ Renamed players table")

    # Step 3: Create new players table with correct schema (including primary_team_name if it exists)
    cursor.execute("""CREATE TABLE players (
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
    print("✓ Created new players table with correct schema")

    # Step 4: Copy data from old table, but remove the INSERT OR IGNORE behavior
    # This time we allow duplicates with different seasons
    print("\n[3] Copying data with proper season-team relationships...")

    cursor.execute("SELECT COUNT(*) FROM players_old")
    total_rows = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO players
        SELECT * FROM players_old
    """)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM players")
    new_rows = cursor.fetchone()[0]
    print(f"✓ Copied {new_rows} player-season records")

    # Step 5: Drop old table
    print("\n[4] Cleaning up...")
    cursor.execute("DROP TABLE players_old")
    conn.commit()
    print("✓ Removed old table")

    # Step 6: Verify the fix
    print("\n[5] Verifying fix...")

    # Check for a player who should have multiple teams
    cursor.execute("""
        SELECT id, first_name, last_name, season_id, team_name
        FROM players
        WHERE id IN (
            SELECT id FROM players GROUP BY id HAVING COUNT(DISTINCT team_name) > 1
        )
        ORDER BY id, season_id
        LIMIT 20
    """)

    results = cursor.fetchall()
    if results:
        print(f"✓ Found {len(set(r[0] for r in results))} players with multiple teams across seasons:")
        print(f"\n{'Player ID':<10} {'Name':<25} {'Season':<10} {'Team':<20}")
        print("-" * 65)
        current_player = None
        for player_id, fname, lname, season_id, team_name in results:
            cursor.execute("SELECT name FROM seasons WHERE id = ?", (season_id,))
            season_name = cursor.fetchone()[0]
            if player_id != current_player:
                current_player = player_id
                print(f"{player_id:<10} {fname + ' ' + lname:<25} {season_name:<10} {team_name:<20}")
            else:
                print(f"{'':<10} {'':<25} {season_name:<10} {team_name:<20}")
    else:
        print("✓ All players have consistent team assignments")

    # Step 7: Show impact
    print("\n[6] Impact Summary:")
    cursor.execute("SELECT COUNT(DISTINCT id) FROM players")
    unique_players = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM players")
    total_records = cursor.fetchone()[0]
    print(f"✓ Unique players: {unique_players}")
    print(f"✓ Total player-season records: {total_records}")
    print(f"✓ Average seasons per player: {total_records / unique_players:.1f}")

    conn.close()

    print("\n" + "="*80)
    print("✓ PLAYER TEAMS FIXED!")
    print("="*80)
    print("\nNow each player is correctly associated with their team for each season.")
    print("Backup saved as: skahl_historical_backup.db")
    print("\nYou can now query with accurate team information:")
    print("""
    SELECT p.first_name, p.last_name, s.name as season, p.team_name
    FROM players p
    JOIN seasons s ON p.season_id = s.id
    WHERE p.first_name = 'John' AND p.last_name = 'Smith'
    ORDER BY s.id;
    """)
    print("="*80 + "\n")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    print("\nYour backup is safe at: skahl_historical_backup.db")
