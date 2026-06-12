"""ESPN results overlay — timely scores + goal events for the openfootball skeleton.

openfootball gives the fixture structure (our team names, groups, schedule, bracket
placeholders) but lags badly on live results. ESPN's public-but-undocumented soccer API is
far more timely, so we overlay its scores and goal-by-goal events onto the openfootball
matches. Results are keyed on the real team pairing, so unresolved knockout slots (which
have no real teams yet) are simply left untouched until the teams are known.

Unofficial source: no key, but undocumented and not guaranteed stable. If it ever fails we
fall back gracefully to whatever openfootball has (see data._overlay_espn).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import requests

ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"

# ESPN spells a handful of teams differently — map them to our (openfootball) names.
ESPN_TO_OF = {
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",
    "Congo DR": "DR Congo",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
    "United States": "USA",
}


def _name(espn_name: str) -> str:
    return ESPN_TO_OF.get(espn_name, espn_name)


def _int(x) -> int:
    try:
        return int(str(x).strip())
    except (ValueError, TypeError):
        return 0


def _minute_parts(disp: str) -> tuple[int, int]:
    """'9'' -> (9, 0); '90'+3'' -> (90, 3)."""
    s = (disp or "").replace("'", "").strip()
    if "+" in s:
        a, b = s.split("+", 1)
        return _int(a), _int(b)
    return _int(s), 0


def parse_summary(summary: dict) -> dict | None:
    """ESPN match summary -> {'goals': {team: [..]}, 'score_by_team': {team: {ht,ft,et,p}}}.

    Goals come from keyEvents (on-pitch only — shootout kicks aren't listed there); the
    score object comes from the per-half 'linescores' so extra time and shootouts resolve
    cleanly.
    """
    comp = (summary.get("header", {}).get("competitions") or [{}])[0]
    cps = comp.get("competitors", [])
    if len(cps) != 2:
        return None

    id2name, linescores, headline = {}, {}, {}
    for c in cps:
        nm = _name((c.get("team") or {}).get("displayName", ""))
        id2name[(c.get("team") or {}).get("id")] = nm
        linescores[nm] = [_int(ls.get("displayValue") or ls.get("value"))
                          for ls in (c.get("linescores") or [])]
        headline[nm] = _int(c.get("score"))
    names = list(linescores)
    if len(names) != 2:
        return None

    goals: dict[str, list] = {nm: [] for nm in names}
    cards: dict[str, list] = {nm: [] for nm in names}
    for e in summary.get("keyEvents", []):
        ttype = (e.get("type") or {}).get("text", "")
        tnm = id2name.get((e.get("team") or {}).get("id"))
        if tnm not in goals:
            continue
        parts = e.get("participants") or []
        minute, offset = _minute_parts((e.get("clock") or {}).get("displayValue", ""))
        if "Goal" in ttype or ttype == "Penalty - Scored":
            scorer = ((parts[0].get("athlete") or {}).get("displayName", "")) if parts else ""
            assist = ((parts[1].get("athlete") or {}).get("displayName", "")) if len(parts) > 1 else ""
            goals[tnm].append({
                "name": scorer, "assist": assist, "minute": minute, "offset": offset,
                "penalty": ttype == "Penalty - Scored",
                "owngoal": "Own Goal" in ttype,
            })
        elif ttype in ("Yellow Card", "Red Card"):
            player = ((parts[0].get("athlete") or {}).get("displayName", "")) if parts else ""
            cards[tnm].append({"name": player, "minute": minute,
                               "type": "red" if ttype == "Red Card" else "yellow"})

    n = max(len(linescores[names[0]]), len(linescores[names[1]]))

    def per(nm: str) -> dict:
        v = linescores[nm]
        if not v:  # no per-half breakdown — fall back to the headline score
            return {"ft": headline.get(nm, 0)}
        d = {"ht": v[0]}
        if n >= 5:        # extra time + penalty shootout
            d["ft"], d["et"], d["p"] = sum(v[0:2]), sum(v[0:4]), (v[4] if len(v) > 4 else 0)
        elif n >= 4:      # extra time, no shootout
            d["ft"], d["et"] = sum(v[0:2]), sum(v[0:4])
        else:             # regulation (or in-progress)
            d["ft"] = sum(v)
        return d

    return {"goals": goals, "cards": cards,
            "score_by_team": {nm: per(nm) for nm in names}}


def fetch_results() -> dict:
    """Return {frozenset({teamA, teamB}): parsed_summary} for every started ESPN match."""
    events = []
    for rng in ("20260611-20260628", "20260629-20260719"):
        try:
            resp = requests.get(f"{ESPN}/scoreboard?dates={rng}", timeout=20)
            resp.raise_for_status()
            events += resp.json().get("events", [])
        except requests.RequestException:
            continue

    started = list(dict.fromkeys(
        e.get("id") for e in events
        if (((e.get("status") or {}).get("type") or {}).get("state")) in ("in", "post")
        and e.get("id")
    ))

    def grab(eid: str) -> dict | None:
        try:
            resp = requests.get(f"{ESPN}/summary?event={eid}", timeout=20)
            resp.raise_for_status()
            return parse_summary(resp.json())
        except requests.RequestException:
            return None

    out: dict = {}
    if started:
        with ThreadPoolExecutor(max_workers=8) as ex:
            for parsed in ex.map(grab, started):
                if parsed and len(parsed["goals"]) == 2:
                    out[frozenset(parsed["goals"])] = parsed
    return out
