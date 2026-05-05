"""
Refresh active-season stats in the SKAHL historical DB.

Reads active_seasons_data.json from WORKSPACE, deletes existing stats
for those seasons, and re-inserts fresh scraped data.

Usage:
  python3 skahl_update_active.py [workspace_path]

  workspace_path defaults to the folder containing this script.

Active seasons: update ACTIVE_SEASON_MAP when a new season starts.
"""
import json, sqlite3, os, shutil, sys
from collections import defaultdict

# ── Paths ──────────────────────────────────────────────────────────────────────
if len(sys.argv) > 1:
    WORKSPACE = sys.argv[1]
else:
    WORKSPACE = os.path.dirname(os.path.abspath(__file__))

DB_WORKSPACE = os.path.join(WORKSPACE, 'skahl_historical.db')
DB_TMP       = '/tmp/skahl_work.db'
JSON_PATH    = os.path.join(WORKSPACE, 'active_seasons_data.json')

# ── Active seasons ─────────────────────────────────────────────────────────────
# sportninja_id → {db_id, season_type}
# Update this when new seasons begin.
ACTIVE_SEASON_MAP = {
    'SA6WRBsAXR2e6mtV': {'db_id': 1106, 'season_type': 'Regular Season'},
}

# ── Helpers ────────────────────────────────────────────────────────────────────
def div_level(div_name):
    n = (div_name or '').upper().strip()
    if n.startswith('B'):                                         return 'B'
    elif n.startswith('C'):                                       return 'C'
    elif n.startswith('DN') or n.startswith('D-N') or n.startswith('D N'): return 'E'
    elif n.startswith('D'):                                       return 'D'
    return None

print("=" * 60)
print("SKAHL ACTIVE SEASON REFRESH")
print("=" * 60)

# ── Load JSON ──────────────────────────────────────────────────────────────────
print(f"\n[1] Loading {JSON_PATH} ...")
with open(JSON_PATH) as f:
    data = json.load(f)
for sn_id, s in data.items():
    print(f"  {s['name']}: {len(s.get('skaters',[]))} skaters, {len(s.get('goalies',[]))} goalies")

# ── Copy DB to /tmp ────────────────────────────────────────────────────────────
print(f"\n[2] Copying DB to {DB_TMP} ...")
shutil.copy(DB_WORKSPACE, DB_TMP)

conn = sqlite3.connect(DB_TMP)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
cursor = conn.cursor()

cursor.execute("SELECT MAX(id) FROM players")
max_player_id = cursor.fetchone()[0] or 0
cursor.execute("SELECT MAX(id) FROM divisions")
max_div_id = cursor.fetchone()[0] or 0

# ── Player name lookup ─────────────────────────────────────────────────────────
print("\n[3] Building player name lookup...")
cursor.execute("""
    SELECT DISTINCT id, LOWER(first_name || last_name) AS nk
    FROM players WHERE first_name IS NOT NULL AND last_name IS NOT NULL
""")
name_to_id = {}
for pid, nk in cursor.fetchall():
    if nk not in name_to_id:
        name_to_id[nk] = pid
print(f"  {len(name_to_id)} unique names indexed")

next_player_id = max_player_id + 1
next_div_id    = max_div_id + 1

# ── Process each active season ─────────────────────────────────────────────────
print("\n[4] Refreshing active seasons...")

for sn_id, season_data in data.items():
    if sn_id not in ACTIVE_SEASON_MAP:
        print(f"  Unknown season {sn_id}, skipping")
        continue

    db_id       = ACTIVE_SEASON_MAP[sn_id]['db_id']
    season_type = ACTIVE_SEASON_MAP[sn_id]['season_type']
    season_name = season_data['name']

    print(f"\n  --- {season_name} (db_id={db_id}) ---")

    # Upsert season row
    cursor.execute("SELECT id FROM seasons WHERE id=?", (db_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO seasons (id, name) VALUES (?,?)", (db_id, season_name))

    # DELETE existing stats for this season so we can re-insert fresh data
    cursor.execute("DELETE FROM player_stats WHERE season_id=?", (db_id,))
    cursor.execute("DELETE FROM goalie_stats WHERE season_id=?", (db_id,))
    conn.commit()

    div_cache = {}

    # ── Skaters ────────────────────────────────────────────────────────────────
    skaters = season_data.get('skaters', [])
    ps_agg  = defaultdict(lambda: {'gp': 0, 'goals': 0, 'assists': 0, 'points': 0, 'pim': 0})
    sk_new  = sk_matched = 0

    for row in skaters:
        fn = (row.get('fn') or '').strip()
        ln = (row.get('ln') or '').strip()
        if not fn and not ln:
            continue
        if (fn + ' ' + ln).strip().lower() == 'empty net':
            continue

        _dsn = row.get('divId', '')
        _dn  = row.get('div', '')
        if _dsn in div_cache:
            div_info = div_cache[_dsn]
        else:
            _lvl = div_level(_dn)
            if not _lvl:
                continue
            cursor.execute("SELECT id FROM divisions WHERE season_id=? AND name=?", (db_id, _dn))
            _ex = cursor.fetchone()
            if _ex:
                _ddid = _ex[0]
            else:
                _ddid = next_div_id; next_div_id += 1
                cursor.execute("INSERT INTO divisions (id, season_id, name) VALUES (?,?,?)",
                               (_ddid, db_id, _dn))
            div_info = {'db_div_id': _ddid, 'level': _lvl, 'name': _dn}
            div_cache[_dsn] = div_info

        _nk = (fn + ln).lower()
        if _nk in name_to_id:
            pid = name_to_id[_nk]; sk_matched += 1
        else:
            pid = next_player_id; next_player_id += 1
            name_to_id[_nk] = pid; sk_new += 1

        s   = row.get('stats', {})
        gp  = int(s.get('GP', 0) or 0)
        g   = int(s.get('G', 0) or 0)
        a   = int(s.get('A', 0) or 0)
        p   = int(s.get('P', 0) or 0)
        pim = int(s.get('PiM', s.get('PIM', 0)) or 0)
        if p == 0 and g + a > 0:
            p = g + a

        cursor.execute("""
            INSERT OR IGNORE INTO players
            (id, season_id, division_id, team_id, team_name,
             first_name, last_name, jersey_number,
             position, position_str, status, status_str,
             primary_team_name, division_level, season_type, primary_division_level)
            VALUES (?,?,?,NULL,?, ?,?,?, NULL,NULL,NULL,NULL, ?,?,?,?)
        """, (pid, db_id, div_info['db_div_id'],
              (row.get('team') or '').strip(),
              fn, ln, row.get('num'),
              (row.get('team') or '').strip(),
              div_info['level'], season_type, div_info['level']))

        ps_agg[(pid, db_id)]['gp']      += gp
        ps_agg[(pid, db_id)]['goals']   += g
        ps_agg[(pid, db_id)]['assists'] += a
        ps_agg[(pid, db_id)]['points']  += p
        ps_agg[(pid, db_id)]['pim']     += pim

    ps_inserted = 0
    for (pid, sid), st in ps_agg.items():
        cursor.execute("""
            INSERT INTO player_stats (player_id, season_id, gp, goals, assists, points, pim)
            VALUES (?,?,?,?,?,?,?)
        """, (pid, sid, st['gp'], st['goals'], st['assists'], st['points'], st['pim']))
        ps_inserted += 1

    conn.commit()
    print(f"    Skaters: {sk_matched} matched, {sk_new} new, {ps_inserted} stat rows")

    # ── Goalies ────────────────────────────────────────────────────────────────
    goalies = season_data.get('goalies', [])
    gl_new  = gl_matched = gl_inserted = 0
    # Aggregate goalie stats by (pid, db_id, ddid) — same player may appear
    # multiple times in the same division (different teams)
    gl_agg  = defaultdict(lambda: {'gp':0,'w':0,'l':0,'t':0,'ga':0,'sa':0,'sv':0,'so':0,'toi':None,'team':'','fn':'','ln':'','num':None,'lvl':''})

    for row in goalies:
        fn = (row.get('fn') or '').strip()
        ln = (row.get('ln') or '').strip()
        if not fn and not ln:
            continue
        if (fn + ' ' + ln).strip().lower() == 'empty net':
            continue

        _dsn = row.get('divId', '')
        _dn  = row.get('div', '')
        if _dsn in div_cache:
            div_info = div_cache[_dsn]
        else:
            _lvl = div_level(_dn)
            if not _lvl:
                continue
            cursor.execute("SELECT id FROM divisions WHERE season_id=? AND name=?", (db_id, _dn))
            _ex = cursor.fetchone()
            if _ex:
                _ddid = _ex[0]
            else:
                _ddid = next_div_id; next_div_id += 1
                cursor.execute("INSERT INTO divisions (id, season_id, name) VALUES (?,?,?)",
                               (_ddid, db_id, _dn))
            div_info = {'db_div_id': _ddid, 'level': _lvl, 'name': _dn}
            div_cache[_dsn] = div_info

        _nk = (fn + ln).lower()
        if _nk in name_to_id:
            pid = name_to_id[_nk]; gl_matched += 1
        else:
            pid = next_player_id; next_player_id += 1
            name_to_id[_nk] = pid; gl_new += 1

        s    = row.get('stats', {})
        gp   = int(s.get('GP', 0) or 0)
        w    = int(s.get('W', 0) or 0)
        l    = int(s.get('L', 0) or 0)
        t    = int(s.get('T', 0) or 0)
        ga   = int(s.get('GA', 0) or 0)
        sa   = int(s.get('SA', 0) or 0)
        sv   = int(s.get('SV', 0) or 0)
        so   = int(s.get('SO', 0) or 0)
        toi  = s.get('MIN')

        ddid = div_info['db_div_id']
        lvl  = div_info['level']
        team = (row.get('team') or '').strip()

        agg_key = (pid, db_id, ddid)
        ag = gl_agg[agg_key]
        ag['gp'] += gp; ag['w'] += w; ag['l'] += l; ag['t'] += t
        ag['ga'] += ga; ag['sa'] += sa; ag['sv'] += sv; ag['so'] += so
        if toi and ag['toi'] is None:
            ag['toi'] = toi  # keep first non-null TOI
        ag['team'] = team; ag['fn'] = fn; ag['ln'] = ln
        ag['num'] = row.get('num'); ag['lvl'] = lvl

    for (pid, sid, ddid), ag in gl_agg.items():
        sa  = ag['sa']; sv = ag['sv']; ga = ag['ga']; gp = ag['gp']
        svp = sv / sa if sa > 0 else 0.0
        gaa = (ga / gp * 60 / 60) if gp > 0 else 0.0  # approximate

        cursor.execute("""
            INSERT OR IGNORE INTO players
            (id, season_id, division_id, team_id, team_name,
             first_name, last_name, jersey_number,
             position, position_str, status, status_str,
             primary_team_name, division_level, season_type, primary_division_level)
            VALUES (?,?,?,NULL,?, ?,?,?, NULL,NULL,NULL,NULL, ?,?,?,?)
        """, (pid, sid, ddid, ag['team'], ag['fn'], ag['ln'], ag['num'],
              ag['team'], ag['lvl'], season_type, ag['lvl']))

        cursor.execute("""
            INSERT INTO goalie_stats
            (player_id, season_id, division_id, gp, w, l, t, otl,
             ga, gaa, sa, sv, svp, so, toi)
            VALUES (?,?,?,?,?,?,?,0, ?,?,?,?,?,?,?)
        """, (pid, sid, ddid, gp, ag['w'], ag['l'], ag['t'],
              ga, gaa, sa, sv, svp, ag['so'], ag['toi']))
        gl_inserted += 1

    conn.commit()
    print(f"    Goalies:  {gl_matched} matched, {gl_new} new, {gl_inserted} stat rows")

# ── Recalculate primary team/division ─────────────────────────────────────────
print("\n[5] Recalculating primary_team_name / primary_division_level...")
cursor.execute("""
    WITH deduped_ps AS (SELECT DISTINCT player_id, season_id, gp FROM player_stats),
    agg AS (SELECT player_id, season_id, SUM(gp) AS gp FROM deduped_ps GROUP BY player_id, season_id),
    best_team AS (
        SELECT p.id, p.team_name, SUM(COALESCE(a.gp,0)) AS tgp,
               ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY SUM(COALESCE(a.gp,0)) DESC) AS rn
        FROM players p
        LEFT JOIN agg a ON p.id=a.player_id AND p.season_id=a.season_id
        WHERE p.division_level IS NOT NULL
        GROUP BY p.id, p.team_name
    ),
    best_div AS (
        SELECT p.id, p.division_level,
               ROW_NUMBER() OVER (
                   PARTITION BY p.id
                   ORDER BY CASE p.division_level WHEN 'B' THEN 1 WHEN 'C' THEN 2 WHEN 'D' THEN 3 ELSE 4 END
               ) AS rn
        FROM players p WHERE p.division_level IS NOT NULL
        GROUP BY p.id, p.division_level
    )
    UPDATE players SET
        primary_team_name      = (SELECT team_name FROM best_team WHERE id=players.id AND rn=1),
        primary_division_level = (SELECT division_level FROM best_div WHERE id=players.id AND rn=1)
    WHERE division_level IS NOT NULL
""")
conn.commit()

conn.close()

# ── Copy updated DB back to workspace ─────────────────────────────────────────
print(f"\n[6] Writing updated DB back to workspace...")
shutil.copy(DB_TMP, DB_WORKSPACE)
print(f"  Done: {DB_WORKSPACE}")

print("\n" + "=" * 60)
print("ACTIVE SEASON REFRESH COMPLETE")
print("=" * 60)
