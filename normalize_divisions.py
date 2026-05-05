#!/usr/bin/env python3
"""
Normalize divisions to B, C, D levels and add season type (Regular/Playoffs flag)
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "skahl_historical.db"

print("\n" + "="*80)
print("NORMALIZING DIVISIONS AND ADDING SEASON TYPE")
print("="*80)

try:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Step 1: Get all unique division names
    print("\n[1] Analyzing division names...")
    cursor.execute("SELECT DISTINCT name FROM divisions ORDER BY name")
    all_divisions = [row[0] for row in cursor.fetchall()]
    print(f"✓ Found {len(all_divisions)} unique division names")
    print("\nDivision names:")
    for i, div_name in enumerate(all_divisions, 1):
        print(f"  {i}. {div_name}")

    # Step 2: Create division mapping - extract letter after "Division" or "Division-"
    print("\n[2] Creating division level mapping (extracting B/C/D/E from Division names)...")

    # Define divisions to exclude
    excluded_divisions = {
        'Division-LADA',
        'Division-Open35',
        'Division-Open40'
    }

    # Define specific divisions to map to E
    novice_to_e = {
        'Division-Novice 1',
        'Division-Novice 2'
    }

    division_mapping = {}
    skipped = []

    for div_name in all_divisions:
        # Only process divisions that contain the word "Division"
        if 'division' not in div_name.lower():
            skipped.append(div_name)
            continue

        # Check if this division should be excluded
        if div_name in excluded_divisions:
            skipped.append(f"{div_name} (excluded)")
            continue

        # Check if this division should be mapped to E
        if div_name in novice_to_e:
            division_mapping[div_name] = 'E'
            continue

        # Extract the division letter (B, C, D, or E)
        div_upper = div_name.upper()
        level = None

        # Look for Division-X, Division X, or just Division followed by letter
        # Extract the first letter after "DIVISION" that is B, C, D, or E
        idx = div_upper.find('DIVISION')
        if idx != -1:
            # Start searching after "DIVISION"
            search_str = div_upper[idx + 8:]  # Skip past "DIVISION"
            for char in search_str:
                if char in ['B', 'C', 'D', 'E']:
                    level = char
                    break

        if level:
            division_mapping[div_name] = level
        else:
            skipped.append(div_name)

    print(f"\nMapped divisions ({len(division_mapping)}):")
    for div_name, level in sorted(division_mapping.items()):
        print(f"  {div_name:<50} → Division {level}")

    if skipped:
        print(f"\nSkipped divisions (no recognized Division letter) ({len(skipped)}):")
        for div_name in sorted(skipped):
            print(f"  {div_name}")

    # Step 3: Add new columns if they don't exist
    print("\n[3] Adding new columns to players table...")
    try:
        cursor.execute("ALTER TABLE players ADD COLUMN division_level TEXT")
        print("✓ Added division_level column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("✓ division_level column already exists")
        else:
            raise

    try:
        cursor.execute("ALTER TABLE players ADD COLUMN season_type TEXT")
        print("✓ Added season_type column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("✓ season_type column already exists")
        else:
            raise

    # Step 4: Update player records with division level and season type
    print("\n[4] Updating player records...")

    updated_count = 0
    for div_name, level in division_mapping.items():
        # Determine season type based on division name
        season_type = "Playoffs" if "playoff" in div_name.lower() else "Regular Season"

        cursor.execute(
            "UPDATE players SET division_level = ?, season_type = ? WHERE division_id IN (SELECT id FROM divisions WHERE name = ?)",
            (level, season_type, div_name)
        )
        updated_count += cursor.rowcount

    conn.commit()
    print(f"✓ Updated {updated_count} player records")

    # Step 5: Verify the update
    print("\n[5] Verification...")

    cursor.execute("""
        SELECT division_level, season_type, COUNT(*) as count
        FROM players
        GROUP BY division_level, season_type
        ORDER BY division_level, season_type
    """)

    print("\nDistribution of players by division level and season type:")
    print(f"{'Level':<10} {'Season Type':<20} {'Count':>10}")
    print("-" * 40)
    for level, stype, count in cursor.fetchall():
        print(f"{level:<10} {stype:<20} {count:>10}")

    # Step 6: Recalculate primary team with normalized data (only from valid divisions B/C/D/E)
    print("\n[6] Recalculating primary team (only from valid Division B/C/D/E)...")

    cursor.execute("SELECT DISTINCT id FROM players WHERE division_level IS NOT NULL")
    player_ids = [row[0] for row in cursor.fetchall()]
    print(f"   Processing {len(player_ids)} players with valid divisions...")

    recalc_count = 0
    for player_id in player_ids:
        # Find the team this player played the most games for (only from valid divisions)
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

    # Step 7: Show examples
    print("\n[7] Sample results with normalized data:")
    cursor.execute("""
        SELECT
            p.first_name || ' ' || p.last_name as name,
            p.primary_team_name,
            COUNT(DISTINCT p.season_id) as seasons,
            SUM(COALESCE(ps.gp, 0)) as total_gp,
            SUM(COALESCE(ps.goals, 0)) as total_goals,
            SUM(COALESCE(ps.assists, 0)) as total_assists,
            SUM(COALESCE(ps.points, 0)) as total_points
        FROM players p
        LEFT JOIN player_stats ps ON p.id = ps.player_id AND p.season_id = ps.season_id
        GROUP BY p.id
        ORDER BY total_gp DESC
        LIMIT 10
    """)

    print(f"\n{'Player':<25} {'Primary Team':<25} {'Seasons':<8} {'GP':<6} {'Goals':<7} {'Assists':<8} {'Points':<7}")
    print("-" * 90)
    for name, team, seasons, gp, goals, assists, points in cursor.fetchall():
        gp_str = str(int(gp)) if gp else "0"
        goals_str = str(int(goals)) if goals else "0"
        assists_str = str(int(assists)) if assists else "0"
        points_str = str(int(points)) if points else "0"
        print(f"{name:<25} {team:<25} {seasons:<8} {gp_str:<6} {goals_str:<7} {assists_str:<8} {points_str:<7}")

    conn.close()

    print("\n" + "="*80)
    print("✓ NORMALIZATION COMPLETE!")
    print("="*80)
    print("\nNow your queries will:")
    print("  • Count only Regular Season games (not playoffs)")
    print("  • Normalize divisions to B, C, D levels")
    print("  • Calculate primary teams based on Regular Season only")
    print("\n" + "="*80 + "\n")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
