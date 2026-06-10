"""World Cup 2026 results, synced from the openfootball public-domain JSON feed.

No API key: the feed is plain JSON on GitHub raw, community-updated. We fetch it on each
run (cached briefly) and roll the per-match scores up into:
  - per-team goals scored        -> the Golden Boot race
  - group standings              -> live group-stage status
  - knockout progression / exit  -> "advanced" / "eliminated" status

openfootball match schema (a match only has `score` once it's been played):
  {team1, team2, group, round, date, time,
   score: {ft:[a,b], ht:[...], et:[a,b]?, p:[a,b]?},   # et = after extra time, p = shootout
   goals1:[{name,minute,penalty?}], goals2:[...]}
On-pitch goals = et if present else ft (a penalty shootout `p` is NOT goals scored).
"""
from __future__ import annotations

import requests

BASE = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026"
TEAMS_URL = f"{BASE}/worldcup.teams.json"
MATCHES_URL = f"{BASE}/worldcup.json"

# Round labels the feed uses for the knockout phase, earliest -> latest.
KNOCKOUT_ROUNDS = [
    "Round of 32",
    "Round of 16",
    "Quarter-final",
    "Quarterfinals",
    "Semi-final",
    "Semifinals",
    "Match for third place",
    "Third place",
    "Final",
]


def _get(url: str) -> object:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_teams() -> list[dict]:
    """The 48 teams, each with name, flag emoji, fifa_code, group."""
    return _get(TEAMS_URL)


def fetch_matches() -> list[dict]:
    return _get(MATCHES_URL)["matches"]


def team_flag_map(teams: list[dict]) -> dict[str, str]:
    return {t["name"]: t.get("flag_icon", "") for t in teams}


def _on_pitch(score: dict) -> list[int] | None:
    """Goals actually scored (extra time included, shootout excluded). None if unplayed."""
    if not score:
        return None
    return score.get("et") or score.get("ft")


def is_played(match: dict) -> bool:
    return _on_pitch(match.get("score")) is not None


def _is_group(match: dict) -> bool:
    return bool(match.get("group"))


# --------------------------------------------------------------------------- goals

def team_goals(matches: list[dict]) -> dict[str, int]:
    """Total tournament goals scored by each team -> the Golden Boot tally."""
    goals: dict[str, int] = {}
    for m in matches:
        sc = _on_pitch(m.get("score"))
        if sc is None:
            continue
        goals[m["team1"]] = goals.get(m["team1"], 0) + sc[0]
        goals[m["team2"]] = goals.get(m["team2"], 0) + sc[1]
    return goals


# ----------------------------------------------------------------------- standings

def group_standings(matches: list[dict]) -> dict[str, list[dict]]:
    """Per group: a sorted table (played, W/D/L, GF/GA/GD, points)."""
    table: dict[str, dict[str, dict]] = {}

    def row(group: str, team: str) -> dict:
        g = table.setdefault(group, {})
        return g.setdefault(
            team,
            {"team": team, "p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "pts": 0},
        )

    for m in matches:
        if not _is_group(m):
            continue
        sc = _on_pitch(m.get("score"))
        if sc is None:
            continue
        a, b = row(m["group"], m["team1"]), row(m["group"], m["team2"])
        ga, gb = sc
        a["p"] += 1; b["p"] += 1
        a["gf"] += ga; a["ga"] += gb
        b["gf"] += gb; b["ga"] += ga
        if ga > gb:
            a["w"] += 1; b["l"] += 1; a["pts"] += 3
        elif gb > ga:
            b["w"] += 1; a["l"] += 1; b["pts"] += 3
        else:
            a["d"] += 1; b["d"] += 1; a["pts"] += 1; b["pts"] += 1

    out: dict[str, list[dict]] = {}
    for group, rows in table.items():
        ranked = sorted(
            rows.values(),
            key=lambda r: (r["pts"], r["gf"] - r["ga"], r["gf"]),
            reverse=True,
        )
        for i, r in enumerate(ranked, 1):
            r["pos"] = i
            r["gd"] = r["gf"] - r["ga"]
        out[group] = ranked
    return out


# -------------------------------------------------------------------------- status

def _ko_round_rank(round_name: str) -> int:
    for i, label in enumerate(KNOCKOUT_ROUNDS):
        if round_name and label.lower() in round_name.lower():
            return i
    return -1


def _winner_loser(match: dict, sc: list[int]) -> tuple[str | None, str | None]:
    """(winner, loser) for a played match, using the shootout to break a level score."""
    a, b = sc
    if a != b:
        return (match["team1"], match["team2"]) if a > b else (match["team2"], match["team1"])
    p = match.get("score", {}).get("p")
    if p:
        return (match["team1"], match["team2"]) if p[0] > p[1] else (match["team2"], match["team1"])
    return None, None  # drawn (group stage)


def team_status(
    matches: list[dict], standings: dict[str, list[dict]], valid_teams: set[str]
) -> dict[str, dict]:
    """Best-effort live status per team. Keys: phase, label, alive (True|False|None).

    `valid_teams` is the real 48-team set, so unresolved knockout slots like
    "Winners Group A" are ignored rather than treated as teams.
    """
    status: dict[str, dict] = {}
    final_rank = _ko_round_rank("Final")

    # Group-stage baseline. `alive` stays None (unknown) — best-3rd rules mean we can't
    # tell who advances until the knockout bracket actually names them below.
    for group, rows in standings.items():
        for r in rows:
            status[r["team"]] = {
                "phase": "group",
                "label": f"{group} · {r['pts']} pts ({r['w']}-{r['d']}-{r['l']})",
                "pos": r["pos"],
                "alive": None,
            }

    # Knockout phase, processed shallow -> deep so the furthest round wins the label.
    ko = [(m, _ko_round_rank(m.get("round", ""))) for m in matches]
    ko = sorted([(m, r) for m, r in ko if r >= 0], key=lambda x: x[1])
    for m, rank in ko:
        rnd = m.get("round", "")
        is_final = rank == final_rank
        is_third = "third" in rnd.lower()
        # Being named in a KO match = you advanced to it; alive until a result says otherwise.
        for team in (m["team1"], m["team2"]):
            if team in valid_teams:
                status[team] = {"phase": "ko", "label": rnd, "alive": True, "ko_rank": rank}
        sc = _on_pitch(m.get("score"))
        if sc is None:
            continue
        winner, loser = _winner_loser(m, sc)
        if is_final:
            if winner in valid_teams:
                status[winner].update(alive=True, label="🏆 Champions")
            if loser in valid_teams:
                status[loser].update(alive=True, label="🥈 Runner-up")
        elif is_third:
            if winner in valid_teams:
                status[winner].update(alive=True, label="🥉 Third place")
            if loser in valid_teams:
                status[loser].update(alive=False, label="4th place")
        elif loser in valid_teams:
            status[loser].update(alive=False, label=f"out · {rnd}")
    return status


def overall(teams: list[dict], matches: list[dict]) -> dict:
    """One bundle the app renders from."""
    standings = group_standings(matches)
    valid = {t["name"] for t in teams}
    return {
        "teams": teams,
        "flags": team_flag_map(teams),
        "goals": team_goals(matches),
        "standings": standings,
        "status": team_status(matches, standings, valid),
        "played": sum(1 for m in matches if is_played(m)),
        "total": len(matches),
    }
