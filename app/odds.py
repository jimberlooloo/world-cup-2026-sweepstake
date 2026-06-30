"""Bookmaker odds for the FIFA World Cup 2026 — outright winner market.

Uses the free tier of the-odds-api.com (500 requests/month). The API key is
read from Streamlit Secrets as `odds_api_key`. If the key is absent or the
request fails, all functions return None gracefully.

Cached for 6 hours to conserve the free quota (~4 fetches/day).
"""
from __future__ import annotations

import streamlit as st

ODDS_API = "https://api.the-odds-api.com/v4"
# Odds API sport key for FIFA World Cup 2026 outright winner
SPORT = "soccer_fifa_world_cup_winner"

# Map Odds API team names -> our openfootball names where they differ
ODDS_TO_OF: dict[str, str] = {
    "United States": "USA",
    "Türkiye": "Turkey",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Congo DR": "DR Congo",
    "Czech Republic": "Czech Republic",
}


def _api_key() -> str | None:
    try:
        return st.secrets.get("odds_api_key") or None
    except Exception:
        return None


def _norm(name: str) -> str:
    return ODDS_TO_OF.get(name, name)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_favourites() -> dict[str, str] | None:
    """Return {prize_label: 'Team · odds'} for Winner, Runner-up, Third place.

    Uses the outright winner market — only Winner is directly available.
    Runner-up and Third place are inferred as 2nd and 3rd shortest-odds teams.
    Returns None if no API key or request fails.
    """
    key = _api_key()
    if not key:
        return None
    try:
        import requests
        resp = requests.get(
            f"{ODDS_API}/sports/{SPORT}/odds",
            params={"apiKey": key, "regions": "uk", "markets": "outrights", "oddsFormat": "decimal"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    # Aggregate implied probability per team across all bookmakers
    prob: dict[str, float] = {}
    for event in data:
        for bm in event.get("bookmakers", []):
            for market in bm.get("markets", []):
                if market.get("key") != "outrights":
                    continue
                for outcome in market.get("outcomes", []):
                    name = _norm(outcome.get("name", ""))
                    price = outcome.get("price", 0)
                    if price > 1:
                        p = 1 / price
                        if p > prob.get(name, 0):
                            prob[name] = p

    if not prob:
        return None

    ranked = sorted(prob.items(), key=lambda kv: -kv[1])

    def fmt(team: str, p: float) -> str:
        return f"{team} · {round(p * 100)}% chance"

    result = {}
    if len(ranked) >= 1:
        result["🥇 Winner"] = fmt(*ranked[0])
    if len(ranked) >= 2:
        result["🥈 Runner-up"] = fmt(*ranked[1])
    if len(ranked) >= 3:
        result["🥉 Third place"] = fmt(*ranked[2])
    return result
