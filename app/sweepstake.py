"""World Cup 2026 family sweepstake — mobile-first Streamlit app.

Reads the player->team allocation from Streamlit Secrets (no names in the repo) and syncs
live results from the openfootball feed on each run. Two tabs: Players (cards + Golden Boot
race) and Planner (the full 48-team sheet). See README.md for an overview.
"""
from __future__ import annotations

import os
import sys

import pandas as pd
import streamlit as st

sys.path.append(os.path.dirname(__file__))
import allocation as alloc  # noqa: E402
import data as feed  # noqa: E402

POT = 48
PRIZES = [
    ("🥇", "1st place team", 24),
    ("🥈", "2nd place team", 12),
    ("🥉", "3rd place team", 6),
    ("👟", "Golden Boot team (most goals)", 6),
]

st.set_page_config(
    page_title="World Cup 2026 Sweepstake",
    page_icon="🏆",
    layout="centered",  # centered reads best on a phone
    initial_sidebar_state="collapsed",
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

def status_chip(s: dict | None) -> str:
    if not s:
        return "⚪ —"
    alive = s.get("alive")
    label = s.get("label", "")
    if alive is False:
        return f"🔴 {label or 'out'}"
    if s.get("phase") == "ko":
        return f"🟢 {label or 'in knockouts'}"
    return f"⚪ {label or 'group stage'}"


def header(b: dict) -> None:
    st.title("🏆 World Cup 2026")
    st.caption("Family Sweepstake")
    left, right = st.columns([3, 1])
    with left:
        st.markdown(
            f"**{b['played']}/{b['total']}** matches played · "
            f"synced live from [openfootball](https://github.com/openfootball/worldcup.json)"
        )
    with right:
        if st.button("🔄 Refresh", width="stretch"):
            st.cache_data.clear()
            st.rerun()
    if not b["is_real"]:
        st.info("Demo allocation (Player 1–16). Add real names in Secrets — see README.", icon="ℹ️")

    with st.expander("💷 £3 to enter · £48 pot · prizes"):
        st.markdown(
            "🎲 3 teams each, drawn at random — no picking, pure luck of the draw.\n\n"
            "👥 16 players sharing all 48 teams. All prizes go to the **owner of the team**:"
        )
        for icon, name, amt in PRIZES:
            st.markdown(f"- {icon} **{name}** — £{amt}")


def golden_boot_race(b: dict) -> None:
    goals, owner, flags = b["goals"], b["owner"], b["flags"]
    ranked = sorted(
        [(t, goals.get(t, 0)) for t in [x["name"] for x in b["teams"]]],
        key=lambda x: x[1],
        reverse=True,
    )
    top_goals = ranked[0][1] if ranked else 0
    st.subheader("👟 Golden Boot race")
    if top_goals == 0:
        st.caption("No goals yet — back tomorrow once the action kicks off!")
    else:
        leaders = [t for t, g in ranked if g == top_goals]
        who = ", ".join(f"{flags.get(t,'')} {t} ({owner.get(t,'?')})" for t in leaders)
        st.success(f"Leading on **{top_goals}** goals: {who}", icon="👟")

    rows = [
        {
            "": flags.get(t, ""),
            "Team": t,
            "⚽": g,
            "Owner": owner.get(t, "—"),
        }
        for t, g in ranked[:12]
    ]
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        column_config={"⚽": st.column_config.NumberColumn(width="small")},
    )


def player_cards(b: dict) -> None:
    goals, status, flags = b["goals"], b["status"], b["flags"]
    standings = []
    for player, teams in b["allocation"].items():
        total = sum(goals.get(t, 0) for t in teams)
        standings.append((player, teams, total))
    standings.sort(key=lambda x: x[2], reverse=True)

    st.subheader("👥 Players — combined goals")
    st.caption("Ranked by their three teams' total goals so far.")
    for rank, (player, teams, total) in enumerate(standings, 1):
        with st.container(border=True):
            top = st.columns([3, 1])
            top[0].markdown(f"**{rank}. {player}**")
            top[1].markdown(f"### {total} ⚽")
            for t in sorted(teams, key=lambda x: goals.get(x, 0), reverse=True):
                c = st.columns([3, 1, 3])
                c[0].markdown(f"{flags.get(t,'')} **{t}**")
                c[1].markdown(f"{goals.get(t,0)} ⚽")
                c[2].caption(status_chip(status.get(t)))


def planner(b: dict) -> None:
    goals, owner, status, flags = b["goals"], b["owner"], b["status"], b["flags"]
    st.subheader("📋 The planner — all 48 teams")
    rows = []
    for t in b["teams"]:
        name = t["name"]
        s = status.get(name)
        rows.append(
            {
                "": flags.get(name, ""),
                "Country": name,
                "Grp": t.get("group", ""),
                "Owner": owner.get(name, "—"),
                "⚽": goals.get(name, 0),
                "Status": status_chip(s),
            }
        )
    df = pd.DataFrame(rows).sort_values(["Owner", "Country"], kind="stable")
    st.dataframe(df, hide_index=True, width="stretch", height=560)

    with st.expander("📊 Group standings"):
        for group, table in sorted(b["standings"].items()):
            st.markdown(f"**{group}**")
            srows = [
                {
                    "": flags.get(r["team"], ""),
                    "Team": r["team"],
                    "P": r["p"], "W": r["w"], "D": r["d"], "L": r["l"],
                    "GD": r["gd"], "Pts": r["pts"], "Owner": owner.get(r["team"], "—"),
                }
                for r in table
            ]
            st.dataframe(pd.DataFrame(srows), hide_index=True, width="stretch")


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
    tab_players, tab_planner = st.tabs(["🏆 Players", "📋 Planner"])
    with tab_players:
        golden_boot_race(b)
        st.divider()
        player_cards(b)
    with tab_planner:
        planner(b)


if __name__ == "__main__":
    main()
