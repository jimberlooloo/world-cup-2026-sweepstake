"""Wall-chart view — the S&S-style World Cup planner re-flowed for a portrait phone.

Two parts, the same as a printed wall chart but stacked vertically instead of wide:
  - groups: 12 group cards (A–L), each with its 4 teams, owner, goals, position
  - bracket: the knockout rounds (R32 -> Final) stacked top-to-bottom, slots filling
    with real teams + owners as the feed resolves them.

Rendered with inline HTML/CSS via st.markdown so it reads like the chart rather than a
plain table. Layout/format inspired by the printed chart; no third-party branding/artwork.
"""
from __future__ import annotations

import html

import streamlit as st

# Knockout rounds in display order: (feed round key, heading shown on the chart).
BRACKET_ROUNDS = [
    ("Round of 32", "Round of 32"),
    ("Round of 16", "Round of 16"),
    ("Quarter-final", "Quarter-finals"),
    ("Semi-final", "Semi-finals"),
    ("Match for third place", "Third-place play-off"),
    ("Final", "Final"),
]

# Short chip label -> feed round key, for the knockout round picker (st.pills).
ROUND_PICKS = [
    ("R32", "Round of 32"),
    ("R16", "Round of 16"),
    ("QF", "Quarter-final"),
    ("SF", "Semi-final"),
    ("3rd", "Match for third place"),
    ("Final", "Final"),
]

CSS = """
<style>
.wc * { box-sizing: border-box; }
.wc { font-family: system-ui, sans-serif; }
.wc-grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
@media (min-width: 560px) { .wc-grid { grid-template-columns: 1fr 1fr; } }
.grp { border: 1px solid #1f7a4d; border-radius: 12px; overflow: hidden;
       background: #0f3d28; }
.grp-h { background: #16a35a; color: #fff; font-weight: 800; letter-spacing: .5px;
         padding: 7px 12px; font-size: 15px; display:flex; justify-content:space-between; }
.grp-h .pld { font-weight:600; opacity:.85; font-size:12px; }
.row { display: grid; grid-template-columns: 26px 1fr auto auto; align-items: center;
       gap: 8px; padding: 7px 12px; border-top: 1px solid #1f7a4d22; }
.row .fl { font-size: 18px; }
.row .tm { color: #eafff3; font-weight: 600; font-size: 14px; line-height: 1.15; }
.row .tm small { display:block; color:#9fdcbb; font-weight:500; font-size:11px; }
.row .ow { background:#0b2a1c; color:#bfe6d2; border:1px solid #2f7a55;
           border-radius: 999px; padding: 2px 9px; font-size: 11px; white-space:nowrap; }
.row .g { color:#ffd84d; font-weight:800; font-size:14px; min-width: 30px; text-align:right; }
.row.out .tm, .row.out .fl { opacity: .45; }
.row.adv { background: #16a35a14; }
.grp-sec { background:#0b2e1d; color:#7fd9a8; font-weight:700; font-size:10px;
           text-transform:uppercase; letter-spacing:1.2px; padding:5px 12px;
           border-top:1px solid #1f7a4d; }
.fx { padding:6px 12px; border-top:1px solid #1f7a4d22; }
.fx:first-of-type { border-top:none; }
.fx-dt { color:#7fbf9e; font-size:10px; letter-spacing:.3px; text-align:center; margin-bottom:3px; }
.fx-tm { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:8px; }
.fx-tm .t { font-size:13px; color:#eafff3; font-weight:600; line-height:1.15; }
.fx-tm .t1 { text-align:right; }
.fx-tm .t2 { text-align:left; }
.fx-tm .t small { display:block; color:#9fdcbb; font-weight:500; font-size:10px; margin-top:2px; }
.fx-tm .fl { font-size:15px; }
.fx-tm .sc { font-weight:800; font-size:14px; color:#ffd84d; min-width:46px; text-align:center; }
.fx-tm .sc.v { color:#5fae86; font-weight:600; font-size:12px; }
.rnd-h { color:#16a35a; font-weight:800; text-transform:uppercase; letter-spacing:1px;
         font-size:13px; margin: 16px 2px 8px; }
.bm { border:1px solid #1f7a4d; border-radius:10px; background:#0f3d28; margin-bottom:8px;
      overflow:hidden; }
.bm-dt { color:#7fbf9e; font-size:10px; letter-spacing:.3px; text-align:center;
         padding:5px 12px 0; }
.bm .row { grid-template-columns: 26px 1fr auto auto; }
.bm .sc { color:#ffd84d; font-weight:800; min-width:22px; text-align:right; }
.bm .mid { text-align:center; color:#5fae86; font-size:10px; padding:1px 0; letter-spacing:1px; }
.slot { color:#7fbf9e; font-style:italic; font-weight:500; }
.win .tm { color:#fff; }
.legend { color:#9fdcbb; font-size:11px; margin: 4px 2px 0; }
</style>
"""


def _esc(s: str) -> str:
    return html.escape(str(s))


def _is_real(team: str, valid: set[str]) -> bool:
    return team in valid


def _fixture_html(f: dict, flags: dict, owner: dict) -> str:
    """One group fixture: UK date/time + 'Team1 score Team2', flags flanking, owner below."""
    sc = f.get("score")
    score = (
        f'<span class="sc">{sc[0]}–{sc[1]}</span>' if sc
        else '<span class="sc v">v</span>'
    )
    when = f.get("day", "")
    if f.get("time"):
        when = f"{when} · {f['time']}" if when else f["time"]
    t1, t2 = f["team1"], f["team2"]
    o1 = f'<small>{_esc(owner[t1])}</small>' if owner.get(t1) else ""
    o2 = f'<small>{_esc(owner[t2])}</small>' if owner.get(t2) else ""
    return (
        f'<div class="fx"><div class="fx-dt">{_esc(when)}</div>'
        '<div class="fx-tm">'
        f'<span class="t t1">{_esc(t1)} <span class="fl">{flags.get(t1,"")}</span>{o1}</span>'
        f'{score}'
        f'<span class="t t2"><span class="fl">{flags.get(t2,"")}</span> {_esc(t2)}{o2}</span>'
        '</div></div>'
    )


def groups_html(b: dict) -> str:
    teams, flags, owner, goals = b["teams"], b["flags"], b["owner"], b["goals"]
    status, standings, fixtures = b["status"], b["standings"], b.get("fixtures", {})

    # group letter -> ordered rows (by standings position if we have it, else feed order)
    by_group: dict[str, list[dict]] = {}
    for t in teams:
        by_group.setdefault(t.get("group", "?"), []).append(t)
    pos_of: dict[str, int] = {}
    played_in: dict[str, int] = {}
    for g, rows in standings.items():
        key = g.replace("Group ", "").strip()
        played_in[key] = rows[0]["p"] if rows else 0
        for r in rows:
            pos_of[r["team"]] = r["pos"]

    cards = []
    for letter in sorted(by_group):
        members = sorted(by_group[letter], key=lambda t: pos_of.get(t["name"], 99))
        pld = played_in.get(letter, 0)
        head = f'<div class="grp-h"><span>GROUP {_esc(letter)}</span>' + (
            f'<span class="pld">{pld}/6</span>' if pld else ""
        ) + "</div>"

        fx_html = [_fixture_html(f, flags, owner) for f in fixtures.get(letter, [])]

        rows_html = []
        for t in members:
            name = t["name"]
            s = status.get(name) or {}
            cls = "row"
            if s.get("alive") is False:
                cls += " out"
            elif s.get("phase") == "ko":
                cls += " adv"
            pos = pos_of.get(name)
            tm = _esc(name) + (f" <small>{pos}{_ord(pos)}</small>" if pos else "")
            rows_html.append(
                f'<div class="{cls}"><span class="fl">{flags.get(name,"")}</span>'
                f'<span class="tm">{tm}</span>'
                f'<span class="ow">{_esc(owner.get(name,"—"))}</span>'
                f'<span class="g">{goals.get(name,0)}⚽</span></div>'
            )

        cards.append(
            f'<div class="grp">{head}'
            '<div class="grp-sec">Fixtures (UK time)</div>' + "".join(fx_html)
            + '<div class="grp-sec">Latest scores</div>' + "".join(rows_html)
            + "</div>"
        )

    return (
        CSS + '<div class="wc"><div class="wc-grid">' + "".join(cards) + "</div>"
        '<div class="legend">🟨 goals · pill = owner · dimmed = knocked out · '
        'highlighted = through to the knockouts</div></div>'
    )


def render_groups(b: dict) -> None:
    st.markdown(groups_html(b), unsafe_allow_html=True)


def _ord(n: int | None) -> str:
    if not n:
        return ""
    return {1: "st", 2: "nd", 3: "rd"}.get(n, "th")


def _side(team: str, b: dict, score: int | None, won: bool) -> str:
    valid = b["_valid"]
    flags, owner = b["flags"], b["owner"]
    cls = "row win" if won else "row"
    sc = f'<span class="sc">{score}</span>' if score is not None else '<span class="sc"></span>'
    if _is_real(team, valid):
        return (
            f'<div class="{cls}"><span class="fl">{flags.get(team,"")}</span>'
            f'<span class="tm">{_esc(team)}</span>'
            f'<span class="ow">{_esc(owner.get(team,"—"))}</span>{sc}</div>'
        )
    # Unresolved slot: no owner yet, so skip the pill (empty pill reads as a skeleton).
    # Keep an empty span to hold the grid column so the score stays aligned.
    return (
        f'<div class="row"><span class="fl">·</span>'
        f'<span class="tm slot">{_esc(team)}</span>'
        f'<span></span>{sc}</div>'
    )


def _by_round(matches: list[dict]) -> dict[str, list[dict]]:
    by_round: dict[str, list[dict]] = {}
    for m in matches:
        by_round.setdefault(m.get("round", ""), []).append(m)
    return by_round


def default_round_key(b: dict) -> str:
    """Earliest knockout round that still has an unplayed match — the 'live' round.

    Drives the round picker's default so the Knockouts tab opens on what's next rather
    than sitting on Round of 32 all tournament. Falls back to the Final once every
    knockout match has a result.
    """
    from data import _on_pitch  # local import to avoid cycle at top

    by_round = _by_round(b["_matches"])
    for round_key, _ in BRACKET_ROUNDS:
        ms = by_round.get(round_key, [])
        if ms and any(_on_pitch(m.get("score")) is None for m in ms):
            return round_key
    return "Final"


def bracket_html(b: dict, rounds: list[str] | None = None, show_headers: bool = True) -> str:
    from data import _on_pitch, _uk_kickoff, _winner_loser  # local import to avoid cycle

    by_round = _by_round(b["_matches"])
    keys = rounds if rounds is not None else [k for k, _ in BRACKET_ROUNDS]
    labels = dict(BRACKET_ROUNDS)

    parts = []
    for round_key in keys:
        ms = by_round.get(round_key, [])
        if not ms:
            continue
        if show_headers:
            parts.append(f'<div class="rnd-h">{_esc(labels.get(round_key, round_key))}</div>')
        for m in ms:
            sc = _on_pitch(m.get("score"))
            s1 = s2 = None
            w1 = w2 = False
            if sc is not None:
                s1, s2 = sc
                winner, _ = _winner_loser(m, sc)
                w1, w2 = (winner == m["team1"]), (winner == m["team2"])
            ko = _uk_kickoff(m.get("date", ""), m.get("time", ""))
            when = (
                f"{ko.strftime('%a')} {ko.day} {ko.strftime('%b')} · {ko.strftime('%H:%M')}"
                if ko else ""
            )
            dt = f'<div class="bm-dt">{_esc(when)}</div>' if when else ""
            parts.append(
                '<div class="bm">' + dt
                + _side(m["team1"], b, s1, w1)
                + '<div class="mid">VS</div>'
                + _side(m["team2"], b, s2, w2)
                + "</div>"
            )
    return CSS + '<div class="wc">' + "".join(parts) + "</div>"


def render_bracket(b: dict, rounds: list[str] | None = None, show_headers: bool = True) -> None:
    st.markdown(bracket_html(b, rounds, show_headers), unsafe_allow_html=True)
