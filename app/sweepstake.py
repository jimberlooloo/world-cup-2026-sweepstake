"""World Cup 2026 family sweepstake — mobile-first Streamlit app.

Reads the player->team allocation from Streamlit Secrets (no names in the repo) and syncs
live results from the openfootball feed on each run. Three tabs: Players (cards + Golden
Boot race), Groups (12 group cards) and Knockouts (the bracket, with a round picker).
See README.md for an overview.
"""
from __future__ import annotations

import html
import os
import sys

import streamlit as st

sys.path.append(os.path.dirname(__file__))
import allocation as alloc  # noqa: E402
import data as feed  # noqa: E402
import wallchart  # noqa: E402

POT = 48
PRIZES = [
    ("🥇", "Winner — owner of the team that lifts the cup", 24),
    ("🥈", "Runner-up — owner of the losing finalist", 12),
    ("🥉", "Third place — owner of the third-place team", 6),
    ("👟", "Golden Boot — player whose 3 teams score the most", 6),
]

st.set_page_config(
    page_title="World Cup 2026 Sweepstake",
    page_icon="🏆",
    layout="centered",  # centered reads best on a phone
    initial_sidebar_state="collapsed",
)

# Trim Streamlit's generous default top padding (96px) so the header sits higher on a phone.
st.markdown(
    "<style>[data-testid='stMainBlockContainer']{padding-top:2.5rem;}</style>",
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- data

@st.cache_data(ttl=600, show_spinner=False)
def load_feed() -> tuple[list[dict], list[dict]]:
    return feed.fetch_teams(), feed.fetch_matches()


def get_state():
    teams, matches = load_feed()
    bundle = feed.overall(teams, matches)
    team_names = [t["name"] for t in teams]
    allocation, is_real = alloc.load_allocation(team_names)
    bundle["allocation"] = allocation
    bundle["owner"] = alloc.owner_of(allocation)
    bundle["is_real"] = is_real
    return bundle


# --------------------------------------------------------------------------- gate

def gate() -> bool:
    """Optional shared-password gate so a public URL doesn't expose family names.

    If `app_password` is set in Streamlit Secrets, visitors must enter it before any
    names render. With no password configured (e.g. local dev) the app is open.
    """
    try:
        password = st.secrets["app_password"] if "app_password" in st.secrets else None
    except Exception:
        password = None
    if not password:
        return True
    if st.session_state.get("authed"):
        return True

    st.title("🏆 World Cup 2026 Sweepstake")
    st.caption("Family members — enter the password to view.")
    entered = st.text_input("Password", type="password", label_visibility="collapsed")
    # Trim surrounding whitespace — mobile keyboards often append a trailing space.
    if entered.strip() == str(password).strip():
        st.session_state["authed"] = True
        st.rerun()
    elif entered:
        st.error("Incorrect password.")
    return False


# ------------------------------------------------------------------------- render

def header(b: dict) -> None:
    st.title("🏆 World Cup 2026")
    left, right = st.columns([3, 1], vertical_alignment="center")
    with left:
        st.markdown(
            f"**{b['played']}/{b['total']}** matches played · "
            f"synced live from [openfootball](https://github.com/openfootball/worldcup.json)"
        )
    with right:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.rerun()
    if not b["is_real"]:
        st.info("Demo allocation (Player 1–16). Add real names in Secrets — see README.", icon="ℹ️")

    with st.expander("💷 £3 to enter · £48 pot · prizes"):
        st.markdown(
            "🎲 3 teams each, drawn at random — no picking, pure luck of the draw.\n\n"
            "👥 16 players sharing all 48 teams:"
        )
        for icon, name, amt in PRIZES:
            st.markdown(f"- {icon} **£{amt}** — {name}")


# Streamlit columns stack vertically on a phone, so the player cards are rendered as
# inline HTML (like the Groups/Knockouts cards) to keep each team on one tidy row.
PLAYERS_CSS = """
<style>
.pl * { box-sizing: border-box; }
.pl { font-family: system-ui, sans-serif; }
.pcard { border:1px solid #2a2a33; border-radius:12px; background:#15151c;
         overflow:hidden; margin-bottom:10px; }
.pcard.gb { border-color:#ffd84d80; }
.pc-h { display:flex; justify-content:space-between; align-items:center;
        padding:9px 14px; background:#1c1c26; }
.pcard.gb .pc-h { background:#ffd84d1a; }
.pc-h .nm { font-weight:800; font-size:15px; color:#fff; }
.pc-h .tot { font-weight:800; font-size:18px; color:#ffd84d; white-space:nowrap; }
.pc-row { display:grid; grid-template-columns:24px 1fr auto auto; gap:8px;
          align-items:center; padding:7px 14px; border-top:1px solid #ffffff10; }
.pc-row .fl { font-size:17px; }
.pc-row .tm { color:#e8e8ef; font-weight:600; font-size:14px; line-height:1.2; }
.pc-row .st { font-size:13px; }
.pc-row .g { color:#ffd84d; font-weight:700; font-size:14px;
             min-width:34px; text-align:right; white-space:nowrap; }
.pl-legend { color:#8a8a96; font-size:11px; margin:2px 2px 0; }
</style>
"""


def _status_dot(s: dict | None) -> str:
    """Per-team progress reduced to one colour dot for the combined-goals cards."""
    if not s:
        return "⚪"
    if s.get("alive") is False:
        return "🔴"
    if s.get("phase") == "ko":
        return "🟢"
    return "⚪"


def _player_card(rank: int, player: str, teams: list[str], total: int,
                 leader: bool, b: dict) -> str:
    goals, status, flags = b["goals"], b["status"], b["flags"]
    rows = []
    for t in sorted(teams, key=lambda x: goals.get(x, 0), reverse=True):
        rows.append(
            f'<div class="pc-row"><span class="fl">{flags.get(t,"")}</span>'
            f'<span class="tm">{html.escape(str(t))}</span>'
            f'<span class="st">{_status_dot(status.get(t))}</span>'
            f'<span class="g">{goals.get(t,0)} ⚽</span></div>'
        )
    badge = " 👟" if leader else ""
    cls = "pcard gb" if leader else "pcard"
    return (
        f'<div class="{cls}"><div class="pc-h">'
        f'<span class="nm">{rank}. {html.escape(str(player))}{badge}</span>'
        f'<span class="tot">{total} ⚽</span></div>'
        + "".join(rows) + "</div>"
    )


def render_players(b: dict) -> None:
    goals = b["goals"]
    standings = sorted(
        ((p, ts, sum(goals.get(t, 0) for t in ts)) for p, ts in b["allocation"].items()),
        key=lambda x: x[2],
        reverse=True,
    )
    top = standings[0][2] if standings else 0
    leaders = {p for p, _, tot in standings if tot == top and top > 0}

    st.subheader("👟 Golden Boot")
    st.caption("£6 to the player whose three teams score the most goals between them.")
    if top == 0:
        st.info("No goals yet — back once the action kicks off!", icon="⚽")
    else:
        st.success(f"Leading on **{top}** goals: {', '.join(sorted(leaders))}", icon="👟")

    cards = [
        _player_card(rank, p, ts, tot, p in leaders, b)
        for rank, (p, ts, tot) in enumerate(standings, 1)
    ]
    st.markdown(
        PLAYERS_CSS + '<div class="pl">' + "".join(cards)
        + '<div class="pl-legend">🟢 in the knockouts · ⚪ group stage · '
        "🔴 knocked out · ⚽ = each team's tournament goals</div></div>",
        unsafe_allow_html=True,
    )


def knockouts(b: dict) -> None:
    """Knockout bracket with a single-line round picker (pills) — phone-friendly nav.

    Defaults to the live round; one round shown at a time so the pills fit on one row.
    """
    picks = wallchart.ROUND_PICKS  # [(short label, feed round key), ...]
    by_short = dict(picks)
    options = [short for short, _ in picks]
    default = next(
        (short for short, key in picks if key == wallchart.default_round_key(b)),
        options[0],
    )
    choice = st.pills(
        "round", options, default=default, label_visibility="collapsed"
    ) or default
    wallchart.render_bracket(b, rounds=[by_short[choice]], show_headers=False)


def main() -> None:
    if not gate():
        return
    try:
        b = get_state()
    except Exception as exc:  # network / feed hiccup — fail friendly on mobile
        st.title("🏆 World Cup 2026 Sweepstake")
        st.error(f"Couldn't sync results right now: {exc}\n\nPull to refresh in a moment.")
        return

    header(b)
    tab_players, tab_groups, tab_ko = st.tabs(["🏆 Players", "🟩 Groups", "🥊 Knockouts"])
    with tab_players:
        render_players(b)
    with tab_groups:
        wallchart.render_groups(b)
    with tab_ko:
        knockouts(b)


if __name__ == "__main__":
    main()
