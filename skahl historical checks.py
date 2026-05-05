import sqlite3
conn = sqlite3.connect("skahl_historical.db")
cursor = conn.cursor()

# Check for players with multiple seasons
cursor.execute("""
    SELECT id, first_name, last_name, COUNT(DISTINCT season_id) as num_seasons
    FROM players
    GROUP BY id
    HAVING num_seasons > 1
    ORDER BY num_seasons DESC
    LIMIT 10
""")

print("Players appearing in multiple seasons:")
for player_id, fname, lname, num_seasons in cursor.fetchall():
    print(f"  {fname} {lname}: {num_seasons} seasons")

# Check for team switches
cursor.execute("""
    SELECT first_name || ' ' || last_name, COUNT(DISTINCT team_name) as num_teams
    FROM players
    GROUP BY id
    HAVING COUNT(DISTINCT team_name) > 1
    ORDER BY num_teams DESC
    LIMIT 10
""")

print("\nPlayers who switched teams:")
for name, num_teams in cursor.fetchall():
    print(f"  {name}: {num_teams} different teams")

conn.close()