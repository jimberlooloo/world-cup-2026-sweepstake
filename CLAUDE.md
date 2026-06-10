# Project guide

Mobile-first **Streamlit** family sweepstake for the 48-team **FIFA World Cup 2026**. 16 players,
3 teams each (random draw), live results synced from the free public-domain
[openfootball](https://github.com/openfootball/worldcup.json) JSON feed.

This is a **public repo by design**: only generic, public-facing content is committed —
**nothing sensitive or family-related** (no real names, no spec/personal docs). Real names
live only in Streamlit Secrets; a public deploy is gated by `app_password`.

## Layout
- `app/sweepstake.py` — the Streamlit app (entry point). Header + two tabs (Players, Planner).
- `app/data.py` — fetch + parse the openfootball feed; per-team goals, standings, KO status.
- `app/allocation.py` — resolve player→team allocation (Secrets first, placeholder draw fallback).
- `draw.py` — CLI to run the real draw and print a paste-ready Streamlit Secrets block.
- `.streamlit/` — theme `config.toml` and `secrets.toml.example`.

## Conventions
- **Public, generic-only:** never commit names, personal data, or family-specific content.
  Real names/allocation live only in Streamlit Secrets (`.streamlit/secrets.toml` is
  gitignored); the committed default is Player 1–16. A public deploy is gated by `app_password`.
- **No API key:** results come from the public feed; never add a paid/keyed source without asking.
- **Mobile-first:** centered layout, no reliance on the sidebar, compact rows.
- **Marts of truth:** goals/status are derived in `data.py`; the app only renders.
- **Reviewed changes:** work on a branch, open a PR with an honest description; human merges.

## Run
See the README "Run it" section. Entry point is `app/sweepstake.py`.
