"""Honours tab — fun trophies, auto-awarded from the live feed.

Players compete for a chocolate bar: most (non-booby) trophies wins. Each trophy is a
small dict with a `fn(bundle)` resolver returning who currently holds it. Adding a new
trophy later is one entry in AWARDS — keep the resolvers pure (no Streamlit) so they're
easy to test.
"""
from __future__ import annotations

import html
from datetime import datetime

import streamlit as st


def _esc(s: object) -> str:
    return html.escape(str(s))


def _minute(g: dict) -> int:
    """Goal minute as a sortable int ('45+2' -> 45). Unknown sorts last."""
    digits = "".join(ch for ch in str(g.get("minute", "")).split("+")[0] if ch.isdigit())
    return int(digits) if digits else 999


def _group_done(b: dict) -> bool:
    fx = b.get("fixtures", {})
    return bool(fx) and all(f["score"] is not None for fs in fx.values() for f in fs)


# --------------------------------------------------------------------- resolvers
# Each returns either {"status": "open"} or
# {"status": "won", "holders": [players], "detail": str, "teams": [teams for flags]}

def first_blood(b: dict) -> dict:
    from data import _on_pitch, _uk_kickoff
    owner = b["owner"]
    events = []  # (kickoff, minute, scoring_team, scorer, opponent)
    for m in b["_matches"]:
        if _on_pitch(m.get("score")) is None:
            continue
        ko = _uk_kickoff(m.get("date", ""), m.get("time", "")) or datetime.max
        for g in (m.get("goals1") or []):
            events.append((ko, _minute(g), m["team1"], g.get("name", ""), m["team2"]))
        for g in (m.get("goals2") or []):
            events.append((ko, _minute(g), m["team2"], g.get("name", ""), m["team1"]))
    if not events:
        return {"status": "open"}
    _, minute, team, scorer, opp = min(events, key=lambda e: (e[0], e[1]))
    who = f"{scorer} {minute}'" if scorer else f"{minute}'"
    return {"status": "won", "holders": [owner.get(team, "—")], "teams": [team],
            "detail": f"{team} ({who}) v {opp}"}


def biggest_thrashing(b: dict) -> dict:
    from data import _on_pitch, _winner_loser
    owner = b["owner"]
    best_margin, best = 0, []
    for m in b["_matches"]:
        sc = _on_pitch(m.get("score"))
        if sc is None or sc[0] == sc[1]:
            continue
        margin = abs(sc[0] - sc[1])
        winner, _ = _winner_loser(m, sc)
        hi, lo = max(sc), min(sc)
        loser = m["team2"] if winner == m["team1"] else m["team1"]
        detail = f"{winner} {hi}–{lo} {loser}"
        if margin > best_margin:
            best_margin, best = margin, [(winner, detail)]
        elif margin == best_margin:
            best.append((winner, detail))
    if not best:
        return {"status": "open"}
    return {"status": "won", "holders": [owner.get(w, "—") for w, _ in best],
            "teams": [w for w, _ in best], "detail": " · ".join(d for _, d in best)}


def top_team(b: dict) -> dict:
    goals, owner = b["goals"], b["owner"]
    top = max(goals.values(), default=0)
    if top == 0:
        return {"status": "open"}
    teams = [t for t, g in goals.items() if g == top]
    return {"status": "won", "holders": [owner.get(t, "—") for t in teams],
            "teams": teams, "detail": " · ".join(f"{t} ({top})" for t in teams)}


def _reached_ko(b: dict, team: str) -> bool:
    return (b["status"].get(team) or {}).get("phase") == "ko"


def treble_dream(b: dict) -> dict:
    holders = [p for p, ts in b["allocation"].items()
               if all(_reached_ko(b, t) for t in ts)]
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": holders, "detail": "all 3 teams in the knockouts"}


def total_wipeout(b: dict) -> dict:
    if not _group_done(b):
        return {"status": "open"}
    holders = [p for p, ts in b["allocation"].items()
               if not any(_reached_ko(b, t) for t in ts)]
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": holders, "detail": "all 3 teams out in the groups"}


def bottlers(b: dict) -> dict:
    from data import _on_pitch
    owner = b["owner"]
    holders, details = set(), []
    for m in b["_matches"]:
        ft = _on_pitch(m.get("score"))
        ht = (m.get("score") or {}).get("ht")
        if ft is None or not ht:
            continue
        (a_ft, b_ft), (a_ht, b_ht) = ft, ht
        if a_ht > b_ht and a_ft <= b_ft and owner.get(m["team1"]):  # led at HT, didn't win
            holders.add(owner[m["team1"]])
            details.append(f"{m['team1']} ({a_ht}–{b_ht} → {a_ft}–{b_ft})")
        if b_ht > a_ht and b_ft <= a_ft and owner.get(m["team2"]):
            holders.add(owner[m["team2"]])
            details.append(f"{m['team2']} ({b_ht}–{a_ht} → {b_ft}–{a_ft})")
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(holders), "detail": " · ".join(details)}


def leaky_sieve(b: dict) -> dict:
    from data import _on_pitch
    owner = b["owner"]
    conceded: dict[str, int] = {}
    for m in b["_matches"]:
        sc = _on_pitch(m.get("score"))
        if sc is None:
            continue
        conceded[m["team1"]] = conceded.get(m["team1"], 0) + sc[1]
        conceded[m["team2"]] = conceded.get(m["team2"], 0) + sc[0]
    worst = max(conceded.values(), default=0)
    if worst == 0:
        return {"status": "open"}
    teams = [t for t, c in conceded.items() if c == worst]
    return {"status": "won", "holders": [owner.get(t, "—") for t in teams],
            "teams": teams, "detail": " · ".join(f"{t} ({worst} conceded)" for t in teams)}


def bore_draw_king(b: dict) -> dict:
    from data import _on_pitch
    owner = b["owner"]
    count: dict[str, int] = {}
    for m in b["_matches"]:
        sc = _on_pitch(m.get("score"))
        if sc is None or sc[0] != 0 or sc[1] != 0:
            continue
        for team in (m["team1"], m["team2"]):
            p = owner.get(team)
            if p:
                count[p] = count.get(p, 0) + 1
    if not count:
        return {"status": "open"}
    most = max(count.values())
    holders = sorted(p for p, c in count.items() if c == most)
    return {"status": "won", "holders": holders,
            "detail": f"{most} goalless draw{'s' if most != 1 else ''}"}


def own_goal_king(b: dict) -> dict:
    from data import _on_pitch
    owner = b["owner"]
    committed: dict[str, int] = {}  # own goal in the opponent's list = your team conceded it
    for m in b["_matches"]:
        if _on_pitch(m.get("score")) is None:
            continue
        for g in (m.get("goals2") or []):
            if g.get("owngoal"):
                committed[m["team1"]] = committed.get(m["team1"], 0) + 1
        for g in (m.get("goals1") or []):
            if g.get("owngoal"):
                committed[m["team2"]] = committed.get(m["team2"], 0) + 1
    if not committed:
        return {"status": "open"}
    most = max(committed.values())
    teams = [t for t, c in committed.items() if c == most]
    return {"status": "won", "holders": [owner.get(t, "—") for t in teams],
            "teams": teams, "detail": " · ".join(f"{t} ({most})" for t in teams)}


def wooden_spoon(b: dict) -> dict:
    """Fewest combined goals. Settled once the group stage is done, so we don't crown it
    while the table is still all zeros. Ties share it."""
    totals = [(p, sum(b["goals"].get(t, 0) for t in ts)) for p, ts in b["allocation"].items()]
    if not totals or not _group_done(b):
        return {"status": "open"}
    low = min(t for _, t in totals)
    return {"status": "won", "holders": sorted(p for p, t in totals if t == low),
            "detail": f"fewest combined goals ({low})"}


# Team strength tiers (FIFA ranking, 1 Apr 2026 anchored) — the same pots the draw used,
# embedded here so the underdog trophies know which sides are favourites vs minnows.
_RANKING = [
    "France", "Spain", "Argentina", "England", "Portugal", "Brazil", "Netherlands",
    "Morocco", "Belgium", "Germany", "Croatia", "Colombia", "Senegal", "Mexico",
    "USA", "Uruguay",
    "Japan", "Switzerland", "Iran", "Austria", "South Korea", "Ecuador", "Norway",
    "Australia", "Turkey", "Sweden", "Canada", "Panama", "Egypt", "Algeria",
    "Scotland", "Qatar",
    "Czech Republic", "Ivory Coast", "Tunisia", "Paraguay", "Uzbekistan", "Saudi Arabia",
    "DR Congo", "Iraq", "South Africa", "Jordan", "Cape Verde", "Ghana",
    "Bosnia & Herzegovina", "Curaçao", "Haiti", "New Zealand",
]
POT1, POT3 = set(_RANKING[0:16]), set(_RANKING[32:48])


def _played_count(b: dict) -> dict[str, int]:
    from data import _on_pitch
    played: dict[str, int] = {}
    for m in b["_matches"]:
        if _on_pitch(m.get("score")) is None:
            continue
        for t in (m["team1"], m["team2"]):
            played[t] = played.get(t, 0) + 1
    return played


def _scored_in_match(goals_list: list) -> dict[str, int]:
    tally: dict[str, int] = {}
    for g in goals_list or []:
        if g.get("owngoal"):
            continue
        tally[g.get("name", "?")] = tally.get(g.get("name", "?"), 0) + 1
    return tally


def hat_trick_hero(b: dict) -> dict:
    from data import _on_pitch
    owner = b["owner"]
    holders, details = set(), []
    for m in b["_matches"]:
        if _on_pitch(m.get("score")) is None:
            continue
        for team, gl in ((m["team1"], m.get("goals1")), (m["team2"], m.get("goals2"))):
            for nm, c in _scored_in_match(gl).items():
                if c >= 3 and owner.get(team):
                    holders.add(owner[team])
                    details.append(f"{nm} ({c}) — {team}")
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(holders), "detail": " · ".join(details)}


def giant_killer(b: dict) -> dict:
    from data import _on_pitch, _winner_loser
    owner = b["owner"]
    holders, teams, details = set(), [], []
    for m in b["_matches"]:
        sc = _on_pitch(m.get("score"))
        if sc is None or sc[0] == sc[1]:
            continue
        winner, loser = _winner_loser(m, sc)
        if loser in POT1 and winner not in POT1 and owner.get(winner):
            holders.add(owner[winner])
            teams.append(winner)
            details.append(f"{winner} beat {loser}")
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(holders), "teams": teams,
            "detail": " · ".join(details)}


def cinderella(b: dict) -> dict:
    holders, teams = set(), []
    for p, ts in b["allocation"].items():
        for t in ts:
            if t in POT3 and _reached_ko(b, t):
                holders.add(p)
                teams.append(t)
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(holders), "teams": teams,
            "detail": " · ".join(sorted(set(teams)))}


def comeback_kings(b: dict) -> dict:
    from data import _on_pitch
    owner = b["owner"]
    holders, details = set(), []
    for m in b["_matches"]:
        ft = _on_pitch(m.get("score"))
        ht = (m.get("score") or {}).get("ht")
        if ft is None or not ht:
            continue
        (a_ft, b_ft), (a_ht, b_ht) = ft, ht
        if a_ht < b_ht and a_ft > b_ft and owner.get(m["team1"]):  # trailed at HT, won
            holders.add(owner[m["team1"]])
            details.append(f"{m['team1']} ({a_ht}–{b_ht} → {a_ft}–{b_ft})")
        if b_ht < a_ht and b_ft > a_ft and owner.get(m["team2"]):
            holders.add(owner[m["team2"]])
            details.append(f"{m['team2']} ({b_ht}–{a_ht} → {b_ft}–{a_ft})")
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(holders), "detail": " · ".join(details)}


def golden_owner(b: dict) -> dict:
    from data import _on_pitch
    owner = b["owner"]
    tally: dict[str, int] = {}
    team_of: dict[str, str] = {}
    for m in b["_matches"]:
        if _on_pitch(m.get("score")) is None:
            continue
        for team, gl in ((m["team1"], m.get("goals1")), (m["team2"], m.get("goals2"))):
            for nm, c in _scored_in_match(gl).items():
                tally[nm] = tally.get(nm, 0) + c
                team_of[nm] = team
    top = max(tally.values(), default=0)
    if top == 0:
        return {"status": "open"}
    scorers = [nm for nm, c in tally.items() if c == top]
    teams = [team_of[nm] for nm in scorers]
    return {"status": "won", "holders": sorted({owner.get(t, "—") for t in teams}),
            "teams": teams, "detail": " · ".join(f"{nm} ({top}) — {team_of[nm]}" for nm in scorers)}


def one_trick_pony(b: dict) -> dict:
    """All your goals from a single team — only judged once all three of your teams have
    played, so you're not branded a one-trick pony before your others have kicked off."""
    played = _played_count(b)
    holders, details = [], []
    for p, ts in b["allocation"].items():
        if any(played.get(t, 0) == 0 for t in ts):
            continue
        gs = {t: b["goals"].get(t, 0) for t in ts}
        total = sum(gs.values())
        if total > 0 and sum(1 for g in gs.values() if g > 0) == 1:
            src = next(t for t, g in gs.items() if g > 0)
            holders.append(p)
            details.append(f"{p}: all {total} from {src}")
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(holders), "detail": " · ".join(details)}


def _offset(g: dict) -> int:
    try:
        return int(g.get("offset") or 0)
    except (ValueError, TypeError):
        return 0


def stoppage_time_king(b: dict) -> dict:
    from data import _on_pitch
    owner = b["owner"]
    by_player: dict[str, int] = {}
    for m in b["_matches"]:
        if _on_pitch(m.get("score")) is None:
            continue
        for team, gl in ((m["team1"], m.get("goals1")), (m["team2"], m.get("goals2"))):
            p = owner.get(team)
            if not p:
                continue
            for g in (gl or []):
                if not g.get("owngoal") and _offset(g) > 0:
                    by_player[p] = by_player.get(p, 0) + 1
    top = max(by_player.values(), default=0)
    if top == 0:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(p for p, c in by_player.items() if c == top),
            "detail": f"{top} stoppage-time goal{'s' if top != 1 else ''}"}


def _lead_swaps(m: dict) -> int:
    events = [(g, 1) for g in (m.get("goals1") or [])] + [(g, 2) for g in (m.get("goals2") or [])]
    events.sort(key=lambda e: (_minute(e[0]), _offset(e[0])))
    s1 = s2 = last = swaps = 0
    for g, side in events:
        if side == 1:
            s1 += 1
        else:
            s2 += 1
        lead = 1 if s1 > s2 else (2 if s2 > s1 else 0)
        if lead and last and lead != last:
            swaps += 1
        if lead:
            last = lead
    return swaps


def rollercoaster(b: dict) -> dict:
    from data import _on_pitch
    owner = b["owner"]
    best, items = 0, []
    for m in b["_matches"]:
        if _on_pitch(m.get("score")) is None:
            continue
        sw = _lead_swaps(m)
        if sw > best:
            best, items = sw, [m]
        elif sw == best and sw > 0:
            items.append(m)
    if best < 1:
        return {"status": "open"}
    holders, teams, details = set(), [], []
    for m in items:
        sc = _on_pitch(m.get("score"))
        for t in (m["team1"], m["team2"]):
            if owner.get(t):
                holders.add(owner[t])
                teams.append(t)
        details.append(f"{m['team1']} {sc[0]}–{sc[1]} {m['team2']} (lead changed {best}×)")
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(holders), "teams": teams, "detail": " · ".join(details)}


def the_full_set(b: dict) -> dict:
    from data import _on_pitch, _winner_loser
    won_a_game = set()
    for m in b["_matches"]:
        sc = _on_pitch(m.get("score"))
        if sc is None or sc[0] == sc[1]:
            continue
        w, _ = _winner_loser(m, sc)
        if w:
            won_a_game.add(w)
    holders = [p for p, ts in b["allocation"].items() if all(t in won_a_game for t in ts)]
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(holders), "detail": "all three teams won a game"}


def dark_horse(b: dict) -> dict:
    goals = b["goals"]
    holders, details = [], []
    for p, ts in b["allocation"].items():
        others = [goals.get(t, 0) for t in ts if t not in POT3]
        for t in ts:
            if t in POT3 and goals.get(t, 0) > 0 and all(goals.get(t, 0) > o for o in others):
                holders.append(p)
                details.append(f"{t} ({goals.get(t, 0)})")
                break
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(holders), "detail": " · ".join(details)}


def penalty_king(b: dict) -> dict:
    from data import _on_pitch
    owner = b["owner"]
    by_player: dict[str, int] = {}
    for m in b["_matches"]:
        if _on_pitch(m.get("score")) is None:
            continue
        for team, gl in ((m["team1"], m.get("goals1")), (m["team2"], m.get("goals2"))):
            p = owner.get(team)
            if not p:
                continue
            for g in (gl or []):
                if g.get("penalty") and not g.get("owngoal"):
                    by_player[p] = by_player.get(p, 0) + 1
    top = max(by_player.values(), default=0)
    if top == 0:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(p for p, c in by_player.items() if c == top),
            "detail": f"{top} penalt{'ies' if top != 1 else 'y'} scored"}


def the_entertainers(b: dict) -> dict:
    from data import _on_pitch
    conceded: dict[str, int] = {}
    for m in b["_matches"]:
        sc = _on_pitch(m.get("score"))
        if sc is None:
            continue
        conceded[m["team1"]] = conceded.get(m["team1"], 0) + sc[1]
        conceded[m["team2"]] = conceded.get(m["team2"], 0) + sc[0]
    goals = b["goals"]
    by_player = {p: sum(goals.get(t, 0) + conceded.get(t, 0) for t in ts)
                 for p, ts in b["allocation"].items()}
    top = max(by_player.values(), default=0)
    if top == 0:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(p for p, c in by_player.items() if c == top),
            "detail": f"{top} goals in their games (scored + conceded)"}


def first_to_fall(b: dict) -> dict:
    from datetime import datetime

    from data import _on_pitch, _uk_kickoff, _winner_loser
    owner = b["owner"]
    best = None  # (kickoff, loser)
    for m in b["_matches"]:
        if m.get("group"):  # knockouts only
            continue
        sc = _on_pitch(m.get("score"))
        if sc is None or sc[0] == sc[1]:
            continue
        _, loser = _winner_loser(m, sc)
        if not loser or not owner.get(loser):
            continue
        ko = _uk_kickoff(m.get("date", ""), m.get("time", "")) or datetime.max
        if best is None or ko < best[0]:
            best = (ko, loser)
    if best is None:
        return {"status": "open"}
    loser = best[1]
    return {"status": "won", "holders": [owner.get(loser, "—")], "teams": [loser],
            "detail": f"{loser} — first out"}


def pointless(b: dict) -> dict:
    if not _group_done(b):
        return {"status": "open"}
    owner = b["owner"]
    teams = [r["team"] for rows in b["standings"].values() for r in rows
             if r["pts"] == 0 and owner.get(r["team"])]
    if not teams:
        return {"status": "open"}
    return {"status": "won", "holders": sorted({owner[t] for t in teams}),
            "teams": teams, "detail": " · ".join(teams)}


def goal_shy(b: dict) -> dict:
    if not _group_done(b):
        return {"status": "open"}
    owner = b["owner"]
    teams = [r["team"] for rows in b["standings"].values() for r in rows
             if r["gf"] == 0 and owner.get(r["team"])]
    if not teams:
        return {"status": "open"}
    return {"status": "won", "holders": sorted({owner[t] for t in teams}),
            "teams": teams, "detail": " · ".join(teams)}


def sitting_duck(b: dict) -> dict:
    from data import _on_pitch
    owner = b["owner"]
    best = None  # (minute, conceding_team)
    for m in b["_matches"]:
        if _on_pitch(m.get("score")) is None:
            continue
        for opp, gl in ((m["team2"], m.get("goals1")), (m["team1"], m.get("goals2"))):
            for g in (gl or []):
                mn = _minute(g)
                if best is None or mn < best[0]:
                    best = (mn, opp)
    if best is None:
        return {"status": "open"}
    mn, conceder = best
    return {"status": "won", "holders": [owner.get(conceder, "—")], "teams": [conceder],
            "detail": f"{conceder} conceded after {mn}'"}


def whipping_boys(b: dict) -> dict:
    from data import _on_pitch, _winner_loser
    owner = b["owner"]
    best_margin, losers, details = 0, [], []
    for m in b["_matches"]:
        sc = _on_pitch(m.get("score"))
        if sc is None or sc[0] == sc[1]:
            continue
        margin = abs(sc[0] - sc[1])
        winner, loser = _winner_loser(m, sc)
        detail = f"{loser} {min(sc)}–{max(sc)} {winner}"
        if margin > best_margin:
            best_margin, losers, details = margin, [loser], [detail]
        elif margin == best_margin:
            losers.append(loser)
            details.append(detail)
    if not losers:
        return {"status": "open"}
    return {"status": "won", "holders": sorted({owner.get(x, "—") for x in losers}),
            "teams": losers, "detail": " · ".join(details)}


def playmaker(b: dict) -> dict:
    owner = b["owner"]
    tally: dict[str, int] = {}
    team_of: dict[str, str] = {}
    for m in b["_matches"]:
        for goals, team in ((m.get("goals1"), m["team1"]), (m.get("goals2"), m["team2"])):
            for g in (goals or []):
                a = g.get("assist")
                if a:
                    tally[a] = tally.get(a, 0) + 1
                    team_of[a] = team
    top = max(tally.values(), default=0)
    if top == 0:
        return {"status": "open"}
    makers = [a for a, c in tally.items() if c == top]
    teams = [team_of[a] for a in makers]
    return {"status": "won", "holders": sorted({owner.get(t, "—") for t in teams}),
            "teams": teams, "detail": " · ".join(f"{a} ({top}) — {team_of[a]}" for a in makers)}


def super_sub(b: dict) -> dict:
    owner = b["owner"]
    holders, details = set(), []
    for m in b["_matches"]:
        for goals, team in ((m.get("goals1"), m["team1"]), (m.get("goals2"), m["team2"])):
            p = owner.get(team)
            if not p:
                continue
            for g in (goals or []):
                if g.get("sub") and not g.get("owngoal"):
                    holders.add(p)
                    details.append(f"{g.get('name', '?')} ({team})")
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(holders), "detail": " · ".join(details)}


def ten_men(b: dict) -> dict:
    from data import _on_pitch, _winner_loser
    owner = b["owner"]
    holders, details = set(), []
    for m in b["_matches"]:
        sc = _on_pitch(m.get("score"))
        if sc is None:
            continue
        winner, loser = _winner_loser(m, sc)
        for cards, team in ((m.get("cards1"), m["team1"]), (m.get("cards2"), m["team2"])):
            p = owner.get(team)
            if not p:
                continue
            if any(c.get("type") == "red" for c in (cards or [])) and team != loser:
                holders.add(p)
                details.append(f"{team} ({'won' if team == winner else 'drew'} with 10)")
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(holders), "detail": " · ".join(details)}


def mr_everything(b: dict) -> dict:
    owner = b["owner"]
    tally: dict[str, int] = {}
    team_of: dict[str, str] = {}
    for m in b["_matches"]:
        for goals, team in ((m.get("goals1"), m["team1"]), (m.get("goals2"), m["team2"])):
            for g in (goals or []):
                if g.get("owngoal"):
                    continue
                for who in (g.get("name"), g.get("assist")):
                    if who:
                        tally[who] = tally.get(who, 0) + 1
                        team_of[who] = team
    top = max(tally.values(), default=0)
    if top == 0:
        return {"status": "open"}
    best = [nm for nm, c in tally.items() if c == top]
    teams = [team_of[nm] for nm in best]
    return {"status": "won", "holders": sorted({owner.get(t, "—") for t in teams}),
            "teams": teams, "detail": " · ".join(f"{nm} ({top}) — {team_of[nm]}" for nm in best)}


def penalty_villain(b: dict) -> dict:
    owner = b["owner"]
    holders, details = set(), []
    for m in b["_matches"]:
        for misses, team in ((m.get("pen_misses1"), m["team1"]), (m.get("pen_misses2"), m["team2"])):
            p = owner.get(team)
            if not p:
                continue
            for pm in (misses or []):
                holders.add(p)
                details.append(f"{pm.get('name', '?')} ({team})")
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(holders), "detail": " · ".join(details)}


def bad_boys(b: dict) -> dict:
    owner = b["owner"]
    by_player: dict[str, int] = {}
    for m in b["_matches"]:
        for cards, team in ((m.get("cards1"), m["team1"]), (m.get("cards2"), m["team2"])):
            p = owner.get(team)
            if not p:
                continue
            for c in (cards or []):
                if c.get("type") == "yellow":
                    by_player[p] = by_player.get(p, 0) + 1
    top = max(by_player.values(), default=0)
    if top == 0:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(p for p, c in by_player.items() if c == top),
            "detail": f"{top} yellow card{'s' if top != 1 else ''}"}


def seeing_red(b: dict) -> dict:
    owner = b["owner"]
    holders, details = set(), []
    for m in b["_matches"]:
        for cards, team in ((m.get("cards1"), m["team1"]), (m.get("cards2"), m["team2"])):
            p = owner.get(team)
            if not p:
                continue
            for c in (cards or []):
                if c.get("type") == "red":
                    holders.add(p)
                    details.append(f"{c.get('name', '?')} ({team})")
    if not holders:
        return {"status": "open"}
    return {"status": "won", "holders": sorted(holders), "detail": " · ".join(details)}


AWARDS = [
    {"icon": "🩸", "name": "First Blood", "blurb": "Owned the team that scored the tournament's first goal", "fn": first_blood},
    {"icon": "💥", "name": "Biggest Thrashing", "blurb": "Biggest winning margin in a single game", "fn": biggest_thrashing},
    {"icon": "🔝", "name": "Top Team", "blurb": "Owns the single highest-scoring team", "fn": top_team},
    {"icon": "✨", "name": "Treble Dream", "blurb": "All three of your teams reach the knockouts", "fn": treble_dream},
    {"icon": "🎩", "name": "Hat-trick Hero", "blurb": "A player on one of your teams scores 3+ in a game", "fn": hat_trick_hero},
    {"icon": "🗡️", "name": "Giant Killer", "blurb": "One of your underdogs beats a top-16 side", "fn": giant_killer},
    {"icon": "👠", "name": "Cinderella", "blurb": "One of your bottom-16 teams reaches the knockouts", "fn": cinderella},
    {"icon": "🔄", "name": "Comeback Kings", "blurb": "Your team wins after trailing at half-time", "fn": comeback_kings},
    {"icon": "👑", "name": "Golden Owner", "blurb": "You own the tournament's top goalscorer", "fn": golden_owner},
    {"icon": "⏱️", "name": "Stoppage Time King", "blurb": "Your teams score the most goals in added time", "fn": stoppage_time_king},
    {"icon": "🎢", "name": "Rollercoaster", "blurb": "Own a team in the game with the most lead changes", "fn": rollercoaster},
    {"icon": "🎰", "name": "The Full Set", "blurb": "All three of your teams win at least one game", "fn": the_full_set},
    {"icon": "🐎", "name": "Dark Horse", "blurb": "Your bottom-pot team outscores both your stronger teams", "fn": dark_horse},
    {"icon": "🎯", "name": "Penalty King", "blurb": "Your teams score the most penalties", "fn": penalty_king},
    {"icon": "🎭", "name": "The Entertainers", "blurb": "Your teams' games rack up the most goals (scored + conceded)", "fn": the_entertainers},
    {"icon": "🅰️", "name": "Playmaker", "blurb": "You own the tournament's top assist-maker", "fn": playmaker},
    {"icon": "⭐", "name": "Mr Everything", "blurb": "Own the player with the most goals + assists combined", "fn": mr_everything},
    {"icon": "🔥", "name": "Super Sub", "blurb": "A substitute on one of your teams comes on and scores", "fn": super_sub},
    {"icon": "🛡️", "name": "Ten Men", "blurb": "Own a team that gets a red card but still wins or draws", "fn": ten_men},
    {"icon": "🥄", "name": "Wooden Spoon", "blurb": "Fewest combined goals (settled after the group stage)", "fn": wooden_spoon, "booby": True},
    {"icon": "🪣", "name": "Total Wipeout", "blurb": "All three of your teams out in the group stage", "fn": total_wipeout, "booby": True},
    {"icon": "😬", "name": "Bottlers", "blurb": "Your team led at half-time and failed to win", "fn": bottlers, "booby": True},
    {"icon": "🕳️", "name": "Leaky Sieve", "blurb": "Your team conceded the most goals", "fn": leaky_sieve, "booby": True},
    {"icon": "😴", "name": "Bore Draw King", "blurb": "Your teams featured in the most 0-0 draws", "fn": bore_draw_king, "booby": True},
    {"icon": "🤦", "name": "Own Goal King", "blurb": "Your teams scored the most own goals", "fn": own_goal_king, "booby": True},
    {"icon": "🐴", "name": "One-Trick Pony", "blurb": "All your goals come from a single team (once all 3 have played)", "fn": one_trick_pony, "booby": True},
    {"icon": "🪦", "name": "First to Fall", "blurb": "Own the first team knocked out in the knockouts", "fn": first_to_fall, "booby": True},
    {"icon": "🅿️", "name": "Pointless", "blurb": "One of your teams finishes the groups on 0 points", "fn": pointless, "booby": True},
    {"icon": "🤐", "name": "Goal Shy", "blurb": "One of your teams fails to score in the group stage", "fn": goal_shy, "booby": True},
    {"icon": "🦆", "name": "Sitting Duck", "blurb": "Own the team that concedes the fastest goal", "fn": sitting_duck, "booby": True},
    {"icon": "🧎", "name": "Whipping Boys", "blurb": "Own the team on the wrong end of the Biggest Thrashing", "fn": whipping_boys, "booby": True},
    {"icon": "🟨", "name": "Bad Boys", "blurb": "Your three teams rack up the most yellow cards", "fn": bad_boys, "booby": True},
    {"icon": "🟥", "name": "Seeing Red", "blurb": "Own a team that gets a player sent off", "fn": seeing_red, "booby": True},
    {"icon": "🥅", "name": "Penalty Villain", "blurb": "Your team's player misses or has a penalty saved in open play", "fn": penalty_villain, "booby": True},
]


# ------------------------------------------------------------------------ render

CSS = """
<style>
.tr * { box-sizing:border-box; }
.tr { font-family:system-ui, sans-serif; }
.trophy { border:1px solid #2a2a33; border-radius:12px; background:#15151c;
          margin-bottom:10px; overflow:hidden; }
.trophy.won { border-color:#ffd84d66; }
.trophy.booby.won { border-color:#74747f80; }
.tr-h { display:flex; align-items:center; gap:9px; padding:10px 14px 3px; }
.tr-ic { font-size:20px; }
.tr-nm { font-weight:800; font-size:15px; color:#fff; }
.tr-bl { color:#9090a0; font-size:12px; padding:0 14px 9px; }
.tr-win { padding:8px 14px; background:#ffd84d14; color:#eafff3; font-size:13px;
          border-top:1px solid #ffffff10; }
.tr-win b { color:#ffd84d; }
.trophy.booby .tr-win { background:#74747f1f; }
.trophy.booby .tr-win b { color:#d7d7de; }
.tr-open { padding:8px 14px; color:#7a7a86; font-size:12px; font-style:italic;
           border-top:1px solid #ffffff10; }
.lb { border:1px solid #2a2a33; border-radius:10px; background:#15151c;
      margin-bottom:10px; overflow:hidden; }
.lb-h { background:#1c1c26; color:#9090a0; font-size:10px; font-weight:700;
        text-transform:uppercase; letter-spacing:1px; padding:5px 12px; }
.lb-row { display:flex; justify-content:space-between; align-items:center;
          padding:5px 12px; border-top:1px solid #ffffff0d; font-size:13px; }
.lb-row .lb-nm { color:#e8e8ef; font-weight:600; }
.lb-row .lb-ct { font-weight:800; }
</style>
"""


def _card(award: dict, res: dict, flags: dict) -> str:
    booby = " booby" if award.get("booby") else ""
    head = (f'<div class="tr-h"><span class="tr-ic">{award["icon"]}</span>'
            f'<span class="tr-nm">{_esc(award["name"])}</span></div>'
            f'<div class="tr-bl">{_esc(award["blurb"])}</div>')
    if res.get("status") != "won":
        return f'<div class="trophy{booby}">{head}<div class="tr-open">Up for grabs…</div></div>'
    holders = ", ".join(res["holders"])
    fl = " ".join(flags.get(t, "") for t in res.get("teams", []))
    line = f'🏆 <b>{_esc(holders)}</b> · {fl} {_esc(res.get("detail", ""))}'.strip()
    return f'<div class="trophy{booby} won">{head}<div class="tr-win">{line}</div></div>'


def _tally(results: list) -> dict[str, int]:
    tally: dict[str, int] = {}
    for _, res in results:
        if res.get("status") == "won":
            for h in res["holders"]:
                tally[h] = tally.get(h, 0) + 1
    return tally


def _resolve(award: dict, b: dict) -> dict:
    """Run a trophy resolver, but never let one buggy resolver crash the whole app — on
    any error treat the trophy as not-yet-won. Live feed data throws up odd edge cases.
    The failure is logged (owner-only app logs) so we can find and fix the real cause."""
    try:
        return award["fn"](b)
    except Exception as exc:  # noqa: BLE001 — resilience over a single trophy is the priority
        import sys
        import traceback
        print(f"[trophy] '{award.get('name')}' resolver failed: {exc!r}", file=sys.stderr)
        traceback.print_exc()
        return {"status": "open"}


def hall_tallies(b: dict) -> tuple[dict, dict]:
    """(fame_tally, shame_tally) — trophies held per player in each hall. For the Money view."""
    results = [(a, _resolve(a, b)) for a in AWARDS]
    good = _tally([(a, r) for a, r in results if not a.get("booby")])
    bad = _tally([(a, r) for a, r in results if a.get("booby")])
    return good, bad


def _standings_html(tally: dict[str, int], label: str, accent: str) -> str:
    """Compact ranked 'who holds how many' list, highest first."""
    if not tally:
        return ""
    rows = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))
    body = "".join(
        f'<div class="lb-row"><span class="lb-nm">{_esc(p)}</span>'
        f'<span class="lb-ct" style="color:{accent}">{c}</span></div>'
        for p, c in rows
    )
    return f'<div class="lb"><div class="lb-h">{label}</div>{body}</div>'


def render_fame(b: dict) -> None:
    flags = b["flags"]
    good = [(a, _resolve(a, b)) for a in AWARDS if not a.get("booby")]
    tally = _tally(good)
    good.sort(key=lambda ar: ar[1].get("status") != "won")  # won trophies float to the top
    st.subheader("🌟 Hall of Fame")
    st.caption("Win a trophy, earn a point — most trophies takes the £6.")
    if not tally:
        st.info("No trophies won yet — every one still up for grabs!", icon="🌟")
    else:
        top = max(tally.values())
        leaders = sorted(p for p, c in tally.items() if c == top)
        word = "trophy" if top == 1 else "trophies"
        st.success(f"**£6** — leading with **{top}** {word}: {', '.join(leaders)}", icon="🌟")
    st.markdown(
        CSS + _standings_html(tally, "Fame trophies", "#ffd84d")
        + '<div class="tr">' + "".join(_card(a, r, flags) for a, r in good) + "</div>",
        unsafe_allow_html=True)


def render_shame(b: dict) -> None:
    flags = b["flags"]
    shame = [(a, _resolve(a, b)) for a in AWARDS if a.get("booby")]
    tally = _tally(shame)
    shame.sort(key=lambda ar: ar[1].get("status") != "won")  # won trophies float to the top
    st.subheader("🙈 Hall of Shame")
    st.caption("Win a shame trophy, earn a point — most takes the £3.")
    if not tally:
        st.info("No shame yet — the £3 refund is still anyone's to lose!", icon="🥄")
    else:
        worst = max(tally.values())
        losers = sorted(p for p, c in tally.items() if c == worst)
        word = "trophy" if worst == 1 else "trophies"
        st.warning(f"**£3 back** — leading with **{worst}** {word}: {', '.join(losers)}",
                   icon="🥄")
    st.markdown(
        CSS + _standings_html(tally, "Shame trophies", "#d7d7de")
        + '<div class="tr">' + "".join(_card(a, r, flags) for a, r in shame) + "</div>",
        unsafe_allow_html=True)
