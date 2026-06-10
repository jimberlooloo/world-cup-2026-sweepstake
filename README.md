# 🏆 World Cup 2026 — Family Sweepstake

A mobile-first [Streamlit](https://streamlit.io) app for a 16-player family sweepstake over
the 48-team FIFA World Cup 2026. Each player owns 3 teams drawn at random; the app syncs live
results from a free public feed and lays them out like a printed wall chart.

> 💷 £3 to enter · £48 pot — 🥇 £24 · 🥈 £12 · 🥉 £6 (to the team's owner) ·
> 👟 Golden Boot £6 (to the player whose 3 teams score the most combined goals)

## What you'll see
Three mobile-first tabs:
- **🏆 Players** — every player ranked by their three teams' combined goals; the leader holds
  the **Golden Boot**.
- **🟩 Groups** — a card per group with all 6 fixtures (UK kickoff times + live scores) and a
  latest-scores standings, owner names shown against each team.
- **🥊 Knockouts** — the bracket, one round at a time (Round of 32 → Final) via a round picker.
  Placeholder slots fill in with the real teams and owners as the feed resolves them.

## How it works
- **Results** sync on each run from the public-domain
  [openfootball](https://github.com/openfootball/worldcup.json) JSON feed — **no API key**.
  Cached 10 minutes; a **Refresh** button forces a re-sync.
- **Allocation** (who owns which teams) lives in **Streamlit Secrets**, so the repo holds
  **no real names**. With no secrets set, it shows placeholder Player 1–16.
- **Privacy on a public URL:** set `app_password` in Secrets and the app asks for a shared
  password before any names render — so a public link doesn't expose family names. Omit it to
  leave the app open.

## Run it locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/sweepstake.py        # runs out of the box with Player 1–16
```
To use real names locally, copy the example secrets and edit (this file is gitignored):
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

## Do the real draw
Run the draw with your 16 family names — it prints a ready-to-paste Secrets block:
```bash
python draw.py "Alice, Bob, Carol, Dan, Eve, Frank, Grace, Heidi, Ivan, Judy, Mallory, Niaj, Olivia, Peggy, Rupert, Sybil"
# or:  python draw.py --names-file names.txt
# add --explicit to emit the fixed mapping instead of names+seed
```
The draw is pure luck but **reproducible** from the seed, so it can't be disputed. Paste the
output into the deployed app's Secrets panel (or `.streamlit/secrets.toml` locally).

## Deploy (Streamlit Community Cloud)
1. Push this repo to GitHub (public is fine — it has no personal data).
2. On [share.streamlit.io](https://share.streamlit.io), create an app from the repo with main
   file `app/sweepstake.py`.
3. In the app's **Secrets**, paste your `[sweepstake]` block from `draw.py`, and set
   `app_password` to a shared password.
4. Share the URL **and** the password with the family — open it on a phone.
