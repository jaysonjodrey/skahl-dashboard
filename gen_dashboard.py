"""
Generate skahl_dashboard.html from dashboard_data.json in WORKSPACE.
Usage: python3 gen_dashboard.py [workspace_path]
"""
import json, datetime, sys, os

WORKSPACE = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(WORKSPACE, 'dashboard_data.json')
OUT_PATH  = os.path.join(WORKSPACE, 'skahl_dashboard.html')

with open(DATA_PATH) as f:
    d = json.load(f)

s = d['summary']

def fmt(n):
    if n is None: return '—'
    if isinstance(n, float): return f'{n:,.2f}'
    return f'{n:,}'

def div_badge(dv):
    if not dv: return ''
    return f'<span class="div-badge div-{dv}">{dv}</span>'

def rank_cls(i):
    if i == 0: return 'gold'
    if i == 1: return 'silver'
    if i == 2: return 'bronze'
    return ''

# ── Skater table rows ──────────────────────────────────────────────────────────
def skater_rows(rows, cols):
    """cols: list of (key, label, css_class)"""
    out = []
    for i, r in enumerate(rows):
        rc = rank_cls(i)
        cells = ''.join(
            f'<td class="num {c if c else ""}">{fmt(r.get(k))}</td>'
            for k, _, c in cols
        )
        out.append(
            f'<tr>'
            f'<td class="rank {rc}">{i+1}</td>'
            f'<td><span class="player-name">{r["name"]}</span>'
            f'<br><span class="team-name">{r.get("team") or ""}</span></td>'
            f'<td></td>'
            f'<td>{div_badge(r.get("div"))}</td>'
            f'{cells}'
            f'</tr>'
        )
    return '\n'.join(out)

# ── Goalie table rows ──────────────────────────────────────────────────────────
def goalie_rows(rows, cols):
    out = []
    for i, r in enumerate(rows):
        rc = rank_cls(i)
        cells = ''.join(
            f'<td class="num {c if c else ""}">{fmt(r.get(k))}</td>'
            for k, _, c in cols
        )
        out.append(
            f'<tr>'
            f'<td class="rank {rc}">{i+1}</td>'
            f'<td><span class="player-name">{r["name"]}</span>'
            f'<br><span class="team-name">{r.get("team") or ""}</span></td>'
            f'<td>{div_badge(r.get("div"))}</td>'
            f'{cells}'
            f'</tr>'
        )
    return '\n'.join(out)

# ── Division skater tables ─────────────────────────────────────────────────────
def div_skater_section(div, rows):
    return f"""
<div id="div-{div}-skater" class="div-sub active" style="display:none">
  <div class="table-wrap">
    <table id="div-{div}-table">
      <thead><tr>
        <th style="width:36px">#</th>
        <th>Player</th><th>Team</th>
        <th class="num" onclick="sortTable('div-{div}-table',3)">Seasons</th>
        <th class="num" onclick="sortTable('div-{div}-table',4)">GP</th>
        <th class="num" onclick="sortTable('div-{div}-table',5)">G</th>
        <th class="num" onclick="sortTable('div-{div}-table',6)">A</th>
        <th class="num sorted" onclick="sortTable('div-{div}-table',7)">PTS</th>
        <th class="num" onclick="sortTable('div-{div}-table',8)">PPG</th>
      </tr></thead>
      <tbody>
        {''.join(
            f"<tr>"
            f"<td class='rank {rank_cls(i)}'>{i+1}</td>"
            f"<td><span class='player-name'>{r['name']}</span><br><span class='team-name'>{r.get('team','')}</span></td>"
            f"<td></td>"
            f"<td class='num'>{fmt(r.get('seasons'))}</td>"
            f"<td class='num'>{fmt(r.get('gp'))}</td>"
            f"<td class='num'>{fmt(r.get('goals'))}</td>"
            f"<td class='num'>{fmt(r.get('assists'))}</td>"
            f"<td class='num pts'>{fmt(r.get('points'))}</td>"
            f"<td class='num'>{fmt(r.get('ppg'))}</td>"
            f"</tr>"
            for i, r in enumerate(rows)
        )}
      </tbody>
    </table>
  </div>
</div>"""

# ── Division goalie tables ─────────────────────────────────────────────────────
def div_goalie_section(div, rows):
    return f"""
<div id="div-{div}-goalie" class="div-sub" style="display:none">
  <div class="table-wrap">
    <table id="div-{div}-gtable">
      <thead><tr>
        <th style="width:36px">#</th>
        <th>Goalie</th><th>Team</th>
        <th class="num">Seasons</th>
        <th class="num">GP</th>
        <th class="num sorted">W</th>
        <th class="num">L</th>
        <th class="num">SO</th>
        <th class="num">SVP</th>
        <th class="num">GAA</th>
      </tr></thead>
      <tbody>
        {''.join(
            f"<tr>"
            f"<td class='rank {rank_cls(i)}'>{i+1}</td>"
            f"<td><span class='player-name'>{r['name']}</span><br><span class='team-name'>{r.get('team','')}</span></td>"
            f"<td></td>"
            f"<td class='num'>{fmt(r.get('seasons'))}</td>"
            f"<td class='num'>{fmt(r.get('gp'))}</td>"
            f"<td class='num pts'>{fmt(r.get('wins'))}</td>"
            f"<td class='num'>{fmt(r.get('losses'))}</td>"
            f"<td class='num'>{fmt(r.get('shutouts'))}</td>"
            f"<td class='num'>{fmt(r.get('svp'))}</td>"
            f"<td class='num'>{fmt(r.get('gaa'))}</td>"
            f"</tr>"
            for i, r in enumerate(rows)
        )}
      </tbody>
    </table>
  </div>
</div>"""

# Precompute season bars
max_goals = max((s2['total_goals'] or 0) for s2 in d['seasons']) or 1
def season_bar(s2):
    h = max(4, int((s2['total_goals'] or 0) / max_goals * 100))
    name = s2['name']
    goals = s2['total_goals']
    return f'<div class="bar" style="height:{h}%" title="{name}: {goals} goals"></div>'
season_bars = '\n'.join(season_bar(s2) for s2 in d['seasons'])

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sno-King Adult Hockey League — Historical Dashboard</title>
<style>
  :root {{
    --bg:#0d1117; --card:#161b22; --border:#30363d;
    --accent:#2563eb; --accent2:#1d4ed8; --gold:#f59e0b;
    --silver:#94a3b8; --bronze:#b45309;
    --text:#e6edf3; --muted:#8b949e; --green:#22c55e;
    --red:#ef4444; --teal:#14b8a6;
    --divB:#6366f1; --divC:#06b6d4; --divD:#22c55e; --divE:#f97316;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px}}
  .header{{position:relative;background:linear-gradient(135deg,#0d1117 0%,#1a2744 50%,#0d1117 100%);padding:28px 24px 20px;border-bottom:1px solid var(--border)}}
  .header h1{{font-size:26px;font-weight:800;color:#fff;letter-spacing:-.5px}}
  .header h1 span{{color:var(--gold)}}
  .header p{{color:var(--muted);font-size:13px;margin-top:4px}}
  .stats-row{{display:flex;gap:16px;margin-top:20px;flex-wrap:wrap}}
  .stat-card{{background:rgba(255,255,255,.05);border:1px solid var(--border);border-radius:10px;padding:14px 18px;min-width:110px}}
  .stat-card .val{{font-size:22px;font-weight:700;color:var(--gold)}}
  .stat-card .lbl{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-top:2px}}
  .nav{{display:flex;gap:2px;padding:12px 24px 0;background:var(--card);border-bottom:1px solid var(--border);overflow-x:auto}}
  .nav-btn{{padding:9px 16px;border:none;background:none;color:var(--muted);cursor:pointer;font-size:13px;font-weight:500;border-bottom:2px solid transparent;transition:all .15s;white-space:nowrap;border-radius:6px 6px 0 0}}
  .nav-btn:hover{{color:var(--text);background:rgba(255,255,255,.05)}}
  .nav-btn.active{{color:#fff;border-bottom-color:var(--accent);background:rgba(37,99,235,.1)}}
  .panel{{display:none;padding:20px 24px}}
  .panel.active{{display:block}}
  .section-header{{display:flex;align-items:center;gap:10px;margin-bottom:14px;margin-top:4px}}
  .section-header h2{{font-size:16px;font-weight:700}}
  .sub-tabs{{display:flex;gap:8px;flex-wrap:wrap}}
  .sub-tab{{padding:5px 14px;border:1px solid var(--border);border-radius:20px;background:none;color:var(--muted);cursor:pointer;font-size:12px;font-weight:500;transition:all .15s}}
  .sub-tab.active,.sub-tab:hover{{background:var(--accent);border-color:var(--accent);color:#fff}}
  .table-wrap{{overflow-x:auto;border-radius:10px;border:1px solid var(--border)}}
  table{{width:100%;border-collapse:collapse}}
  thead tr{{background:#1e2936}}
  th{{padding:10px 12px;text-align:left;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);cursor:pointer;user-select:none;white-space:nowrap}}
  th:hover{{color:var(--text)}}
  th.sorted{{color:var(--gold)}}
  td{{padding:9px 12px;border-top:1px solid rgba(48,54,61,.6);font-size:13px;white-space:nowrap}}
  tr:hover td{{background:rgba(255,255,255,.03)}}
  .rank{{color:var(--muted);font-size:12px;width:32px}}
  .rank.gold{{color:var(--gold);font-weight:700}}
  .rank.silver{{color:var(--silver);font-weight:700}}
  .rank.bronze{{color:var(--bronze);font-weight:700}}
  .player-name{{font-weight:600;color:#fff}}
  .team-name{{color:var(--muted);font-size:12px}}
  .div-badge{{display:inline-block;padding:2px 7px;border-radius:10px;font-size:11px;font-weight:700}}
  .div-B{{background:rgba(99,102,241,.25);color:#818cf8;border:1px solid rgba(99,102,241,.4)}}
  .div-C{{background:rgba(6,182,212,.2);color:#22d3ee;border:1px solid rgba(6,182,212,.4)}}
  .div-D{{background:rgba(34,197,94,.2);color:#4ade80;border:1px solid rgba(34,197,94,.4)}}
  .div-E{{background:rgba(249,115,22,.2);color:#fb923c;border:1px solid rgba(249,115,22,.4)}}
  .num{{text-align:right;font-variant-numeric:tabular-nums}}
  .pts{{font-weight:700;color:var(--gold)}}
  .svp-val{{font-weight:700;color:var(--teal)}}
  .gaa-val{{font-weight:700;color:var(--green)}}
  .search-box{{display:flex;gap:10px;margin-bottom:16px}}
  .search-input{{flex:1;padding:9px 14px;background:var(--card);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:14px;outline:none;max-width:380px}}
  .search-input:focus{{border-color:var(--accent)}}
  .chart-wrap{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:16px}}
  .chart-title{{font-size:13px;font-weight:600;color:var(--muted);margin-bottom:12px}}
  .bar-chart{{display:flex;align-items:flex-end;gap:3px;height:120px;padding-bottom:4px}}
  .bar{{flex:1;background:var(--accent);border-radius:3px 3px 0 0;min-width:6px;cursor:pointer;transition:opacity .15s;position:relative}}
  .bar:hover{{opacity:.8}}
  .teams-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}}
  .team-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 16px}}
  .team-card .tname{{font-weight:700;font-size:14px;margin-bottom:6px}}
  .team-card .tmeta{{font-size:12px;color:var(--muted);display:flex;gap:12px}}
  .player-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;max-width:680px}}
  .player-card h3{{font-size:20px;font-weight:800;margin-bottom:4px}}
  .player-stats-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:16px 0}}
  .pstat{{background:rgba(255,255,255,.04);border-radius:8px;padding:12px;text-align:center}}
  .pstat .pval{{font-size:20px;font-weight:700;color:var(--gold)}}
  .pstat .plbl{{font-size:11px;color:var(--muted);margin-top:2px}}
  .season-table{{margin-top:12px}}
  .filter-row{{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;align-items:center}}
  .filter-label{{font-size:12px;color:var(--muted)}}
  .updated-label{{position:absolute;top:28px;right:24px;font-size:11px;color:var(--muted);text-align:right}}
  .mode-toggle{{display:flex;align-items:center;gap:8px;background:var(--card);border-bottom:1px solid var(--border);padding:10px 20px}}
  .mode-label{{color:var(--muted);font-size:12px;font-weight:600;letter-spacing:.5px;text-transform:uppercase;margin-right:4px}}
  .mode-btn{{padding:6px 20px;border:1px solid var(--border);background:none;color:var(--muted);cursor:pointer;font-size:13px;font-weight:600;border-radius:20px;transition:all .15s}}
  .mode-btn:hover{{color:var(--text);border-color:var(--accent)}}
  .mode-btn.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
  .scatter-filters{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px;padding:10px 14px;background:var(--surface,var(--card));border:1px solid var(--border);border-radius:8px}}
  .scatter-lbl{{color:var(--muted);font-size:11px;font-weight:700;letter-spacing:.5px;text-transform:uppercase}}
  .scatter-filters select{{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:4px 10px;border-radius:6px;font-size:13px;cursor:pointer}}
  .scatter-pill{{padding:4px 14px;border:1px solid var(--border);background:none;color:var(--muted);cursor:pointer;font-size:12px;font-weight:700;border-radius:14px;transition:all .15s}}
  .scatter-pill.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
  .scatter-pill:hover:not(.active){{border-color:var(--accent);color:var(--text)}}
  .chart-wrap{{position:relative;height:420px;margin-top:8px}}
  .scatter-title{{font-size:15px;font-weight:700;margin-bottom:2px}}
  .scatter-sub{{font-size:12px;color:var(--muted);margin-bottom:12px}}
  [data-skateronly]{{display:inline-flex}}
  [data-goalieonly]{{display:none}}
  .goalie-note{{font-size:12px;color:var(--muted);margin-bottom:10px;padding:8px 12px;background:rgba(255,255,255,.03);border-radius:6px;border-left:3px solid var(--accent)}}
  .empty{{color:var(--muted);padding:24px;text-align:center}}
  .div-section-tabs{{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap}}
  .div-section-tab{{padding:5px 12px;border:1px solid var(--border);border-radius:6px;background:none;color:var(--muted);cursor:pointer;font-size:12px;font-weight:500;transition:all .15s}}
  .div-section-tab.active{{background:rgba(255,255,255,.08);border-color:var(--text);color:var(--text)}}
  @media(max-width:600px){{
    .stats-row{{gap:8px}}
    .stat-card{{min-width:80px;padding:10px 12px}}
    .stat-card .val{{font-size:18px}}
    .panel{{padding:14px 12px}}
    .player-stats-grid{{grid-template-columns:repeat(2,1fr)}}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="updated-label">Last updated<br>{datetime.date.today().strftime('%B %-d, %Y')}</div>
  <h1>SKAHL <span>Historical Stats</span></h1>
  <p>Sno-King Adult Hockey League &middot; All-time records from 2015 to 2026</p>
  <div class="stats-row">
    <div class="stat-card"><div class="val">{fmt(s['unique_players'])}</div><div class="lbl">Players</div></div>
    <div class="stat-card"><div class="val">{fmt(s['total_gp'])}</div><div class="lbl">Games Played</div></div>
    <div class="stat-card"><div class="val">{fmt(s['total_goals'])}</div><div class="lbl">Goals Scored</div></div>
    <div class="stat-card"><div class="val">{fmt(s['total_saves'])}</div><div class="lbl">Saves Made</div></div>
  </div>
</div>

<div class="mode-toggle">
  <span class="mode-label">View:</span>
  <button class="mode-btn active" id="mode-skaters" onclick="switchMode('skaters')">&#9976; Skaters</button>
  <button class="mode-btn" id="mode-goalies" onclick="switchMode('goalies')">&#128325; Goalies</button>
</div>
<div class="nav">
  <button class="nav-btn active" data-skateronly onclick="showTab('alltime')">&#127954; All-Time</button>
  <button class="nav-btn" data-skateronly onclick="showTab('divisions')">&#9976; By Division</button>
  <button class="nav-btn" data-skateronly onclick="showTab('teams')">&#127942; Teams</button>
  <button class="nav-btn" data-skateronly onclick="showTab('seasons')">&#128197; Seasons</button>
  <button class="nav-btn" data-goalieonly onclick="showTab('goalies')">&#128325; All-Time</button>
  <button class="nav-btn" id="nav-scatter" onclick="showTab('scatter')">&#128202; Scatter</button>
</div>

<!-- ══════════════════════════════════════════════════════ ALL-TIME ══ -->
<div id="tab-alltime" class="panel active">
  <div class="filter-row">
    <span class="filter-label">Leaderboard:</span>
    <div class="sub-tabs">
      <button class="sub-tab active" onclick="showAllTimeList('points',this)">Points</button>
      <button class="sub-tab" onclick="showAllTimeList('goals',this)">Goals</button>
      <button class="sub-tab" onclick="showAllTimeList('assists',this)">Assists</button>
      <button class="sub-tab" onclick="showAllTimeList('gp',this)">Games Played</button>
    </div>
    <div class="search-box" style="margin:0;margin-left:auto">
      <input class="search-input" id="atSearch" placeholder="Filter by name or team…" oninput="filterTable('at-table',this.value)">
    </div>
  </div>
  <div class="table-wrap">
    <table id="at-table">
      <thead><tr>
        <th style="width:36px">#</th>
        <th>Player</th><th>Team</th><th>Div</th>
        <th class="num" onclick="sortTable('at-table',4)">Seasons</th>
        <th class="num" onclick="sortTable('at-table',5)">GP</th>
        <th class="num" onclick="sortTable('at-table',6)">G</th>
        <th class="num" onclick="sortTable('at-table',7)">A</th>
        <th class="num sorted" onclick="sortTable('at-table',8)">PTS</th>
        <th class="num" onclick="sortTable('at-table',9)">PPG</th>
      </tr></thead>
      <tbody id="at-body">
        {skater_rows(d['topScorers'], [('seasons','Seasons',''),('gp','GP',''),('goals','G',''),('assists','A',''),('points','PTS','pts'),('ppg','PPG','')])}
      </tbody>
    </table>
  </div>
</div>

<!-- ════════════════════════════════════════════════════ BY DIVISION ══ -->
<div id="tab-divisions" class="panel">
  <div class="filter-row">
    <span class="filter-label">Division:</span>
    <div class="sub-tabs" id="div-tabs">
      <button class="sub-tab active" onclick="showDiv('B',this)">Division B</button>
      <button class="sub-tab" onclick="showDiv('C',this)">Division C</button>
      <button class="sub-tab" onclick="showDiv('D',this)">Division D</button>
      <button class="sub-tab" onclick="showDiv('E',this)">Division E</button>
    </div>
  </div>
  <div class="div-section-tabs">
    <button class="div-section-tab active" id="div-skater-btn" onclick="showDivSection('skater')">&#9196; Skaters</button>
    <button class="div-section-tab" id="div-goalie-btn" onclick="showDivSection('goalie')">&#129354; Goalies</button>
  </div>

  {''.join(div_skater_section(div, d['divLeaders'][div]) for div in ['B','C','D','E'])}
  {''.join(div_goalie_section(div, d['goalieDivLeaders'][div]) for div in ['B','C','D','E'])}
</div>

<!-- ══════════════════════════════════════════════════════ GOALIES ══ -->
<div id="tab-goalies" class="panel">
  <div class="filter-row">
    <span class="filter-label">Leaderboard:</span>
    <div class="sub-tabs">
      <button class="sub-tab active" onclick="showGoalieList('wins',this)">Most Wins</button>
      <button class="sub-tab" onclick="showGoalieList('gaa',this)">Best GAA</button>
      <button class="sub-tab" onclick="showGoalieList('svp',this)">Best Sv%</button>
      <button class="sub-tab" onclick="showGoalieList('shutouts',this)">Shutouts</button>
      <button class="sub-tab" onclick="showGoalieList('gp',this)">Most GP</button>
    </div>
    <div class="search-box" style="margin:0;margin-left:auto">
      <input class="search-input" id="gSearch" placeholder="Filter by name or team…" oninput="filterTable('g-table',this.value)">
    </div>
  </div>
  <div class="goalie-note" id="goalie-note">Min. 10 GP · Career totals · Regular season only</div>
  <div class="table-wrap">
    <table id="g-table">
      <thead><tr id="g-thead-row">
        <th style="width:36px">#</th>
        <th>Goalie</th><th>Div</th>
        <th class="num">Seasons</th>
        <th class="num">GP</th>
        <th class="num sorted">W</th>
        <th class="num">L</th>
        <th class="num">T</th>
        <th class="num">OTL</th>
        <th class="num">SO</th>
        <th class="num">Sv%</th>
        <th class="num">GAA</th>
      </tr></thead>
      <tbody id="g-body">
      </tbody>
    </table>
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════ TEAMS ══ -->
<div id="tab-teams" class="panel">
  <div class="filter-row">
    <span class="filter-label">Filter division:</span>
    <div class="sub-tabs">
      <button class="sub-tab active" onclick="filterTeams('all',this)">All</button>
      <button class="sub-tab" onclick="filterTeams('B',this)">B</button>
      <button class="sub-tab" onclick="filterTeams('C',this)">C</button>
      <button class="sub-tab" onclick="filterTeams('D',this)">D</button>
      <button class="sub-tab" onclick="filterTeams('E',this)">E</button>
    </div>
    <div class="search-box" style="margin:0;margin-left:auto">
      <input class="search-input" id="teamSearch" placeholder="Search teams…" oninput="renderTeams()">
    </div>
  </div>
  <div class="teams-grid" id="teams-grid"></div>
</div>

<!-- ══════════════════════════════════════════════════════ SEASONS ══ -->
<div id="tab-seasons" class="panel">
  <div class="chart-wrap">
    <div class="chart-title">Goals scored per season</div>
    <div class="bar-chart">{season_bars}</div>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>Season</th>
        <th class="num">Players</th>
        <th class="num">GP</th>
        <th class="num">Goals</th>
      </tr></thead>
      <tbody>
        {''.join(
            f"<tr><td>{r['name']}</td>"
            f"<td class='num'>{fmt(r['players'])}</td>"
            f"<td class='num'>{fmt(r['total_gp'])}</td>"
            f"<td class='num'>{fmt(r['total_goals'])}</td></tr>"
            for r in reversed(d['seasons'])
        )}
      </tbody>
    </table>
  </div>
</div>

<div id="tab-scatter" class="panel">
  <div class="scatter-filters">
    <span class="scatter-lbl">Season</span>
    <select id="scatter-season" onchange="renderScatter()">
      <option value="all">All Seasons</option>
    </select>
    <span class="scatter-lbl" style="margin-left:8px">Division</span>
    <button class="scatter-pill active" data-sdiv="all" onclick="scatterDivClick(this)">All</button>
    <button class="scatter-pill" data-sdiv="B" onclick="scatterDivClick(this)">B</button>
    <button class="scatter-pill" data-sdiv="C" onclick="scatterDivClick(this)">C</button>
    <button class="scatter-pill" data-sdiv="D" onclick="scatterDivClick(this)">D</button>
    <button class="scatter-pill" data-sdiv="E" onclick="scatterDivClick(this)">E</button>
  </div>
  <div class="scatter-title" id="scatter-title">Goals per Game vs. Assists per Game</div>
  <div class="scatter-sub" id="scatter-sub">All-time seasons with 15+ GP &middot; bubble size = points that season &middot; highlighted = above-median in both axes</div>
  <div class="chart-wrap"><canvas id="scatter-canvas"></canvas></div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script src="dashboard_data.js"></script>
<script>
"""

# Main dashboard JS

html += r"""
// ── Tab navigation ────────────────────────────────────────────────────────────
function showTab(id) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  event.currentTarget.classList.add('active');
  if (id === 'goalies' && !goalieInit) initGoalies();
  if (id === 'scatter') renderScatter();
  if (id === 'teams') renderTeams();
  if (id === 'divisions') showDiv(currentDiv, null);
}

// ── All-Time leaderboards ─────────────────────────────────────────────────────
const atLists = {
  points:  DATA.topScorers,
  goals:   DATA.topGoals,
  assists: DATA.topAssists,
  gp:      DATA.topGP,
};
const atCols = {
  points:  ['seasons','gp','goals','assists','points','ppg'],
  goals:   ['seasons','gp','goals','assists','points','ppg'],
  assists: ['seasons','gp','goals','assists','points','ppg'],
  gp:      ['seasons','gp','goals','assists','points','ppg'],
};

function showAllTimeList(type, btn) {
  document.querySelectorAll('#tab-alltime .sub-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const rows = atLists[type] || [];
  const body = document.getElementById('at-body');
  body.innerHTML = rows.map((r, i) => `
    <tr>
      <td class="rank ${['gold','silver','bronze'][i]||''}">${i+1}</td>
      <td><span class="player-name">${r.name}</span><br><span class="team-name">${r.team||''}</span></td>
      <td></td>
      <td>${divBadge(r.div)}</td>
      <td class="num">${r.seasons||'—'}</td>
      <td class="num">${r.gp||'—'}</td>
      <td class="num">${r.goals??'—'}</td>
      <td class="num">${r.assists??'—'}</td>
      <td class="num pts">${r.points??'—'}</td>
      ${r.ppg !== undefined ? `<td class="num">${r.ppg}</td>` : ''}
    </tr>`).join('');
  document.getElementById('atSearch').value = '';
}

// ── Division section ──────────────────────────────────────────────────────────
let currentDiv = 'B';
let currentDivSection = 'skater';

function showDiv(div, btn) {
  currentDiv = div;
  document.querySelectorAll('#div-tabs .sub-tab').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  else {
    const btns = document.querySelectorAll('#div-tabs .sub-tab');
    const idx = ['B','C','D','E'].indexOf(div);
    if (btns[idx]) btns[idx].classList.add('active');
  }
  // Show correct subsection
  document.querySelectorAll('.div-sub').forEach(el => el.style.display = 'none');
  const el = document.getElementById(`div-${div}-${currentDivSection}`);
  if (el) el.style.display = 'block';
}

function showDivSection(section) {
  currentDivSection = section;
  document.getElementById('div-skater-btn').classList.toggle('active', section === 'skater');
  document.getElementById('div-goalie-btn').classList.toggle('active', section === 'goalie');
  document.querySelectorAll('.div-sub').forEach(el => el.style.display = 'none');
  const el = document.getElementById(`div-${currentDiv}-${section}`);
  if (el) el.style.display = 'block';
}

// On initial division tab load, show B skaters
document.getElementById('div-B-skater').style.display = 'block';

// ── Goalies ───────────────────────────────────────────────────────────────────
let goalieInit = false;
let currentGoalieList = 'wins';

const goalieLists = {
  wins:     DATA.goalieWins,
  gaa:      DATA.goalieGAA,
  svp:      DATA.goalieSVP,
  shutouts: DATA.goalieShutouts,
  gp:       DATA.goalieGP,
};

const goalieNotes = {
  wins:     'Min. 10 GP · Career totals · All divisions',
  gaa:      'Min. 20 GP · Lower is better · All divisions',
  svp:      'Min. 20 GP · Higher is better · All divisions',
  shutouts: 'Min. 5 GP · Career totals · All divisions',
  gp:       'Career totals · All divisions',
};

const goalieHighlight = {
  wins:     'wins',
  gaa:      'gaa',
  svp:      'svp',
  shutouts: 'shutouts',
  gp:       'gp',
};

function initGoalies() {
  goalieInit = true;
  renderGoalieList('wins');
}

function showGoalieList(type, btn) {
  document.querySelectorAll('#tab-goalies .sub-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentGoalieList = type;
  renderGoalieList(type);
  document.getElementById('gSearch').value = '';
}

function renderGoalieList(type) {
  const rows = goalieLists[type] || [];
  const highlight = goalieHighlight[type];
  document.getElementById('goalie-note').textContent = goalieNotes[type] || '';

  const isWins = type === 'wins';
  const headRow = document.getElementById('g-thead-row');
  if (isWins) {
    headRow.innerHTML = `
      <th style="width:36px">#</th>
      <th>Goalie</th><th>Div</th>
      <th class="num">Seasons</th><th class="num">GP</th>
      <th class="num sorted">W</th><th class="num">L</th>
      <th class="num">T</th><th class="num">OTL</th>
      <th class="num">SO</th><th class="num">Sv%</th><th class="num">GAA</th>`;
  } else {
    headRow.innerHTML = `
      <th style="width:36px">#</th>
      <th>Goalie</th><th>Div</th>
      <th class="num">Seasons</th><th class="num">GP</th>
      <th class="num">W</th><th class="num">L</th>
      <th class="num">SO</th>
      <th class="num ${type==='svp'?'sorted':''}">Sv%</th>
      <th class="num ${type==='gaa'?'sorted':''}">GAA</th>`;
  }

  const body = document.getElementById('g-body');
  body.innerHTML = rows.map((r, i) => {
    const rc = ['gold','silver','bronze'][i] || '';
    if (isWins) {
      return `<tr>
        <td class="rank ${rc}">${i+1}</td>
        <td><span class="player-name">${r.name}</span><br><span class="team-name">${r.team||''}</span></td>
        <td>${divBadge(r.div)}</td>
        <td class="num">${r.seasons??'—'}</td>
        <td class="num">${r.gp??'—'}</td>
        <td class="num pts">${r.wins??'—'}</td>
        <td class="num">${r.losses??'—'}</td>
        <td class="num">${r.ties??'—'}</td>
        <td class="num">${r.otl??'—'}</td>
        <td class="num">${r.shutouts??'—'}</td>
        <td class="num svp-val">${r.svp??'—'}</td>
        <td class="num gaa-val">${r.gaa??'—'}</td>
      </tr>`;
    } else {
      const svpCell = `<td class="num ${type==='svp'?'svp-val':''}">${r.svp??'—'}</td>`;
      const gaaCell = `<td class="num ${type==='gaa'?'gaa-val':''}">${r.gaa??'—'}</td>`;
      const soCell  = `<td class="num ${type==='shutouts'?'pts':''}">${r.shutouts??'—'}</td>`;
      return `<tr>
        <td class="rank ${rc}">${i+1}</td>
        <td><span class="player-name">${r.name}</span><br><span class="team-name">${r.team||''}</span></td>
        <td>${divBadge(r.div)}</td>
        <td class="num">${r.seasons??'—'}</td>
        <td class="num ${type==='gp'?'pts':''}">${r.gp??'—'}</td>
        <td class="num">${r.wins??'—'}</td>
        <td class="num">${r.losses??'—'}</td>
        ${soCell}${svpCell}${gaaCell}
      </tr>`;
    }
  }).join('');
}

// ── Teams ─────────────────────────────────────────────────────────────────────
let teamDivFilter = 'all';
function filterTeams(div, btn) {
  teamDivFilter = div;
  document.querySelectorAll('#tab-teams .sub-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderTeams();
}
function renderTeams() {
  const q = (document.getElementById('teamSearch').value || '').toLowerCase();
  const grid = document.getElementById('teams-grid');
  grid.innerHTML = DATA.teams
    .filter(t => (teamDivFilter === 'all' || t.div === teamDivFilter) &&
                 (!q || t.name.toLowerCase().includes(q)))
    .map(t => `<div class="team-card">
      <div class="tname">${t.name} ${divBadge(t.div)}</div>
      <div class="tmeta"><span>${t.seasons} seasons</span><span>${t.players} players</span></div>
    </div>`).join('');
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function divBadge(dv) {
  if (!dv) return '';
  return `<span class="div-badge div-${dv}">${dv}</span>`;
}

function filterTable(tableId, q) {
  q = q.toLowerCase();
  const rows = document.getElementById(tableId).querySelectorAll('tbody tr');
  rows.forEach(row => {
    row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}

function sortTable(tableId, col) {
  const table = document.getElementById(tableId);
  const rows  = Array.from(table.querySelectorAll('tbody tr'));
  const dir   = table.dataset.sortDir === 'asc' ? -1 : 1;
  table.dataset.sortDir = dir === 1 ? 'desc' : 'asc';
  rows.sort((a, b) => {
    const av = parseFloat(a.cells[col]?.textContent.replace(/,/g,'')) || 0;
    const bv = parseFloat(b.cells[col]?.textContent.replace(/,/g,'')) || 0;
    return (bv - av) * dir;
  });
  const tbody = table.querySelector('tbody');
  rows.forEach(r => tbody.appendChild(r));
}


// ── Mode toggle ────────────────────────────────────────────────────────────────
let currentMode = 'skaters';
function switchMode(mode) {
  currentMode = mode;
  document.getElementById('mode-skaters').classList.toggle('active', mode === 'skaters');
  document.getElementById('mode-goalies').classList.toggle('active', mode === 'goalies');

  // Show/hide nav buttons
  document.querySelectorAll('[data-skateronly]').forEach(el => {
    el.style.display = mode === 'skaters' ? '' : 'none';
  });
  document.querySelectorAll('[data-goalieonly]').forEach(el => {
    el.style.display = mode === 'goalies' ? '' : 'none';
  });

  // Navigate to the right default tab
  if (mode === 'skaters') {
    const firstSkater = document.querySelector('.nav-btn[data-skateronly]');
    if (firstSkater) firstSkater.click();
  } else {
    const goalieBtn = document.querySelector('.nav-btn[data-goalieonly]');
    if (goalieBtn) goalieBtn.click();
  }
}

// ── Scatter chart ──────────────────────────────────────────────────────────────
let scatterChart = null;
let scatterDivFilter = 'all';

function scatterDivClick(btn) {
  document.querySelectorAll('.scatter-pill').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  scatterDivFilter = btn.dataset.sdiv;
  renderScatter();
}

function renderScatter() {
  const isGoalies = currentMode === 'goalies';
  const sid = document.getElementById('scatter-season').value;
  const allRows = isGoalies ? DATA.scatterGoalies : DATA.scatterSkaters;

  let rows = allRows.filter(r => {
    if (sid !== 'all' && String(r.sid) !== sid) return false;
    if (scatterDivFilter !== 'all' && r.dv !== scatterDivFilter) return false;
    return true;
  });

  // Build chart points
  const pts = rows.map(r => isGoalies
    ? { x: r.svp, y: r.gaa, r: Math.max(3, Math.sqrt((r.w||0)+1)*3), name: r.n, meta: r }
    : { x: r.gpg, y: r.apg, r: Math.max(3, 3 + Math.sqrt((r.pt||0))*1.1), name: r.n, meta: r }
  );

  // Compute medians
  const xs = pts.map(p => p.x).sort((a,b)=>a-b);
  const ys = pts.map(p => p.y).sort((a,b)=>a-b);
  const mid = n => n ? n[Math.floor(n.length/2)] : 0;
  const medX = mid(xs), medY = mid(ys);

  // Highlight points above median in both axes (for goalies: high SVP AND low GAA)
  const highlighted = isGoalies
    ? pts.map(p => p.x >= medX && p.y <= medY)
    : pts.map(p => p.x >= medX && p.y >= medY);

  const colors = pts.map((_, i) => highlighted[i]
    ? 'rgba(79,195,247,0.7)' : 'rgba(79,195,247,0.22)');
  const borders = pts.map((_, i) => highlighted[i]
    ? 'rgba(79,195,247,1)' : 'rgba(79,195,247,0.45)');

  document.getElementById('scatter-title').textContent = isGoalies
    ? 'Save Percentage vs. Goals Against Average'
    : 'Goals per Game vs. Assists per Game';
  document.getElementById('scatter-sub').textContent = isGoalies
    ? `${pts.length.toLocaleString()} goalie-seasons (3+ GP) · bubble size = wins · highlighted = above median SV% and below median GAA`
    : `${pts.length.toLocaleString()} player-seasons (15+ GP) · bubble size = points · highlighted = above median in both axes`;

  const ctx = document.getElementById('scatter-canvas').getContext('2d');
  if (scatterChart) scatterChart.destroy();

  scatterChart = new Chart(ctx, {
    type: 'bubble',
    data: { datasets: [{ data: pts, backgroundColor: colors, borderColor: borders, borderWidth: 1,
      hoverBackgroundColor: 'rgba(248,113,113,0.85)', hoverBorderColor: 'rgba(248,113,113,1)' }] },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a2937', borderColor: '#4fc3f7', borderWidth: 1, padding: 10,
          callbacks: {
            title: items => items[0].raw.name,
            label: ctx => {
              const r = ctx.raw.meta;
              const sid = document.getElementById('scatter-season').value;
              const allData = isGoalies ? DATA.scatterGoalies : DATA.scatterSkaters;
              const rows = allData.filter(pr =>
                pr.n === r.n &&
                (scatterDivFilter === 'all' || pr.dv === scatterDivFilter) &&
                (sid === 'all' || String(pr.sid) === sid)
              );
              const lbl = sid === 'all' ? 'Career' : 'Season';
              if (isGoalies) {
                const tgp = rows.reduce((s, pr) => s + (pr.gp||0), 0);
                const tw  = rows.reduce((s, pr) => s + (pr.w||0), 0);
                const tsv = rows.reduce((s, pr) => s + (pr.sv||0), 0);
                const tsa = rows.reduce((s, pr) => s + (pr.sa||0), 0);
                const tga = rows.reduce((s, pr) => s + (pr.ga||0), 0);
                const svpPct = tsa > 0 ? (tsv/tsa*100).toFixed(1)+'%' : '—';
                const gaaVal = tgp > 0 ? (tga/tgp).toFixed(2) : '—';
                return [
                  `${r.dv || '?'} Div  ·  ${lbl}: ${tgp} GP  ${tw} W`,
                  `SV% ${svpPct}   GAA ${gaaVal}`,
                ];
              }
              const tgp  = rows.reduce((s, pr) => s + (pr.gp||0), 0);
              const tg   = rows.reduce((s, pr) => s + (pr.g||0), 0);
              const ta   = rows.reduce((s, pr) => s + (pr.a||0), 0);
              const tpts = tg + ta;
              const ppg  = tgp > 0 ? (tpts / tgp).toFixed(2) : '—';
              return [
                `${r.dv || '?'} Div  ·  ${lbl}: ${tgp} GP  ${tpts} PTS`,
                `${tg} G  ${ta} A  ${ppg} PPG`,
              ];
            }
          }
        }
      },
      scales: {
        x: {
          title: { display: true, color: '#94a3b8', font: { size: 11, weight: 600 },
                   text: isGoalies ? 'Save Percentage' : 'Goals per Game' },
          grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8',
            callback: isGoalies ? v => (v*100).toFixed(0)+'%' : v => v },
          reverse: false,
        },
        y: {
          title: { display: true, color: '#94a3b8', font: { size: 11, weight: 600 },
                   text: isGoalies ? 'Goals Against Average' : 'Assists per Game' },
          grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' },
          reverse: isGoalies,
        },
      },
    },
    plugins: [{
      id: 'medLines',
      beforeDatasetsDraw(chart) {
        const { ctx, scales: { x, y }, chartArea: ca } = chart;
        if (!ca) return;
        ctx.save();
        ctx.strokeStyle = 'rgba(148,163,184,0.28)';
        ctx.lineWidth = 1; ctx.setLineDash([3,4]);
        const px = x.getPixelForValue(medX);
        ctx.beginPath(); ctx.moveTo(px, ca.top); ctx.lineTo(px, ca.bottom); ctx.stroke();
        const py = y.getPixelForValue(medY);
        ctx.beginPath(); ctx.moveTo(ca.left, py); ctx.lineTo(ca.right, py); ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = 'rgba(148,163,184,0.4)'; ctx.font = '10px system-ui';
        if (isGoalies) {
          ctx.fillText('Elite goalies', ca.right - 90, ca.top + 14);
          ctx.fillText('High-scoring, low save', ca.right - 140, ca.bottom - 6);
          ctx.fillText('Stingy, softer shots', ca.left + 6, ca.top + 14);
          ctx.fillText('High GAA, low SV%', ca.left + 6, ca.bottom - 6);
        } else {
          ctx.fillText('Two-way scorers', ca.right - 110, ca.top + 14);
          ctx.fillText('Pure shooters', ca.right - 90, ca.bottom - 6);
          ctx.fillText('Playmakers', ca.left + 6, ca.top + 14);
          ctx.fillText('Lower output', ca.left + 6, ca.bottom - 6);
        }
        ctx.restore();
      }
    }],
  });
}

// ── Populate scatter season dropdown ──────────────────────────────────────────
(function buildSeasonDropdown() {
  const sel = document.getElementById('scatter-season');
  DATA.scatterSeasons.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s.id; opt.textContent = s.name;
    sel.appendChild(opt);
  });
})();

// ── Bootstrap ────────────────────
(function() {
  const firstBtn = document.querySelector('#tab-alltime .sub-tab.active');
  if (firstBtn) showAllTimeList('points', firstBtn);
  renderTeams();
  // Apply initial mode (skaters) to set nav visibility correctly
  document.querySelectorAll('[data-skateronly]').forEach(el => el.style.display = '');
  document.querySelectorAll('[data-goalieonly]').forEach(el => el.style.display = 'none');
})();
</script>
</body>
</html>"""

with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Dashboard written to {OUT_PATH}')
