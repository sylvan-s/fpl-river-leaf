#!/usr/bin/env python3
"""Offline tests for fpl_research_mcp - no network required.

Injects synthetic payloads matching the real FPL schema into the module cache,
so the join/delta/FDR logic is exercised without hitting the API.
Run:  python3 test_fpl_mcp.py
"""
import datetime as _dt
import sys
import time

import fpl_research_mcp as m

TEAMS = [
    {"id": 1, "name": "Arsenal", "short_name": "ARS"},
    {"id": 14, "name": "Liverpool", "short_name": "LIV"},
    {"id": 15, "name": "Man City", "short_name": "MCI"},
    {"id": 7, "name": "Coventry City", "short_name": "COV"},
]

# delta = (G+A) - xGI
ELEMENTS = [
    # heavy UNDERperformer -> should top the BUY list (delta -4.10)
    {"id": 1, "web_name": "Watkins", "team": 1, "element_type": 4, "now_cost": 80,
     "minutes": 900, "goals_scored": 2, "assists": 1, "expected_goals": 5.1,
     "expected_assists": 2.0, "expected_goal_involvements": 7.1, "total_points": 40,
     "form": "3.2", "selected_by_percent": "12.5", "status": "a", "news": "",
     "ict_index": "80.0", "starts": 10, "chance_of_playing_next_round": None},
    # heavy OVERperformer -> should top the SELL list (delta +3.80)
    {"id": 2, "web_name": "Thiago", "team": 15, "element_type": 4, "now_cost": 80,
     "minutes": 900, "goals_scored": 8, "assists": 2, "expected_goals": 5.0,
     "expected_assists": 1.2, "expected_goal_involvements": 6.2, "total_points": 70,
     "form": "6.0", "selected_by_percent": "30.0", "status": "a", "news": "",
     "ict_index": "120.0", "starts": 10, "chance_of_playing_next_round": None},
    # injured, and below the minutes floor
    {"id": 3, "web_name": "Ekitike", "team": 14, "element_type": 4, "now_cost": 75,
     "minutes": 90, "goals_scored": 0, "assists": 0, "expected_goals": 0.9,
     "expected_assists": 0.1, "expected_goal_involvements": 1.0, "total_points": 2,
     "form": "0.5", "selected_by_percent": "3.0", "status": "i",
     "news": "Achilles injury - unknown return date", "ict_index": "5.0",
     "starts": 1, "chance_of_playing_next_round": 0},
    # midfielder, mild underperformer
    {"id": 4, "web_name": "Rice", "team": 1, "element_type": 3, "now_cost": 75,
     "minutes": 900, "goals_scored": 3, "assists": 2, "expected_goals": 3.0,
     "expected_assists": 2.9, "expected_goal_involvements": 5.9, "total_points": 55,
     "form": "4.4", "selected_by_percent": "18.0", "status": "a", "news": "",
     "ict_index": "95.0", "starts": 10, "chance_of_playing_next_round": None},
    # doubtful flag
    {"id": 5, "web_name": "Sesko", "team": 15, "element_type": 4, "now_cost": 70,
     "minutes": 400, "goals_scored": 1, "assists": 0, "expected_goals": 1.1,
     "expected_assists": 0.2, "expected_goal_involvements": 1.3, "total_points": 15,
     "form": "1.5", "selected_by_percent": "5.0", "status": "d",
     "news": "Shin injury - 75% chance of playing", "ict_index": "30.0",
     "starts": 4, "chance_of_playing_next_round": 75},
]

FUTURE = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=10))
EVENTS = [
    {"id": 1, "name": "Gameweek 1", "deadline_time": FUTURE.strftime("%Y-%m-%dT%H:%M:%SZ"),
     "is_next": True, "is_current": False, "finished": False, "average_entry_score": 0},
    {"id": 2, "name": "Gameweek 2", "deadline_time": "2026-08-28T17:30:00Z",
     "is_next": False, "is_current": False, "finished": False, "average_entry_score": 0},
]

# ARS: GW1 easy(2), GW2 DOUBLE (2 + 3). LIV: GW1 only -> blank GW2.
FIXTURES = [
    {"event": 1, "team_h": 1, "team_a": 7, "team_h_difficulty": 2, "team_a_difficulty": 5},
    {"event": 1, "team_h": 15, "team_a": 14, "team_h_difficulty": 4, "team_a_difficulty": 3},
    {"event": 2, "team_h": 1, "team_a": 15, "team_h_difficulty": 2, "team_a_difficulty": 4},
    {"event": 2, "team_h": 7, "team_a": 1, "team_h_difficulty": 5, "team_a_difficulty": 3},
]

BOOT = {"teams": TEAMS, "elements": ELEMENTS, "events": EVENTS}


def seed():
    now = time.time()
    m._cache.clear()
    m._cache["/bootstrap-static/"] = (now, BOOT)
    m._cache["/fixtures/?future=1"] = (now, FIXTURES)


FAILS = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILS.append(label)


print("== get_deadline ==")
seed()
out = m.get_deadline()
check("names next GW", "Gameweek 1" in out, out)
check("shows countdown", "away" in out, out)
check("flags chip set 1 expiry", "Chip set 1 expires" in out, out)

print("\n== xgi_delta ==")
seed()
out = m.xgi_delta(position="MID,FWD", min_minutes=270)
buy_sec = out.split("OVERPERFORMERS")[0]
sell_sec = out.split("OVERPERFORMERS")[1]
check("Watkins in BUY section", "Watkins" in buy_sec, buy_sec)
check("Thiago in SELL section", "Thiago" in sell_sec, sell_sec)
check("Watkins delta -4.10", "-4.10" in out, out)
check("Thiago delta +3.80", "+3.80" in out, out)
check("min_minutes filters Ekitike out", "Ekitike" not in out)
seed()
check("max_price filters", "Thiago" not in m.xgi_delta(position="FWD", min_minutes=270, max_price=7.5))
seed()
check("position filter excludes MID", "Rice" not in m.xgi_delta(position="FWD", min_minutes=270))

print("\n== fixture_difficulty ==")
seed()
out = m.fixture_difficulty(next_n=2)
check("detects ARS double", "DGW GW2" in out, out)
check("detects LIV blank", "BLANK GW2" in out, out)
check("no longer reports a single FDR average", "AvgFDR" not in out, out)
check("reports TWO position-split columns", "ATT x" in out and "DEF x" in out, out)
check("labels the directions explicitly",
      "HIGHER is better" in out and "LOWER is better" in out, out)
check("names the best run for each position",
      "Best run for ATTACKERS" in out and "Best run for DEFENDERS" in out, out)
check("states it no longer uses FDR", "NOT" in out and "FDR" in out, out)
# FDR must be gone from the source entirely - one model, no contradictions
_src = open(m.__file__).read()
check("FDR fields unreferenced anywhere in the server",
      "team_h_difficulty" not in _src and "team_a_difficulty" not in _src)

print("\n== injury_report ==")
seed()
out = m.injury_report()
check("lists injured", "Ekitike" in out and "INJURED" in out, out)
check("lists doubtful", "Sesko" in out and "DOUBTFUL" in out, out)
check("omits available", "Watkins" not in out, out)
check("shows odds", "75%" in out, out)
seed()
check("name filter works", "Watkins" in m.injury_report(names="Watkins"))

print("\n== compare_players ==")
seed()
out = m.compare_players("Watkins,Thiago")
check("both present", "Watkins" in out and "Thiago" in out, out)
check("delta row computed", "-4.10" in out and "+3.80" in out, out)

print("\n== analyze_players ==")
seed()
out = m.analyze_players(position="FWD", sort_by="points", available_only=True)
check("excludes flagged when available_only", "Ekitike" not in out and "Sesko" not in out, out)
check("orders by points", out.index("Thiago") < out.index("Watkins"), out)
seed()
check("ownership filter", "Thiago" not in m.analyze_players(position="FWD", max_ownership=15.0))

print("\n== escalation_check ==")
# Baseline: GW1 next, GW2 has an ARS double and a LIV blank -> NEXT-gameweek warning.
seed()
m._cache["/entry/1041614/event/1/picks/"] = (time.time(), {"picks": []})
out = m.escalation_check(horizon=2)
check("escalates on next-GW double", "RUN WITH OPUS" in out, out)
check("names the double", "DOUBLE" in out and "GW2" in out, out)
check("names the blank", "BLANK" in out, out)
check("labels it NEXT gameweek", "NEXT gameweek" in out, out)

# Quiet week: every team plays exactly once in each GW -> no escalation.
seed()
m._cache["/fixtures/?future=1"] = (time.time(), [
    {"event": 1, "team_h": 1, "team_a": 7, "team_h_difficulty": 2, "team_a_difficulty": 5},
    {"event": 1, "team_h": 15, "team_a": 14, "team_h_difficulty": 4, "team_a_difficulty": 3},
    {"event": 2, "team_h": 7, "team_a": 1, "team_h_difficulty": 5, "team_a_difficulty": 3},
    {"event": 2, "team_h": 14, "team_a": 15, "team_h_difficulty": 3, "team_a_difficulty": 4},
])
m._cache["/entry/1041614/event/1/picks/"] = (time.time(), {"picks": []})
out = m.escalation_check(horizon=2)
check("no escalation on a routine week", "SONNET IS FINE" in out, out)
check("reports zero signals", "none" in out.lower() or "Escalation score 0" in out, out)

# Squad with 4 flagged players -> wildcard territory.
seed()
m._cache["/fixtures/?future=1"] = (time.time(), [
    {"event": 1, "team_h": 1, "team_a": 7, "team_h_difficulty": 2, "team_a_difficulty": 5},
    {"event": 2, "team_h": 7, "team_a": 1, "team_h_difficulty": 5, "team_a_difficulty": 3},
])
for e in m._cache["/bootstrap-static/"][1]["elements"]:
    e["status"] = "i"
m._cache["/entry/1041614/event/1/picks/"] = (time.time(), {
    "picks": [{"element": i, "position": i, "is_captain": False, "is_vice_captain": False}
              for i in range(1, 6)]})
out = m.escalation_check(horizon=1)
check("flags injury cluster as wildcard territory", "Wildcard territory" in out, out)


print("\n== D7 opponent adjustment ==")
_T=[{"id":1,"name":"MyTeam","short_name":"MYT"},{"id":2,"name":"LeakyPotent","short_name":"LKP"},
    {"id":3,"name":"SolidBlunt","short_name":"SLD"},{"id":4,"name":"Average","short_name":"AVG"}]
_G=20
_EV=[{"id":i,"deadline_time":"2020-01-01T00:00:00Z","finished":True,"is_next":False}
     for i in range(1,_G+1)]
_EV.append({"id":99,"deadline_time":"2030-01-01T00:00:00Z","finished":False,"is_next":True})
def _p(i,n,t,et,xg,xa,xgc,mins=_G*90):
    return {"id":i,"web_name":n,"team":t,"element_type":et,"now_cost":60,"minutes":mins,
      "starts":_G,"expected_goals":xg,"expected_assists":xa,"expected_goal_involvements":xg+xa,
      "goals_scored":int(xg),"assists":int(xa),"bonus":15,
      "expected_goals_conceded":str(xgc*mins/90),"goals_conceded":20,"clean_sheets":8,
      "selected_by_percent":"10.0","status":"a","clearances_blocks_interceptions":0,
      "tackles":0,"recoveries":0,"penalties_order":None,"direct_freekicks_order":None,
      "corners_and_indirect_freekicks_order":None}
_els=[_p(1,"Striker",1,4,14.0,4.0,1.3), _p(2,"Defender",1,2,1.5,1.5,1.3)]
for _tid,(_xg,_xgc) in {2:(2.2,1.9),3:(0.8,0.7),4:(1.35,1.35)}.items():
    for _j in range(6):
        _els.append(_p(100+_tid*10+_j,f"T{_tid}p{_j}",_tid,3,_xg*_G/6,2.0,_xgc))

def _run(fx):
    m._cache["/fixtures/?future=1"]=(time.time(),fx)
    m._cache["/bootstrap-static/"]=(time.time(),{"teams":_T,"elements":_els,"events":_EV})
    m._contam_cache=m._intel_cache=m._strength_cache=None
    m._priors_cache={"players":{}}     # isolate from the real priors snapshot
    out=m.captaincy_odds("Striker,Defender"); r={}
    for l in out.split("\n")[3:8]:
        f=l.split()
        if f and f[0] in ("Striker","Defender"):
            r[f[0]]={"exp":float(f[4]),"haul":float(f[5].rstrip("%")),
                     "blank":float(f[6].rstrip("%"))}
    return r

_a=_run([{"event":99,"team_h":1,"team_a":2}])   # home v leaky+potent
_b=_run([{"event":99,"team_h":2,"team_a":1}])   # away at same
_c=_run([{"event":99,"team_h":1,"team_a":3}])   # home v solid+blunt
_d=_run([{"event":99,"team_h":1,"team_a":2},{"event":99,"team_h":1,"team_a":4}])
_e=_run([])                                      # blank

check("home beats away", _a["Striker"]["exp"] > _b["Striker"]["exp"])
check("leaky opponent helps the attacker", _a["Striker"]["exp"] > _c["Striker"]["exp"])
check("potent opponent hurts the defender", _a["Defender"]["exp"] < _c["Defender"]["exp"])
check("...and raises his blank risk", _a["Defender"]["blank"] > _c["Defender"]["blank"])
check("ONE fixture, opposite effects on attacker vs defender",
      _a["Striker"]["exp"] > _c["Striker"]["exp"] and _a["Defender"]["exp"] < _c["Defender"]["exp"])
check("DGW roughly doubles expectation", _d["Striker"]["exp"] > _a["Striker"]["exp"]*1.5)
check("DGW raises P(haul) - Triple Captain case", _d["Striker"]["haul"] > _a["Striker"]["haul"])
check("blank gameweek scores zero",
      _e["Striker"]["exp"] == 0.0 and _e["Striker"]["blank"] == 100.0)
check("home/away factors are symmetric around 1.0",
      abs((m.HOME_FACTOR + m.AWAY_FACTOR)/2 - 1.0) < 0.02)


print("\n== fixture_outlook (5-GW window, position-split) ==")
_FT=[{"id":1,"name":"EasyRun","short_name":"EZY"},{"id":2,"name":"HardRun","short_name":"HRD"},
     {"id":3,"name":"Leaky","short_name":"LKY"},{"id":4,"name":"Solid","short_name":"SLD"}]
_FG=20
_FEV=[{"id":i,"deadline_time":"2020-01-01T00:00:00Z","finished":True,"is_next":False}
      for i in range(1,_FG+1)]
_FEV+=[{"id":_FG+i,"deadline_time":"2030-01-01T00:00:00Z","finished":False,
        "is_next":(i==1)} for i in range(1,6)]
def _fp(i,n,t,et,xgi,xgc,mins=_FG*90):
    return {"id":i,"web_name":n,"team":t,"element_type":et,"now_cost":60,"minutes":mins,
      "starts":_FG,"expected_goals":xgi*0.6,"expected_assists":xgi*0.4,
      "expected_goal_involvements":xgi,"goals_scored":5,"assists":3,"bonus":15,
      "expected_goals_conceded":str(xgc*mins/90),"goals_conceded":20,"clean_sheets":8,
      "selected_by_percent":"10.0","status":"a","clearances_blocks_interceptions":0,
      "tackles":0,"recoveries":0,"penalties_order":None,"direct_freekicks_order":None,
      "corners_and_indirect_freekicks_order":None}
_fels=[_fp(1,"AttEasy",1,3,12.0,1.3), _fp(2,"AttHard",2,3,12.0,1.3),
       _fp(3,"DefEasy",1,2,2.0,1.3),  _fp(4,"DefHard",2,2,2.0,1.3)]
for _t,(_xg,_xgc) in {3:(2.2,1.9),4:(0.8,0.7)}.items():
    for _j in range(6): _fels.append(_fp(200+_t*10+_j,f"T{_t}p{_j}",_t,3,_xg*_FG/6,_xgc))
_FFX=[]
for _gw in range(21,25):
    _FFX.append({"event":_gw,"team_h":1,"team_a":3})   # EZY always v Leaky
    _FFX.append({"event":_gw,"team_h":2,"team_a":4})   # HRD always v Solid

def _fseed(fx=None):
    m._cache["/fixtures/?future=1"]=(time.time(), fx if fx is not None else _FFX)
    m._cache["/bootstrap-static/"]=(time.time(),{"teams":_FT,"elements":_fels,"events":_FEV})
    m._contam_cache=m._intel_cache=m._strength_cache=None
    m._priors_cache={"players":{}}

_fseed()
_o=m.fixture_outlook("AttEasy,AttHard,DefEasy,DefHard", next_n=4)
_v={}
for _l in _o.split("\n"):
    _f=_l.split()
    if _f and _f[0] in ("AttEasy","AttHard","DefEasy","DefHard"):
        _v[_f[0]]={"xgi":float(_f[5]),"cs":float(_f[6])}
check("attacker: leaky opponents raise expected xGI", _v["AttEasy"]["xgi"] > _v["AttHard"]["xgi"])
check("defender: the SAME run lowers expected clean sheets",
      _v["DefEasy"]["cs"] < _v["DefHard"]["cs"])
check("ONE fixture run, opposite verdicts by position",
      _v["AttEasy"]["xgi"] > _v["AttHard"]["xgi"] and _v["DefEasy"]["cs"] < _v["DefHard"]["cs"])

_fseed([{"event":21,"team_h":1,"team_a":3},{"event":21,"team_h":1,"team_a":4},
        {"event":22,"team_h":1,"team_a":3}])
_o=m.fixture_outlook("AttEasy", next_n=3)
check("counts a DOUBLE gameweek as two fixtures", "DGW GW21" in _o)
check("counts a BLANK gameweek as zero", "BLANK GW23" in _o)
check("sums FIXTURES not gameweeks (3 fixtures over 3 GWs)",
      any(_l.split()[4] == "3" for _l in _o.split("\n") if _l.startswith("AttEasy")))

_fseed()
_o=m.fixture_outlook(compare="DefEasy>DefHard", next_n=4)
check("head-to-head shows OUT, IN and NET", all(s in _o for s in ("OUT","IN","NET")))
check("head-to-head warns on mismatched positions",
      "not comparable" in m.fixture_outlook(compare="AttEasy>DefHard", next_n=4))
check("warns that fixtures break ties rather than make the case", "TIMING" in _o)


print("\n== local history cache ==")
import os as _os2, sqlite3 as _sq, tempfile as _tf
_REAL_DB = m._DB_PATH
m._DB_PATH = _os2.path.join(_tf.mkdtemp(), "test_cache.sqlite")   # never touch the real one

_CALLS = {"n": 0}
_orig_get = m._get
def _counting_get(path, ttl=900):
    if "element-summary" in path:
        _CALLS["n"] += 1
        return {"history": [
            {"round": r, "minutes": 90, "total_points": 5 + r, "goals_scored": 1,
             "assists": 0, "bonus": 1, "bps": 20, "expected_goals": 0.4,
             "expected_assists": 0.2, "expected_goal_involvements": 0.6,
             "expected_goals_conceded": 1.2, "clean_sheets": 0, "goals_conceded": 1,
             "saves": 0, "clearances_blocks_interceptions": 3, "tackles": 2,
             "recoveries": 4, "starts": 1, "was_home": r % 2, "opponent_team": 5}
            for r in range(1, 6)]}
    return _orig_get(path, ttl)
m._get = _counting_get

def _cseed(fin_to):
    ev = [{"id": i, "finished": i <= fin_to, "data_checked": i <= fin_to,
           "is_next": (i == fin_to + 1), "deadline_time": "2026-01-01T00:00:00Z"}
          for i in range(1, 6)]
    m._cache.clear()
    m._cache["/bootstrap-static/"] = (time.time(), {
        "teams": [{"id": 1, "short_name": "AAA", "name": "A"}],
        "elements": [], "events": ev})

_cseed(3)                                   # GW1-3 final, GW4-5 live
_h = m._player_history(1); _c1 = _CALLS["n"]
check("first read costs one API call", _c1 == 1)

_cseed(3)                                   # wipes the in-memory cache
_h2 = m._player_history(1)
check("second read served from SQLite, no API call", _CALLS["n"] == _c1)
check("returns only FINISHED gameweeks from cache", len(_h2) == 3)
_con = _sq.connect(m._DB_PATH)
_r = [x[0] for x in _con.execute("SELECT DISTINCT round FROM player_gw ORDER BY round")]
check("live gameweeks are NEVER persisted", _r == [1, 2, 3], str(_r))
_v = _con.execute("SELECT total_points,expected_goal_involvements,tackles "
                  "FROM player_gw WHERE player_id=1 AND round=2").fetchone()
check("values survive the round trip intact", _v == (7.0, 0.6, 2.0), str(_v))
_con.close()

_cseed(4)                                   # GW4 now final
_before = _CALLS["n"]; _h3 = m._player_history(1)
check("re-fetches once a newer gameweek is final", _CALLS["n"] == _before + 1)
_con = _sq.connect(m._DB_PATH)
_r = [x[0] for x in _con.execute("SELECT DISTINCT round FROM player_gw ORDER BY round")]
check("stores the newly-final gameweek, still not the live one", _r == [1, 2, 3, 4], str(_r))
_con.close()

_cseed(0)                                   # pre-season: nothing final
check("pre-season stores nothing and says so",
      "nothing to cache" in m.cache_history(refresh=True).lower())

m._get = _orig_get
m._DB_PATH = _REAL_DB

print("\n== player_gw schema migration (26 Aug 2026 card/own-goal/pen-miss columns) ==")
_mig_db = _os2.path.join(_tf.mkdtemp(), "old_schema.sqlite")
_OLD_COLS = (  # the pre-26-Aug-2026 column set, deliberately hand-copied here
    "minutes", "total_points", "goals_scored", "assists", "bonus", "bps",
    "expected_goals", "expected_assists", "expected_goal_involvements",
    "expected_goals_conceded", "clean_sheets", "goals_conceded", "saves",
    "clearances_blocks_interceptions", "tackles", "recoveries", "starts",
    "was_home", "opponent_team",
)
_conn = _sq.connect(_mig_db)
_old_cols_sql = ",\n    ".join(f"{c} REAL" for c in _OLD_COLS)
_conn.execute(f"""
    CREATE TABLE player_gw (
        player_id INTEGER NOT NULL, round INTEGER NOT NULL,
        {_old_cols_sql}, fetched_utc TEXT, PRIMARY KEY (player_id, round))""")
_conn.execute("""
    CREATE TABLE player_sync (
        player_id INTEGER PRIMARY KEY, synced_to INTEGER NOT NULL, fetched_utc TEXT)""")
_conn.execute("INSERT INTO player_gw (player_id, round, minutes, total_points) VALUES (1, 1, 90, 6)")
_conn.execute("INSERT INTO player_sync VALUES (1, 3, '2026-08-01T00:00:00Z')")
_conn.commit()
_conn.close()

m._DB_PATH = _mig_db
_conn = m._db()                              # triggers the migration
check("new columns added to an old-schema database",
      {"yellow_cards", "red_cards", "own_goals", "penalties_missed"}
      <= {r[1] for r in _conn.execute("PRAGMA table_info(player_gw)")})
check("pre-existing row survives the ALTER, new columns NULL",
      _conn.execute("SELECT minutes, total_points, yellow_cards FROM player_gw "
                    "WHERE player_id=1 AND round=1").fetchone() == (90.0, 6.0, None))
check("player_sync cleared so the next fetch backfills the new columns",
      _conn.execute("SELECT COUNT(*) FROM player_sync").fetchone()[0] == 0)
_conn.close()

_conn2 = m._db()                             # re-run: nothing missing now
check("re-running the migration a second time is a no-op (idempotent)",
      _conn2.execute("SELECT COUNT(*) FROM player_gw").fetchone()[0] == 1)
_conn2.close()
m._DB_PATH = _REAL_DB

print("\n== entry history cache (actual FPL points) ==")
m._DB_PATH = _os2.path.join(_tf.mkdtemp(), "test_entry_cache.sqlite")
_ENTRY_CALLS = {"n": 0}
_orig_get2 = m._get


def _entry_counting_get(path, ttl=900):
    if "/event/" in path and "/picks/" in path:
        _ENTRY_CALLS["n"] += 1
        gw = int(path.split("/event/")[1].split("/picks")[0])
        return {"entry_history": {
            "event": gw, "points": 40 + gw,
            "total_points": sum(40 + g for g in range(1, gw + 1)),
            "bank": 0, "value": 1000, "event_transfers": 0,
            "event_transfers_cost": 0, "points_on_bench": 5,
            "overall_rank": 100000 - gw * 10}}
    return _orig_get2(path, ttl)


m._get = _entry_counting_get

_cseed(3)                                   # GW1-3 final, GW4-5 live (reuses seed above)
_rows, _errs = m._entry_history(9999)
check("first read costs one API call per finished GW", _ENTRY_CALLS["n"] == 3)
check("no fetch errors", _errs == [])
check("returns rows for finished GWs only", [r["event"] for r in _rows] == [1, 2, 3])
check("total_points is FPL's own cumulative figure, not recomputed here",
      _rows[-1]["total_points"] == sum(40 + g for g in range(1, 4)))

_before = _ENTRY_CALLS["n"]
_rows2, _ = m._entry_history(9999)
check("second read served from SQLite, no API call", _ENTRY_CALLS["n"] == _before)
check("still three rows", len(_rows2) == 3)

_con = _sq.connect(m._DB_PATH)
_r = [x[0] for x in _con.execute(
    "SELECT DISTINCT event FROM entry_gw WHERE entry_id=9999 ORDER BY event")]
check("live gameweeks are NEVER persisted for entries either", _r == [1, 2, 3], str(_r))
_con.close()

_cseed(4)                                   # GW4 now final
_before = _ENTRY_CALLS["n"]
_rows3, _ = m._entry_history(9999)
check("re-fetches once a newer gameweek is final", _ENTRY_CALLS["n"] == _before + 1)
check("four rows now cached", len(_rows3) == 4)

_snap_path = _os2.path.join(_tf.mkdtemp(), "entry_summary.json")
_orig_snapshot_path = m._ENTRY_SNAPSHOT_PATH
m._ENTRY_SNAPSHOT_PATH = _snap_path
_txt = m.entry_summary(9999)
check("reports total points", f"Total points {_rows3[-1]['total_points']:.0f}" in _txt)
check("reports average per gameweek", "average" in _txt.lower())
check("reports the next deadline", "Next deadline" in _txt)

import json as _json3
check("writes the dashboard snapshot file", _os2.path.exists(_snap_path))
_snap = _json3.load(open(_snap_path))
check("snapshot total matches cached total", _snap["total_points"] == _rows3[-1]["total_points"])
check("snapshot gws_played matches row count", _snap["gws_played"] == len(_rows3))
check("snapshot avg is total/gws",
      abs(_snap["avg_per_gw"] - _rows3[-1]["total_points"] / len(_rows3)) < 0.05)
check("snapshot carries the next gameweek id", _snap["next_gw"] == 5)

_cseed(0)                                   # pre-season: nothing final, nothing to summarise
if _os2.path.exists(_snap_path):
    _os2.remove(_snap_path)
m._DB_PATH = _os2.path.join(_tf.mkdtemp(), "test_entry_cache_empty.sqlite")
_txt2 = m.entry_summary(9999)
check("pre-season entry_summary says nothing cached yet",
      "no finished-gameweek" in _txt2.lower())
check("pre-season does not write a snapshot", not _os2.path.exists(_snap_path))

m._ENTRY_SNAPSHOT_PATH = _orig_snapshot_path
m._get = _orig_get2
m._DB_PATH = _REAL_DB

print("\n== availability and suspension risk ==")
# Minutes are the dominant source of blanks. These two mechanisms are distinct
# and the tests exist mainly to stop them being conflated again.
check("available -> full P(start)", m._availability({"status": "a"})[0] == 1.0)
check("suspended -> P(start) 0", m._availability({"status": "s"})[0] == 0.0)
check("injured -> P(start) 0", m._availability({"status": "i"})[0] == 0.0)
check("unavailable -> P(start) 0", m._availability({"status": "u"})[0] == 0.0)
check("doubtful scales by chance",
      m._availability({"status": "d", "chance_of_playing_next_round": 25})[0] == 0.25)
check("doubtful with no percentage falls back to 0.5",
      m._availability({"status": "d", "chance_of_playing_next_round": None})[0] == 0.5)

_b = {"minutes": 2700}                       # 30 full matches
check("picks the 5-yellow threshold before GW19",
      m._suspension({**_b, "yellow_cards": 0}, 5)["threshold"] == 5)
check("one booking away is flagged to_go=1",
      m._suspension({**_b, "yellow_cards": 4}, 5)["to_go"] == 1)
check("5-yellow threshold lapses after GW19",
      m._suspension({**_b, "yellow_cards": 4}, 25)["threshold"] == 10)
check("second threshold is a 2-match ban",
      m._suspension({**_b, "yellow_cards": 9}, 20)["matches"] == 2)
check("already suspended reads BANNED",
      m._suspension({**_b, "yellow_cards": 5, "status": "s"}, 6)["label"] == "BANNED")

# THE important one: a player cannot cross two thresholds in a single match, so
# anything further than one booking away carries no ban risk for the next game.
check("one away -> non-zero ban risk",
      m._suspension({**_b, "yellow_cards": 4}, 5)["p_ban"] > 0)
check("more than one away -> zero ban risk",
      m._suspension({**_b, "yellow_cards": 2}, 5)["p_ban"] == 0.0)
check("a player who will not start cannot be booked",
      m._suspension({**_b, "yellow_cards": 4}, 5, p_start=0.0)["p_ban"] == 0.0)
check("lower P(start) lowers ban risk",
      m._suspension({**_b, "yellow_cards": 4}, 5, p_start=0.5)["p_ban"]
      < m._suspension({**_b, "yellow_cards": 4}, 5, p_start=1.0)["p_ban"])
check("all thresholds passed reads '-'",
      m._suspension({**_b, "yellow_cards": 16}, 38)["label"] == "-")
check("zero minutes does not divide by zero",
      m._suspension({"minutes": 0, "yellow_cards": 0}, 1)["p_ban"] == 0.0)

print("\n== priors snapshot v2 ==")
check("v2 path is separate from v1", m._PRIORS_PATH_V2 != m._PRIORS_PATH)
check("v2 preferred over v1 on load", "_PRIORS_PATH_V2, _PRIORS_PATH"
      in open(m.__file__).read())
_keep_src = open(m.__file__).read()
for _f in ("yellow_cards", "red_cards", "saves", "penalties_saved", "bps"):
    check(f"snapshot captures {_f}", f'"{_f}"' in _keep_src)

print("\n== k estimation: dispersion by metric ==")
# REGRESSION TEST for the 8 Aug 2026 bug. The Poisson sampling-variance model is
# right for counts and badly wrong for the xG family, where each unit is a sum of
# ~0.11 probabilities rather than a whole event. It drove between-variance
# negative and pinned k to its cap, which would have frozen every attacker on his
# prior for a whole season without ever showing an error.
import random as _rnd
_rnd.seed(7)

# xGI-like: small continuous rates, genuine spread between players.
_xgi = [(max(_rnd.gauss(0.30, 0.14), 0.01), _rnd.uniform(10, 35)) for _ in range(160)]
_k_poisson = m._estimate_k(_xgi, 1.0)
_k_fixed = m._estimate_k(_xgi, m.DISPERSION["expected_goal_involvements"])
check("Poisson model degenerates on xGI-like data", m._k_degenerate(_k_poisson),
      f"k={_k_poisson}")
check("dispersion correction rescues it", not m._k_degenerate(_k_fixed), f"k={_k_fixed}")
check("corrected k converges inside a 38-game season", _k_fixed < 38, f"k={_k_fixed}")

# Count-like: large integer-ish rates. Poisson is correct here and must not move.
_cnt = [(max(_rnd.gauss(7.7, 1.9), 0.1), _rnd.uniform(10, 35)) for _ in range(160)]
check("counts are unaffected by the correction",
      abs(m._estimate_k(_cnt, 1.0) - m._estimate_k(_cnt, m.DISPERSION["cbit"])) < 1e-9)
check("count k stays small (individual data trusted fast)",
      m._estimate_k(_cnt, m.DISPERSION["cbit"]) < 10)

check("xG family carries a sub-1 dispersion",
      all(m.DISPERSION[k] < 1.0 for k in
          ("expected_goals", "expected_assists", "expected_goal_involvements")))
check("count metrics carry dispersion 1.0",
      m.DISPERSION["cbit"] == 1.0 and m.DISPERSION["cbirt"] == 1.0)

check("_k_degenerate spots every fallback", all(
    m._k_degenerate(v) for v in (10.0, 40.0, 60.0)))
check("_k_degenerate passes a derived value", not m._k_degenerate(15.5))
check("thin population still returns the safe default",
      m._estimate_k([(0.3, 10.0)] * 5, 0.11) == 10.0)
check("identical players shrink hard rather than crash",
      m._estimate_k([(0.3, 10.0)] * 40, 0.11) == 40.0)
# Parse rather than grep: string counting picked up comment mentions and the
# definition itself, and reported a failure that was not real.
import ast as _ast
_calls = [n for n in _ast.walk(_ast.parse(open(m.__file__).read()))
          if isinstance(n, _ast.Call)
          and getattr(n.func, "id", None) == "_estimate_k"]
check("every _estimate_k call site passes a dispersion",
      len(_calls) >= 5 and all(len(c.args) >= 2 or
                               any(kw.arg in ("dispersion", "empirical_var")
                                   for kw in c.keywords) for c in _calls),
      f"{len(_calls)} call sites, arg counts {[len(c.args) for c in _calls]}")

print("\n== prior-season table ==")
import os as _os2
import sqlite3 as _sq2
import tempfile as _tf

_tmp = _tf.mkdtemp()
_pj = _os2.path.join(_tmp, "priors.json")
_pdb = _os2.path.join(_tmp, "t.sqlite")
import json as _json2
_json2.dump({
    "season_described": "2025/26", "captured_utc": "2026-08-07T23:25:33Z",
    "teams": {"1": "ARS", "14": "LIV"},
    "players": {
        "1": {"web_name": "Raya", "team": 1, "element_type": 1, "minutes": 3330,
              "starts": 37, "expected_goal_involvements": "0.07",
              "expected_goals_conceded": "27.56", "clearances_blocks_interceptions": 37,
              "tackles": 1, "recoveries": 304, "goals_scored": 0, "assists": 0,
              "selected_by_percent": "30.9", "clean_sheets": 19, "now_cost": 60},
        "2": {"web_name": "NoMins", "team": 14, "element_type": 3, "minutes": 0,
              "starts": 0, "expected_goal_involvements": "0.00",
              "expected_goals_conceded": "0.00", "clearances_blocks_interceptions": 0,
              "tackles": 0, "recoveries": 0, "goals_scored": 0, "assists": 0,
              "selected_by_percent": "0.1", "clean_sheets": 0, "now_cost": 45},
    }}, open(_pj, "w"))

_ov1, _ov2 = m._PRIORS_PATH, m._PRIORS_PATH_V2
m._PRIORS_PATH, m._PRIORS_PATH_V2 = _pj, _os2.path.join(_tmp, "absent.json")
_res = m._load_priors_db(_pdb)
check("loads the snapshot into SQLite", "PRIOR-SEASON TABLE LOADED" in _res)
check("reports v1 when v2 is absent", "v1 snapshot" in _res)
check("warns about the fields v1 lacks", "yellow_cards" in _res and "EMPTY" in _res)

_c2 = _sq2.connect(_pdb)
check("player_season populated", _c2.execute("SELECT COUNT(*) FROM player_season").fetchone()[0] == 2)
check("team_season populated", _c2.execute("SELECT COUNT(*) FROM team_season").fetchone()[0] == 2)
# Strings in the JSON must be cast, or every numeric comparison silently fails.
check("string decimals cast to REAL",
      _c2.execute("SELECT typeof(expected_goal_involvements) FROM player_season LIMIT 1").fetchone()[0] == "real")
# Season TOTALS must never land in player_gw - that would double-count aggregates.
check("season totals kept OUT of player_gw",
      _c2.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='player_gw'").fetchone()[0] == 0)
_r2 = _c2.execute("SELECT cbit90, n90 FROM v_player_season_rates WHERE player_id=1").fetchone()
check("view computes per-90 correctly", abs(_r2[0] - (38 / (3330 / 90.0))) < 1e-6, str(_r2))
check("zero-minute player yields NULL not a crash",
      _c2.execute("SELECT cbit90 FROM v_player_season_rates WHERE player_id=2").fetchone()[0] is None)
_c2.close()

m._load_priors_db(_pdb)                      # idempotency
_c2 = _sq2.connect(_pdb)
check("re-running does not duplicate rows",
      _c2.execute("SELECT COUNT(*) FROM player_season").fetchone()[0] == 2)
_c2.close()
m._PRIORS_PATH, m._PRIORS_PATH_V2 = _ov1, _ov2

check("db defaults outside the synced folder", "google" not in m._DB_PATH.lower()
      and "CloudStorage" not in m._DB_PATH)

print("\n== read-only guarantee ==")
src = open(m.__file__).read()
check("no HTTP writes in source", not any(f"httpx.{v}(" in src for v in ("post", "put", "patch", "delete")))
check("only GET used", "httpx.get(" in src)

print("\n" + ("ALL TESTS PASSED" if not FAILS else f"{len(FAILS)} FAILURE(S): {FAILS}"))
sys.exit(1 if FAILS else 0)
