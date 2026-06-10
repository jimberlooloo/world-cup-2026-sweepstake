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

# Knockout rounds in display order, with the short label shown on the chart.
BRACKET_ROUNDS = [
    ("Round of 32", "Round of 32"),
    ("Round of 16", "Round of 16"),
    ("Quarter-final", "Quarter-finals"),
    ("Semi-final", "Semi-finals"),
    ("Match for third place", "Third-place play-off"),
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
.rnd-h { color:#16a35a; font-weight:800; text-transform:uppercase; letter-spacing:1px;
         font-size:13px; margin: 16px 2px 8px; }
.bm { border:1px solid #1f7a4d; border-radius:10px; background:#0f3d28; margin-bottom:8px; }
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


def groups_html(b: dict) -> str:
    teams, flags, owner, goals = b["teams"], b["flags"], b["owner"], b["goals"]
    status, standings = b["status"], b["standings"]

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
        members = sorted(
            by_group[letter], key=lambda t: pos_of.get(t["name"], 99)
        )
        pld = played_in.get(letter, 0)
        head = f'<div class="grp-h"><span>GROUP {_esc(letter)}</span>' + (
            f'<span class="pld">{pld}/3</span>' if pld else ""
        ) + "</div>"
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
        cards.append(f'<div class="grp">{head}{"".join(rows_html)}</div>')

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
    return (
        f'<div class="row"><span class="fl">·</span>'
        f'<span class="tm slot">{_esc(team)}</span>'
        f'<span class="ow"></span>{sc}</div>'
    )


def bracket_html(b: dict) -> str:
    from data import _on_pitch, _winner_loser  # local import to avoid cycle at top

    matches = b["_matches"]
    by_round: dict[str, list[dict]] = {}
    for m in matches:
        by_round.setdefault(m.get("round", ""), []).append(m)

    parts = []
    for round_key, label in BRACKET_ROUNDS:
        ms = by_round.get(round_key, [])
        if not ms:
            continue
        parts.append(f'<div class="rnd-h">{_esc(label)}</div>')
        for m in ms:
            sc = _on_pitch(m.get("score"))
            s1 = s2 = None
            w1 = w2 = False
            if sc is not None:
                s1, s2 = sc
                winner, _ = _winner_loser(m, sc)
                w1, w2 = (winner == m["team1"]), (winner == m["team2"])
            parts.append(
                '<div class="bm">'
                + _side(m["team1"], b, s1, w1)
                + '<div class="mid">VS</div>'
                + _side(m["team2"], b, s2, w2)
                + "</div>"
            )
    return CSS + '<div class="wc">' + "".join(parts) + "</div>"


def render_bracket(b: dict) -> None:
    st.markdown(bracket_html(b), unsafe_allow_html=True)
