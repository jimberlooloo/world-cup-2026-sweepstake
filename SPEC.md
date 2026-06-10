# SPEC — World Cup 2026 Family Sweepstake

The contract. Anything not covered here is flagged before building.

## What it is
A mobile-first Streamlit app for a 16-player family sweepstake over the 48-team FIFA World
Cup 2026. Each player owns 3 teams, drawn at random. The app syncs live results and shows
who's winning — especially the Golden Boot race.

## Rules (display only)
- 💷 £3 to enter · £48 pot.
- 🎲 3 teams each, drawn at random — no picking.
- 👥 16 players share all 48 teams.
- 🏆 Prizes, all paid to the **team's owner**:
  - 🥇 1st place team — £24
  - 🥈 2nd place team — £12
  - 🥉 3rd place team — £6
  - 👟 Golden Boot team (most goals) — £6
- No payment tracking in the app (entry/pot are informational).

## Data
- Source: openfootball public-domain feed
  (`raw.githubusercontent.com/openfootball/worldcup.json/master/2026/`) — **no API key**.
  - `worldcup.teams.json` — 48 teams (name, flag emoji, fifa_code, group).
  - `worldcup.json` — all matches; a `score` object appears once played.
- Synced on each app run, cached 10 min, with a manual **Refresh** button.
- On-pitch goals = `score.et` if present else `score.ft` (penalty shootout `p` excluded).
- Derived: per-team goal tally (Golden Boot), group standings, best-effort knockout
  advanced/eliminated status.
- Network/feed failure degrades gracefully (friendly message, no crash).

## Allocation (no personal info in the repo)
- The player→team mapping lives in **Streamlit Secrets** under `[sweepstake]`, never git.
- Two accepted shapes: `players` + `seed` (app draws), or an explicit `[sweepstake.allocation]`
  mapping. See `.streamlit/secrets.toml.example`.
- `draw.py` turns 16 real names into a paste-ready Secrets block (pure-luck draw, reproducible
  from the seed).
- With no secrets configured the app falls back to placeholder **Player 1–16** so it runs out
  of the box, and shows a notice.

## UI (mobile-first, centered, two tabs)
- **Header:** title, sync status (`played/total`), Refresh, prize/rules expander.
- **🏆 Players tab:**
  - *Golden Boot race* — teams ranked by goals, leader highlighted with owner.
  - *Player cards* — each player ranked by their 3 teams' combined goals; per-team goals +
    live status chip.
- **📋 Planner tab:** the full 48-team sheet (flag, country, group, owner, goals, status),
  plus a group-standings expander.

## Deploy
- Streamlit Community Cloud, entry `app/sweepstake.py`, lean `requirements.txt`.
- Real allocation pasted into the app's Secrets panel. Repo stays public and clean.

## Out of scope (v1)
Payment tracking, login/auth, editing results in-app, push notifications, historical archive.
