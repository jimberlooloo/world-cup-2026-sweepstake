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
import trophies  # noqa: E402
import wallchart  # noqa: E402

POT = 48

st.set_page_config(
    page_title="World Cup 2026 Sweepstake",
    page_icon="🏆",
    layout="centered",  # centered reads best on a phone
    initial_sidebar_state="collapsed",
)

# Trim Streamlit's generous default top padding (96px) so the header sits higher on a phone,
# and keep the one header column-row (matches count + Refresh) on a single line on mobile
# rather than letting Streamlit stack it. The header is the app's only st.columns row.
st.markdown(
    "<style>"
    "[data-testid='stMainBlockContainer']{padding-top:2.5rem;}"
    "[data-testid='stMainBlockContainer'] h1"
    "{font-size:2rem;line-height:1.2;white-space:nowrap;padding:0 0 .3rem;}"
    "[data-baseweb='tab-list']{gap:6px;}"  # fit all 5 tabs across a phone, no swipe
    "[data-testid='stHorizontalBlock']{flex-wrap:nowrap;align-items:center;}"
    "[data-testid='stHorizontalBlock'] [data-testid='stColumn']{min-width:0;}"
    # Right column (btn_group) pushes its content to the right
    "[data-testid='stHorizontalBlock']:first-of-type>[data-testid='stColumn']:last-child"
    "{display:flex;justify-content:flex-end;}"
    # Inner button row: no gap, buttons sit flush together
    "[data-testid='stHorizontalBlock']:first-of-type>[data-testid='stColumn']:last-child"
    " [data-testid='stHorizontalBlock']{gap:4px!important;}"
    # Flat ghost icon buttons in the header — no border, no background box
    "[data-testid='stHorizontalBlock'] button"
    "{padding:0.3rem 0.4rem!important;min-height:0!important;line-height:1!important;"
    "font-size:1.2rem!important;background:transparent!important;"
    "border:none!important;box-shadow:none!important;}"
    "[data-testid='stHorizontalBlock'] button:hover"
    "{background:rgba(255,255,255,0.08)!important;}"
    "[data-testid='stHorizontalBlock'] [data-testid='stPopover']{display:flex;}"
    "</style>",
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

    The password may also be passed as a `?pw=` URL query param so the family can bookmark
    a one-tap link. It's left in the URL on purpose: every fresh session (browser refresh,
    pull-to-refresh, app wake-up) re-reads it and logs straight back in. Fine here since the
    only thing it guards is family names, not real credentials.
    """
    try:
        password = st.secrets["app_password"] if "app_password" in st.secrets else None
    except Exception:
        password = None
    if not password:
        return True
    if st.session_state.get("authed"):
        return True

    # One-tap link via ?pw= (kept in the URL so reloads stay logged in).
    qp = st.query_params.get("pw")
    if qp is not None and str(qp).strip() == str(password).strip():
        st.session_state["authed"] = True
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

MONEY_CSS = """
<style>
.mny { border:1px solid #1f7a4d; border-radius:12px; background:#0f3d28;
       overflow:hidden; margin-bottom:10px; }
.mny-h { background:#16a35a; color:#fff; font-weight:800; font-size:14px;
         padding:7px 12px; letter-spacing:.3px; }
.mn-row { padding:7px 12px; border-top:1px solid #1f7a4d33; }
.mn-top { display:flex; justify-content:space-between; align-items:baseline; gap:8px; }
.mn-prize { font-weight:600; color:#eafff3; font-size:14px; }
.mn-amt { color:#ffd84d; font-weight:800; font-size:14px; white-space:nowrap; }
.mn-who { color:#9fdcbb; font-size:12px; margin-top:1px; }
.mn-tbd { color:#5fae86; font-size:12px; font-style:italic; margin-top:1px; }
.mn-fav { color:#a0c8ff; font-size:11px; display:block; margin-top:2px; }
.mn-pass { color:#e8a33d; font-size:11px; margin-top:2px; }
.mny-sub { background:#0c3120; color:#9fdcbb; font-size:11px; padding:5px 12px;
           border-top:1px solid #1f7a4d33; }
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


def _choc_holders(b: dict) -> list[str]:
    """First player(s) to have all 3 teams eliminated."""
    try:
        result = trophies.first_all_out(b)
        if (result or {}).get("status") == "won":
            return result.get("holders", [])
    except Exception:
        pass
    return []


def _tiers(scores: dict[str, float]) -> list[list[str]]:
    """Players grouped into tied tiers, best first. A zero score doesn't place at all."""
    live = {p: v for p, v in scores.items() if v > 0}
    return [sorted(p for p, s in live.items() if s == v)
            for v in sorted(set(live.values()), reverse=True)]


def _award(tiers: list[list[str]], taken: set[str]) -> tuple[list[str], list[str]]:
    """Give a prize to the best tier with someone left, since nobody wins twice.

    Returns (holders, passed_over) — passed_over is everyone ranked at or above the
    winning tier who was skipped because they already hold a bigger prize.
    """
    passed: list[str] = []
    for tier in tiers:
        free = [p for p in tier if p not in taken]
        if free:
            return free, passed + [p for p in tier if p in taken]
        passed += tier
    return [], passed


def render_money(b: dict) -> None:
    """Consolidated 'who's winning' view — current holder of every cash prize plus each
    player's provisional winnings.

    One prize each: prizes are settled biggest-first — the three placings, then the rest —
    and anyone already holding a bigger one is passed over so the prize cascades to the next
    player in line. Ties split whatever they land on.

    Once the final is set, both finalists' owners are certain of £18 or £9 even though the
    match decides which, so they're locked out of the lesser prizes straight away.
    """
    goals, owner, allocation, status = b["goals"], b["owner"], b["allocation"], b["status"]
    totals = {p: sum(goals.get(t, 0) for t in ts) for p, ts in allocation.items()}

    fame_tally, shame_tally = trophies.hall_tallies(b)

    def owners_of(label: str) -> list[str]:
        return sorted({owner[t] for t, s in status.items()
                       if (s or {}).get("label") == label and owner.get(t)})

    # Guaranteed £18 or £9 the moment the final is set — the 3rd-place game isn't a guarantee
    # of anything, since 4th place pays nothing, so those owners stay in the running.
    finalists = owners_of("Final")
    final_tbd = (f'{", ".join(finalists)} · the final decides which'
                 if len(finalists) == 2 else "the final decides it")

    # (name, amount, how it's won, what shows until it's decided, ranked tiers of candidates)
    # Order matters: this is the settling order, biggest prize first.
    placings = [
        ("🥇 Winner", 18, "owner of the team that lifts the cup", final_tbd, owners_of("🏆 Champions")),
        ("🥈 Runner-up", 9, "owner of the runner-up", final_tbd, owners_of("🥈 Runner-up")),
        ("🥉 Third place", 6, "owner of the third-place team", "the 3rd-place game decides it", owners_of("🥉 Third place")),
    ]
    others = [
        ("👟 Golden Boot", 6, "3 teams' most combined goals", "no goals yet", _tiers(totals)),
        ("🌟 Hall of Fame", 6, "most fame trophies", "up for grabs", _tiers(fame_tally)),
        ("🙈 Hall of Shame", 3, "most shame trophies (£3 back)", "up for grabs", _tiers(shame_tally)),
    ]

    try:
        import odds as _odds_mod
        favourites = _odds_mod.fetch_favourites() or {}
    except Exception:
        favourites = {}

    money: dict[str, float] = {}
    taken: set[str] = set()  # holds a prize already, so out of the running for a smaller one
    held: dict[str, str] = {}  # player -> the prize keeping them out, for the passed-over note
    settled = []
    # A placing can't cascade — it belongs to whoever owns that team — so it only ever blocks
    # a player from a later, smaller prize. Settle all three before anything else.
    for name, amt, rule, tbd, holders in placings:
        holders = [h for h in holders if h not in taken]
        taken.update(holders)
        held.update({h: name for h in holders})
        settled.append((name, amt, rule, tbd, holders, []))
    # The rest cascade past anyone with a placing banked or guaranteed by reaching the final.
    for name, amt, rule, tbd, tiers in others:
        holders, passed = _award(tiers, taken | set(finalists))
        taken.update(holders)
        held.update({h: name for h in holders})
        settled.append((name, amt, rule, tbd, holders, passed))

    def why(p: str) -> str:
        # A finalist's placing isn't settled yet, but £18-or-£9 is already banked either way.
        return "in the final" if p in finalists else held.get(p, "a bigger prize")

    rows = []
    for name, amt, rule, tbd, holders, passed in settled:
        note = ""
        if holders:
            for h in holders:
                money[h] = money.get(h, 0) + amt / len(holders)
            line = (f'<div class="mn-who">{html.escape(rule)} · '
                    f'{", ".join(html.escape(h) for h in holders)}</div>')
        else:
            line = f'<div class="mn-tbd">{html.escape(rule)} · {html.escape(tbd)}</div>'
        if passed:
            note = ('<div class="mn-pass">↩ passed over: '
                    + ", ".join(f'{html.escape(p)} ({html.escape(why(p))})' for p in passed)
                    + "</div>")
        fav = favourites.get(name)
        if fav:
            # fav is "Team (odds)" — extract team to find owner
            fav_team = fav.split(" · ")[0]
            fav_owner = owner.get(fav_team, "")
            owner_str = f" · owned by {fav_owner}" if fav_owner else ""
            fav_html = (f'<span class="mn-fav">🎰 Bookies fav: {html.escape(fav)}{html.escape(owner_str)}</span>')
        else:
            fav_html = ""
        rows.append(f'<div class="mn-row"><div class="mn-top"><span class="mn-prize">'
                    f'{name}</span><span class="mn-amt">£{amt}</span></div>{line}{note}{fav_html}</div>')

    # The Chocolate Bar is a booby prize with no cash, so it sits outside the one-prize rule.
    choc = _choc_holders(b)
    choc_line = (f'<div class="mn-who">first to have all 3 teams knocked out · '
                 f'{", ".join(html.escape(h) for h in choc)}</div>' if choc else
                 '<div class="mn-tbd">first to have all 3 teams knocked out · still teams alive</div>')
    rows.append('<div class="mn-row"><div class="mn-top"><span class="mn-prize">'
                f'🍫 Chocolate Bar</span><span class="mn-amt">🍫</span></div>{choc_line}</div>')

    def fmt(x: float) -> str:
        return f"£{x:.0f}" if x == int(x) else f"£{x:.2f}"

    standings = ""
    if money:
        ranked = sorted(money.items(), key=lambda kv: (-kv[1], kv[0]))
        standings = ('<div class="lb"><div class="lb-h">In the money (provisional)</div>'
                     + "".join(f'<div class="lb-row"><span class="lb-nm">{html.escape(p)}</span>'
                               f'<span class="lb-ct" style="color:#ffd84d">{fmt(v)}</span></div>'
                               for p, v in ranked) + "</div>")

    st.markdown(
        MONEY_CSS
        + '<div class="mny"><div class="mny-h">Prizes · current leaders</div>'
        + '<div class="mny-sub">One prize each — you keep your biggest, and anything else '
          'passes down to the next player in line.</div>'
        + "".join(rows) + "</div>" + standings,
        unsafe_allow_html=True,
    )


NEXT_CSS = """
<style>
.nextm { border:1px solid #1f7a4d; border-radius:12px; background:#0f3d28;
         padding:9px 14px; margin:2px 0 6px; }
.nm-when { color:#7fd9a8; font-size:11px; font-weight:700; text-transform:uppercase;
           letter-spacing:.8px; text-align:center; margin-bottom:6px; }
.nm-row { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:10px; }
.nm-t { font-size:14px; font-weight:700; color:#eafff3; line-height:1.15; }
.nm-t small { display:block; color:#9fdcbb; font-weight:500; font-size:11px; margin-top:1px; }
.nm-t1 { text-align:right; }
.nm-t2 { text-align:left; }
.nm-fl { font-size:16px; }
.nm-v { color:#5fae86; font-weight:700; font-size:12px; }
.livm { border:1px solid #c0392b66; border-radius:12px; background:#2d0b0b;
        padding:9px 14px; margin:2px 0 6px; }
.lv-when { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.8px;
           text-align:center; margin-bottom:6px; color:#ff6b6b; }
.lv-dot { display:inline-block; width:7px; height:7px; border-radius:50%;
          background:#ff4444; margin-right:5px;
          animation:lv-pulse 1.4s ease-in-out infinite; }
@keyframes lv-pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
.lv-score { color:#fff; font-weight:900; font-size:22px; line-height:1; }
.lv-hint { color:#c0392b99; font-size:10px; text-align:center; margin-top:5px;
           font-style:italic; }
</style>
"""


def next_match(b: dict) -> None:
    """LIVE banner during a match; 'Next up' banner otherwise."""
    flags, owner, valid = b["flags"], b["owner"], b["_valid"]

    def side(team: str) -> tuple[str, str, str]:
        if team in valid:
            return flags.get(team, ""), html.escape(str(team)), html.escape(owner.get(team, "—"))
        return "", html.escape(str(team)), ""

    live_matches = b.get("_live", [])
    if live_matches:
        cards = []
        for lm in live_matches:
            t1, t2 = lm["team1"], lm["team2"]
            s1, s2 = lm["score"][0], lm["score"][1]
            clock = html.escape(lm.get("clock", ""))
            f1, n1, o1 = side(t1)
            f2, n2, o2 = side(t2)
            o1h = f"<small>{o1}</small>" if o1 else ""
            o2h = f"<small>{o2}</small>" if o2 else ""
            head = f'<span class="lv-dot"></span>LIVE' + (f" · {clock}" if clock else "")
            cards.append(
                '<div class="livm">'
                + f'<div class="lv-when">{head}</div>'
                + '<div class="nm-row">'
                + f'<span class="nm-t nm-t1">{n1} <span class="nm-fl">{f1}</span>{o1h}</span>'
                + f'<span class="lv-score">{s1}–{s2}</span>'
                + f'<span class="nm-t nm-t2"><span class="nm-fl">{f2}</span> {n2}{o2h}</span>'
                + "</div>"
                + '<div class="lv-hint">Refresh for latest score</div>'
                + "</div>"
            )
        st.markdown(NEXT_CSS + "".join(cards), unsafe_allow_html=True)
        return

    upcoming = []
    for m in b["_matches"]:
        if feed._on_pitch(m.get("score")) is not None:
            continue
        ko = feed._uk_kickoff(m.get("date", ""), m.get("time", ""))
        if ko is not None:
            upcoming.append((ko, m))
    if not upcoming:
        return
    ko, m = min(upcoming, key=lambda x: x[0])
    when = f"{ko.strftime('%a')} {ko.day} {ko.strftime('%b')} · {ko.strftime('%H:%M')}"
    label = m.get("group") or m.get("round") or ""
    head = f"⚽ Next up · {label} · {when}" if label else f"⚽ Next up · {when}"
    f1, n1, o1 = side(m["team1"])
    f2, n2, o2 = side(m["team2"])
    o1h = f"<small>{o1}</small>" if o1 else ""
    o2h = f"<small>{o2}</small>" if o2 else ""
    st.markdown(
        NEXT_CSS
        + '<div class="nextm">'
        + f'<div class="nm-when">{html.escape(head)}</div>'
        + '<div class="nm-row">'
        + f'<span class="nm-t nm-t1">{n1} <span class="nm-fl">{f1}</span>{o1h}</span>'
        + '<span class="nm-v">v</span>'
        + f'<span class="nm-t nm-t2"><span class="nm-fl">{f2}</span> {n2}{o2h}</span>'
        + "</div></div>",
        unsafe_allow_html=True,
    )


def _share_text(b: dict) -> str:
    """Compact share snapshot — top 5 for goals, fame trophies, shame trophies."""
    goals_by_player = sorted(
        ((p, sum(b["goals"].get(t, 0) for t in ts)) for p, ts in b["allocation"].items()),
        key=lambda x: -x[1],
    )
    fame, shame = trophies.hall_tallies(b)
    top_fame = sorted(fame.items(), key=lambda x: -x[1])[:5]
    top_shame = sorted(shame.items(), key=lambda x: -x[1])[:5]

    lines = [f"🏆 World Cup 2026 Sweepstake", f"{b['played']}/{b['total']} matches played"]
    goals_top = [(p, g) for p, g in goals_by_player[:5] if g > 0]
    if goals_top:
        lines.append("⚽ Goals: " + " · ".join(f"{p} {g}" for p, g in goals_top))
    if top_fame:
        lines.append("🌟 Fame: " + " · ".join(f"{p} {c}" for p, c in top_fame))
    if top_shame:
        lines.append("🙈 Shame: " + " · ".join(f"{p} {c}" for p, c in top_shame))
    # Live match or next match
    live = b.get("_live", [])
    if live:
        for lm in live:
            lines.append(f"🔴 LIVE: {lm['team1']} {lm['score'][0]}–{lm['score'][1]} {lm['team2']}"
                         + (f" · {lm['clock']}" if lm.get("clock") else ""))
    else:
        upcoming = sorted(
            ((feed._uk_kickoff(m.get("date", ""), m.get("time", "")), m)
             for m in b["_matches"] if feed._on_pitch(m.get("score")) is None
             and feed._uk_kickoff(m.get("date", ""), m.get("time", "")) is not None),
            key=lambda x: x[0],
        )
        if upcoming:
            ko, m = upcoming[0]
            when = f"{ko.strftime('%a')} {ko.day} {ko.strftime('%b')} {ko.strftime('%H:%M')}"
            lines.append(f"⚽ Next up: {m['team1']} v {m['team2']} · {when}")
    return "\n".join(lines)


# Newest first. Keep generic — no real names, no personal content.
UPDATES = [
    ("17 Jul", "💷 One prize each — you keep your biggest, the rest passes down the line"),
    ("17 Jul", "🥇 Both finalists' owners are now locked in for £18 or £9"),
    ("30 Jun", "🫀 New: Penalty Loser · 📉 Biggest Collapse · 🧺 Colander"),
    ("30 Jun", "🍫 Chocolate Bar: now goes to the first player with all 3 teams out"),
    ("30 Jun", "💀 New shame trophy: Giant Slain — your top-16 team knocked out by a lower side"),
    ("30 Jun", "🔴 Eliminated teams greyed out with strikethrough on player cards"),
    ("22 Jun", "🚪 New shame trophy: First Out — first team eliminated from the groups"),
    ("22 Jun", "🍫 Wooden Spoon renamed to Chocolate Bar, added to prize list"),
    ("16 Jun", "📅 Next match shown on each player's card"),
    ("13 Jun", "📤 Share button — send a score snapshot to the group"),
    ("13 Jun", "🔴 Live match banner when a game is in progress"),
    ("12 Jun", "🏆 One trophy line per person on Fame & Shame cards"),
    ("12 Jun", "💷 Prize money standings — see who's in the money"),
    ("12 Jun", "🎖️ Trophy standings table in Fame & Shame"),
    ("12 Jun", "🃏 New trophies: Super Sub, Penalty Villain, Ten Men, Mr Everything"),
    ("12 Jun", "🟨 New trophies: Bad Boys, Seeing Red, Playmaker"),
    ("12 Jun", "⚡ Live scores via ESPN — results update within minutes"),
    ("11 Jun", "🏆 Fame & Shame — 34 trophies for every occasion"),
    ("10 Jun", "🗓️ Wall chart — groups, knockouts and Golden Boot race"),
    ("10 Jun", "🎉 Sweepstake launched — 16 players, 48 teams, one winner"),
]

ADD_TO_HOME_HTML = """
<style>
  body{margin:0;background:transparent;font-family:system-ui,sans-serif;font-size:0.95rem;color:#fafafa;}
  .tip{display:none;line-height:1.5;}
  .tip b{color:#fff;}
  .done{display:none;color:#4caf82;}
</style>
<div class="tip" id="ios">
  Tap the <b>Share</b> button <b>&#x2B06;</b> in Safari then choose <b>Add to Home Screen</b>.
</div>
<div class="tip" id="android">
  Tap the <b>&#8942;</b> menu in Chrome then choose <b>Add to Home Screen</b>.
</div>
<div class="tip" id="desktop">
  Open this page on your phone to add it to your home screen.
</div>
<div class="done" id="installed">
  ✅ Already on your home screen.
</div>
<script>
  var ua=navigator.userAgent;
  var standalone=window.navigator.standalone||window.matchMedia('(display-mode:standalone)').matches;
  if(standalone){
    document.getElementById('installed').style.display='block';
  } else if(/iPhone|iPad|iPod/.test(ua)){
    document.getElementById('ios').style.display='block';
  } else if(/Android/.test(ua)){
    document.getElementById('android').style.display='block';
  } else {
    document.getElementById('desktop').style.display='block';
  }
</script>
"""


@st.dialog("Settings")
def settings_dialog() -> None:
    st.markdown("### App updates")
    for date, text in UPDATES:
        st.markdown(f"**{date}** — {text}")
    st.divider()
    st.markdown("### Add to Home Screen")
    st.components.v1.html(ADD_TO_HOME_HTML, height=60)


def header(b: dict) -> None:
    import json
    st.title("🏆 World Cup 2026")
    left, btn_group = st.columns([3, 2], vertical_alignment="center")
    with left:
        st.markdown(f"**{b['played']}/{b['total']}** matches played")
    with btn_group:
        refresh_col, share_col, updates_col = st.columns(3, vertical_alignment="center")
    with refresh_col:
        if st.button("🔄", help="Refresh"):
            st.cache_data.clear()
            st.rerun()
    with share_col:
        share_json = json.dumps(_share_text(b))
        st.components.v1.html(
            f"""<style>
            html,body{{margin:0;padding:0;width:36px;overflow:hidden;}}
            body{{background:transparent;display:flex;justify-content:center;
                 align-items:center;height:36px;}}
            button{{background:transparent;border:none;border-radius:6px;
                   color:#fafafa;font-size:19px;padding:5px 6px;cursor:pointer;
                   line-height:1;font-family:system-ui,sans-serif;display:flex;
                   align-items:center;justify-content:center;}}
            button:hover{{background:rgba(255,255,255,0.08);}}
            </style>
            <button onclick="share()" title="Share">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" stroke-width="2.2"
                stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/>
                <polyline points="16 6 12 2 8 6"/>
                <line x1="12" y1="2" x2="12" y2="15"/>
              </svg>
            </button>
            <script>
            function share(){{
              var text={share_json};
              var nav=(window.top&&window.top.navigator)||navigator;
              if(nav.share){{
                nav.share({{title:'World Cup 2026 Sweepstake',text:text}}).catch(function(){{}});
              }}else{{
                navigator.clipboard.writeText(text)
                  .then(function(){{alert('Copied to clipboard!');}})
                  .catch(function(){{alert('Share not supported on this browser.');}});
              }}
            }}
            </script>""",
            height=36,
        )
    with updates_col:
        if st.button("⋮", help="Settings"):
            settings_dialog()
    next_match(b)
    if not b["is_real"]:
        st.info("Demo allocation (Player 1–16). Add real names in Secrets — see README.", icon="ℹ️")

    with st.expander("💷 £48 pot · prizes & leaders"):
        render_money(b)


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
.pc-row.out { opacity:0.38; }
.pc-row.out .tm { text-decoration:line-through; }
.pc-row.out .g { color:#888; }
.pl-legend { color:#8a8a96; font-size:11px; margin:2px 2px 0; }
.pc-next { padding:6px 14px 8px; border-top:1px solid #ffffff10;
           color:#8a8a96; font-size:12px; }
.pc-next b { color:#c8c8d4; font-weight:600; }
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


def _player_next(teams: list[str], b: dict) -> str:
    """Return a formatted 'Next: ...' string for this player's soonest unplayed match."""
    team_set = set(teams)
    upcoming = []
    for m in b.get("_matches", []):
        if {m.get("team1"), m.get("team2")} & team_set:
            if feed._on_pitch(m.get("score")) is not None:
                continue  # already played
            ko = feed._uk_kickoff(m.get("date", ""), m.get("time", ""))
            if ko is not None:
                upcoming.append((ko, m))
    if not upcoming:
        return ""
    ko, m = min(upcoming, key=lambda x: x[0])
    flags = b.get("flags", {})
    f1 = flags.get(m["team1"], "")
    f2 = flags.get(m["team2"], "")
    when = f"{ko.strftime('%a')} {ko.day} {ko.strftime('%b')} · {ko.strftime('%H:%M')}"
    teams_str = f"{f1} {html.escape(str(m['team1']))} v {f2} {html.escape(str(m['team2']))}"
    return f'<div class="pc-next">⚽ Next: <b>{teams_str}</b> · {when}</div>'


def _player_card(rank: int, player: str, teams: list[str], total: int,
                 leader: bool, b: dict) -> str:
    goals, status, flags = b["goals"], b["status"], b["flags"]
    rows = []
    for t in sorted(teams, key=lambda x: goals.get(x, 0), reverse=True):
        eliminated = (status.get(t) or {}).get("alive") is False
        row_cls = "pc-row out" if eliminated else "pc-row"
        rows.append(
            f'<div class="{row_cls}"><span class="fl">{flags.get(t,"")}</span>'
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
        + "".join(rows)
        + _player_next(teams, b)
        + "</div>"
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
    tab_players, tab_groups, tab_ko, tab_fame, tab_shame = st.tabs(
        ["🏆 Players", "🟩 Groups", "🥊 Knockouts", "🌟 Fame", "🙈 Shame"]
    )
    with tab_players:
        render_players(b)
    with tab_groups:
        wallchart.render_groups(b)
    with tab_ko:
        knockouts(b)
    with tab_fame:
        trophies.render_fame(b)
    with tab_shame:
        trophies.render_shame(b)


if __name__ == "__main__":
    main()
