import sqlite3, json, sys, os

WORKSPACE = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
DB  = os.path.join(WORKSPACE, 'skahl_historical.db')
OUT = os.path.join(WORKSPACE, 'dashboard_data.json')

conn = sqlite3.connect(DB)
c = conn.cursor()

# ── Skater CTEs ────────────────────────────────────────────────────────────────
BASE_CTE = """
WITH deduped_ps AS (
    SELECT DISTINCT player_id, season_id, gp, goals, assists, points FROM player_stats
),
agg_stats AS (
    SELECT player_id, season_id,
           SUM(gp) AS gp, SUM(goals) AS goals, SUM(assists) AS assists, SUM(points) AS points
    FROM deduped_ps GROUP BY player_id, season_id
),
valid_rs AS (
    SELECT DISTINCT id AS player_id, season_id
    FROM players WHERE division_level IS NOT NULL AND season_type = 'Regular Season'
),
career AS (
    SELECT vs.player_id,
           COUNT(DISTINCT vs.season_id) AS seasons,
           SUM(a.gp) AS gp, SUM(a.goals) AS goals, SUM(a.assists) AS assists, SUM(a.points) AS points
    FROM valid_rs vs JOIN agg_stats a ON vs.player_id=a.player_id AND vs.season_id=a.season_id
    GROUP BY vs.player_id
),
player_meta AS (
    SELECT id, first_name, last_name, primary_team_name, primary_division_level,
           ROW_NUMBER() OVER (PARTITION BY id ORDER BY rowid) AS rn
    FROM players WHERE division_level IS NOT NULL
)
"""

# ── Goalie CTE (reusable prefix) ───────────────────────────────────────────────
GOALIE_CTE = """
WITH goalie_agg AS (
    SELECT gs.player_id,
           COUNT(DISTINCT gs.season_id) AS seasons,
           SUM(gs.gp)  AS gp,
           SUM(gs.w)   AS wins,
           SUM(gs.l)   AS losses,
           SUM(gs.t)   AS ties,
           SUM(gs.otl) AS otl,
           SUM(gs.ga)  AS ga,
           SUM(gs.sa)  AS sa,
           SUM(gs.sv)  AS sv,
           SUM(gs.so)  AS shutouts,
           SUM(gs.pim) AS pim
    FROM goalie_stats gs
    JOIN divisions d ON d.id = gs.division_id
    GROUP BY gs.player_id
),
pmeta AS (
    SELECT id, first_name, last_name, primary_team_name, primary_division_level,
           ROW_NUMBER() OVER (PARTITION BY id ORDER BY rowid) AS rn
    FROM players WHERE division_level IS NOT NULL
)
"""

# League summary
c.execute(BASE_CTE + """
SELECT
  (SELECT COUNT(DISTINCT id) FROM player_meta WHERE rn=1) as unique_players,
  (SELECT COUNT(DISTINCT season_id) FROM valid_rs) as rs_seasons,
  (SELECT SUM(gp) FROM career) as total_gp,
  (SELECT SUM(goals) FROM career) as total_goals,
  (SELECT SUM(points) FROM career) as total_points,
  (SELECT COUNT(DISTINCT team_name) FROM players WHERE division_level IS NOT NULL) as unique_teams,
  (SELECT COALESCE(SUM(sv),0) FROM goalie_stats) as total_saves
""")
row = c.fetchone()
summary = dict(zip(['unique_players','rs_seasons','total_gp','total_goals','total_points','unique_teams','total_saves'], row))

# All-time scorers (RS) — no limit
c.execute(BASE_CTE + """
SELECT pm.first_name || ' ' || pm.last_name, pm.primary_team_name, pm.primary_division_level,
       c.seasons, c.gp, c.goals, c.assists, c.points,
       ROUND(CAST(c.points AS FLOAT)/NULLIF(c.gp,0),2) as ppg
FROM career c JOIN player_meta pm ON c.player_id=pm.id AND pm.rn=1
WHERE c.gp >= 5
ORDER BY c.points DESC
""")
top_scorers = [dict(zip(['name','team','div','seasons','gp','goals','assists','points','ppg'], r)) for r in c.fetchall()]

# Top 50 goal scorers
c.execute(BASE_CTE + """
SELECT pm.first_name || ' ' || pm.last_name, pm.primary_team_name, pm.primary_division_level,
       c.seasons, c.gp, c.goals, c.assists, c.points,
       ROUND(CAST(c.points AS FLOAT)/NULLIF(c.gp,0),2) as ppg
FROM career c JOIN player_meta pm ON c.player_id=pm.id AND pm.rn=1
WHERE c.gp >= 5
ORDER BY c.goals DESC LIMIT 50
""")
top_goals = [dict(zip(['name','team','div','seasons','gp','goals','assists','points','ppg'], r)) for r in c.fetchall()]

# Top 50 assist leaders
c.execute(BASE_CTE + """
SELECT pm.first_name || ' ' || pm.last_name, pm.primary_team_name, pm.primary_division_level,
       c.seasons, c.gp, c.goals, c.assists, c.points,
       ROUND(CAST(c.points AS FLOAT)/NULLIF(c.gp,0),2) as ppg
FROM career c JOIN player_meta pm ON c.player_id=pm.id AND pm.rn=1
WHERE c.gp >= 5
ORDER BY c.assists DESC LIMIT 50
""")
top_assists = [dict(zip(['name','team','div','seasons','gp','goals','assists','points','ppg'], r)) for r in c.fetchall()]

# Top 50 by games played
c.execute(BASE_CTE + """
SELECT pm.first_name || ' ' || pm.last_name, pm.primary_team_name, pm.primary_division_level,
       c.seasons, c.gp, c.goals, c.assists, c.points,
       ROUND(CAST(c.points AS FLOAT)/NULLIF(c.gp,0),2) as ppg
FROM career c JOIN player_meta pm ON c.player_id=pm.id AND pm.rn=1
WHERE c.gp >= 5
ORDER BY c.gp DESC LIMIT 50
""")
top_gp = [dict(zip(['name','team','div','seasons','gp','goals','assists','points','ppg'], r)) for r in c.fetchall()]

# Division leaders — team shown is the one they played most for WITHIN that specific division
div_leaders = {}
for div in ['B','C','D','E']:
    c.execute(BASE_CTE + f"""
    , div_best_team AS (
        SELECT p.id AS player_id, p.team_name,
               ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY SUM(COALESCE(a2.gp,0)) DESC) AS rn
        FROM players p
        LEFT JOIN agg_stats a2 ON p.id = a2.player_id AND p.season_id = a2.season_id
        WHERE p.division_level = '{div}' AND p.season_type = 'Regular Season'
        GROUP BY p.id, p.team_name
    )
    SELECT pm.first_name || ' ' || pm.last_name, dbt.team_name,
           c.seasons, c.gp, c.goals, c.assists, c.points,
           ROUND(CAST(c.points AS FLOAT)/NULLIF(c.gp,0),2)
    FROM career c
    JOIN player_meta pm ON c.player_id = pm.id AND pm.rn = 1
    JOIN div_best_team dbt ON c.player_id = dbt.player_id AND dbt.rn = 1
    WHERE pm.primary_division_level = '{div}' AND c.gp >= 5
    ORDER BY c.points DESC LIMIT 30
    """)
    div_leaders[div] = [dict(zip(['name','team','seasons','gp','goals','assists','points','ppg'], r)) for r in c.fetchall()]

# Teams
c.execute("""
    SELECT team_name, division_level, COUNT(DISTINCT season_id) as seasons,
           COUNT(DISTINCT id) as total_players
    FROM players
    WHERE division_level IS NOT NULL AND season_type='Regular Season'
    GROUP BY team_name, division_level
    ORDER BY seasons DESC, total_players DESC
    LIMIT 60
""")
teams = [dict(zip(['name','div','seasons','players'], r)) for r in c.fetchall()]

# Season-by-season totals
c.execute("""
    SELECT s.name, s.id,
           COUNT(DISTINCT CASE WHEN p.division_level IS NOT NULL AND p.season_type='Regular Season' THEN p.id END) as players,
           SUM(CASE WHEN p.division_level IS NOT NULL AND p.season_type='Regular Season' THEN ps2.gp ELSE 0 END) as total_gp,
           SUM(CASE WHEN p.division_level IS NOT NULL AND p.season_type='Regular Season' THEN ps2.goals ELSE 0 END) as total_goals
    FROM seasons s
    LEFT JOIN players p ON p.season_id = s.id
    LEFT JOIN player_stats ps2 ON ps2.player_id = p.id AND ps2.season_id = p.season_id
    GROUP BY s.id
    ORDER BY s.id ASC
""")
seasons_data = [dict(zip(['name','id','players','total_gp','total_goals'], r)) for r in c.fetchall()]
seasons_data = [s for s in seasons_data if s['players'] and s['players'] > 0]

# Jayson's career
c.execute("""
    WITH deduped_ps AS (SELECT DISTINCT player_id, season_id, gp, goals, assists, points FROM player_stats),
    agg AS (SELECT player_id, season_id, SUM(gp) as gp, SUM(goals) as goals, SUM(assists) as assists, SUM(points) as points
            FROM deduped_ps GROUP BY player_id, season_id)
    SELECT s.name, p.team_name, p.division_level, p.season_type,
           a.gp, a.goals, a.assists, a.points
    FROM players p
    JOIN seasons s ON s.id = p.season_id
    JOIN agg a ON a.player_id = p.id AND a.season_id = p.season_id
    WHERE LOWER(p.first_name)='jayson' AND LOWER(p.last_name)='jodrey'
      AND p.division_level IS NOT NULL
    GROUP BY p.id, p.season_id
    ORDER BY p.season_id
""")
jayson = [dict(zip(['season','team','div','type','gp','goals','assists','points'], r)) for r in c.fetchall()]

# ── GOALIE LEADERBOARDS ────────────────────────────────────────────────────────

# Top goalies by wins (min 10 GP)
c.execute(GOALIE_CTE + """
SELECT pm.first_name || ' ' || pm.last_name, pm.primary_team_name, pm.primary_division_level,
       ga.seasons, ga.gp, ga.wins, ga.losses, ga.ties, ga.otl, ga.shutouts,
       ROUND(CAST(ga.sv AS FLOAT)/NULLIF(ga.sa,0), 3) as svp,
       ROUND(CAST(ga.ga AS FLOAT)/NULLIF(ga.gp,0), 2) as gaa
FROM goalie_agg ga
JOIN pmeta pm ON ga.player_id = pm.id AND pm.rn = 1
WHERE ga.gp >= 10
ORDER BY ga.wins DESC LIMIT 50
""")
goalie_wins = [dict(zip(['name','team','div','seasons','gp','wins','losses','ties','otl','shutouts','svp','gaa'], r)) for r in c.fetchall()]

# Top goalies by GAA (min 20 GP, lower is better)
c.execute(GOALIE_CTE + """
SELECT pm.first_name || ' ' || pm.last_name, pm.primary_team_name, pm.primary_division_level,
       ga.seasons, ga.gp, ga.wins, ga.losses, ga.shutouts,
       ROUND(CAST(ga.sv AS FLOAT)/NULLIF(ga.sa,0), 3) as svp,
       ROUND(CAST(ga.ga AS FLOAT)/NULLIF(ga.gp,0), 2) as gaa
FROM goalie_agg ga
JOIN pmeta pm ON ga.player_id = pm.id AND pm.rn = 1
WHERE ga.gp >= 20 AND ga.ga > 0
ORDER BY gaa ASC LIMIT 50
""")
goalie_gaa = [dict(zip(['name','team','div','seasons','gp','wins','losses','shutouts','svp','gaa'], r)) for r in c.fetchall()]

# Top goalies by SVP (min 20 GP)
c.execute(GOALIE_CTE + """
SELECT pm.first_name || ' ' || pm.last_name, pm.primary_team_name, pm.primary_division_level,
       ga.seasons, ga.gp, ga.wins, ga.losses, ga.shutouts,
       ROUND(CAST(ga.sv AS FLOAT)/NULLIF(ga.sa,0), 3) as svp,
       ROUND(CAST(ga.ga AS FLOAT)/NULLIF(ga.gp,0), 2) as gaa
FROM goalie_agg ga
JOIN pmeta pm ON ga.player_id = pm.id AND pm.rn = 1
WHERE ga.gp >= 20 AND ga.sa > 0
ORDER BY svp DESC LIMIT 50
""")
goalie_svp = [dict(zip(['name','team','div','seasons','gp','wins','losses','shutouts','svp','gaa'], r)) for r in c.fetchall()]

# Top goalies by shutouts (min 5 GP)
c.execute(GOALIE_CTE + """
SELECT pm.first_name || ' ' || pm.last_name, pm.primary_team_name, pm.primary_division_level,
       ga.seasons, ga.gp, ga.wins, ga.losses, ga.shutouts,
       ROUND(CAST(ga.sv AS FLOAT)/NULLIF(ga.sa,0), 3) as svp,
       ROUND(CAST(ga.ga AS FLOAT)/NULLIF(ga.gp,0), 2) as gaa
FROM goalie_agg ga
JOIN pmeta pm ON ga.player_id = pm.id AND pm.rn = 1
WHERE ga.gp >= 5 AND ga.shutouts > 0
ORDER BY ga.shutouts DESC LIMIT 50
""")
goalie_shutouts = [dict(zip(['name','team','div','seasons','gp','wins','losses','shutouts','svp','gaa'], r)) for r in c.fetchall()]

# Top goalies by games played
c.execute(GOALIE_CTE + """
SELECT pm.first_name || ' ' || pm.last_name, pm.primary_team_name, pm.primary_division_level,
       ga.seasons, ga.gp, ga.wins, ga.losses, ga.shutouts,
       ROUND(CAST(ga.sv AS FLOAT)/NULLIF(ga.sa,0), 3) as svp,
       ROUND(CAST(ga.ga AS FLOAT)/NULLIF(ga.gp,0), 2) as gaa
FROM goalie_agg ga
JOIN pmeta pm ON ga.player_id = pm.id AND pm.rn = 1
ORDER BY ga.gp DESC LIMIT 50
""")
goalie_gp = [dict(zip(['name','team','div','seasons','gp','wins','losses','shutouts','svp','gaa'], r)) for r in c.fetchall()]

# Goalie division leaders
goalie_div_leaders = {}
for div in ['B','C','D','E']:
    c.execute(f"""
    WITH goalie_agg AS (
        SELECT gs.player_id,
               COUNT(DISTINCT gs.season_id) AS seasons,
               SUM(gs.gp) AS gp, SUM(gs.w) AS wins, SUM(gs.l) AS losses,
               SUM(gs.so) AS shutouts, SUM(gs.ga) AS ga, SUM(gs.sa) AS sa, SUM(gs.sv) AS sv
        FROM goalie_stats gs
        JOIN divisions d ON d.id = gs.division_id
        GROUP BY gs.player_id
    ),
    pmeta AS (
        SELECT id, first_name, last_name, primary_team_name, primary_division_level,
               ROW_NUMBER() OVER (PARTITION BY id ORDER BY rowid) AS rn
        FROM players WHERE division_level IS NOT NULL
    )
    SELECT pm.first_name || ' ' || pm.last_name, pm.primary_team_name,
           ga.seasons, ga.gp, ga.wins, ga.losses, ga.shutouts,
           ROUND(CAST(ga.sv AS FLOAT)/NULLIF(ga.sa,0), 3) as svp,
           ROUND(CAST(ga.ga AS FLOAT)/NULLIF(ga.gp,0), 2) as gaa
    FROM goalie_agg ga
    JOIN pmeta pm ON ga.player_id = pm.id AND pm.rn = 1
    WHERE pm.primary_division_level = '{div}' AND ga.gp >= 5
    ORDER BY ga.wins DESC LIMIT 25
    """)
    goalie_div_leaders[div] = [dict(zip(['name','team','seasons','gp','wins','losses','shutouts','svp','gaa'], r)) for r in c.fetchall()]

# ── Scatter data ─────────────────────────────────────────────────────────────
# Skaters: per-season (gp>=15, SKAHL RS) + raw counts for filter-aware tooltip
c.execute("""
    SELECT p.first_name||' '||p.last_name,
           p.primary_division_level,
           s.id,
           ps.gp,
           ROUND(CAST(ps.goals   AS FLOAT)/ps.gp, 3),
           ROUND(CAST(ps.assists AS FLOAT)/ps.gp, 3),
           ps.goals + ps.assists,
           ps.goals,
           ps.assists
    FROM player_stats ps
    JOIN players p  ON p.id  = ps.player_id
    JOIN seasons s  ON s.id  = ps.season_id
    WHERE ps.gp >= 15 AND p.division_level IS NOT NULL
      AND p.season_type = 'Regular Season'
      AND LOWER(p.first_name||' '||p.last_name) != 'empty net'
    GROUP BY ps.player_id, ps.season_id
    ORDER BY ps.goals + ps.assists DESC
""")
scatter_skaters = [
    dict(zip(['n','dv','sid','gp','gpg','apg','pt','g','a'], r))
    for r in c.fetchall()
]

# Goalies: per-season (gp>=3) + raw counts for filter-aware tooltip
c.execute("""
    SELECT p.first_name||' '||p.last_name,
           p.primary_division_level,
           s.id,
           gs.gp, gs.w,
           ROUND(gs.svp, 4),
           ROUND(gs.gaa, 3),
           gs.sv, gs.sa, gs.ga
    FROM goalie_stats gs
    JOIN players p  ON p.id  = gs.player_id
    JOIN seasons s  ON s.id  = gs.season_id
    WHERE gs.gp >= 3
      AND LOWER(p.first_name||' '||p.last_name) != 'empty net'
    GROUP BY gs.player_id, gs.season_id
    ORDER BY gs.svp DESC
""")
scatter_goalies = [
    dict(zip(['n','dv','sid','gp','w','svp','gaa','sv','sa','ga'], r))
    for r in c.fetchall()
]

# Seasons list for scatter dropdown (all RS with division players, sorted by id)
c.execute("""
    SELECT DISTINCT s.id, s.name FROM seasons s
    JOIN players p ON p.season_id = s.id
    WHERE p.division_level IS NOT NULL AND p.season_type = 'Regular Season'
    ORDER BY s.id
""")
scatter_seasons = [{'id': r[0], 'name': r[1]} for r in c.fetchall()]

conn.close()

data = {
    'summary': summary,
    'topScorers': top_scorers,
    'topGoals': top_goals,
    'topAssists': top_assists,
    'topGP': top_gp,
    'divLeaders': div_leaders,
    'teams': teams,
    'seasons': seasons_data,
    'jayson': jayson,
    # Goalie data
    'goalieWins': goalie_wins,
    'goalieGAA': goalie_gaa,
    'goalieSVP': goalie_svp,
    'goalieShutouts': goalie_shutouts,
    'goalieGP': goalie_gp,
    'goalieDivLeaders': goalie_div_leaders,
    'scatterSkaters': scatter_skaters,
    'scatterGoalies': scatter_goalies,
    'scatterSeasons': scatter_seasons,
}

with open(OUT, 'w') as f:
    json.dump(data, f)

# Also write a .js version so the dashboard works when opened from the filesystem
js_out = OUT.replace('dashboard_data.json', 'dashboard_data.js')
with open(js_out, 'w') as f:
    f.write('var DATA = ')
    json.dump(data, f)
    f.write(';\n')
print(f'Saved JS: {js_out}')

print(f'Data ready:')
print(f'  Scorers: {len(top_scorers)}, Teams: {len(teams)}, Seasons: {len(seasons_data)}')
print(f'  Goalie wins leaders: {len(goalie_wins)}')
print(f'  Goalie GAA leaders:  {len(goalie_gaa)}')
print(f'  Goalie SVP leaders:  {len(goalie_svp)}')
print(f'  Goalie SO leaders:   {len(goalie_shutouts)}')
print(f'  Goalie GP leaders:   {len(goalie_gp)}')
print(f'Saved: {OUT}')
