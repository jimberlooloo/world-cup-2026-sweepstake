"""Who owns which teams.

The repo contains **no real names**. The live allocation comes from Streamlit Secrets
(or a local .streamlit/secrets.toml), so personal info never touches git. With no secrets
configured the app falls back to placeholder "Player 1..16" drawn over the real 48 teams,
so it runs out of the box.

Two secret shapes are accepted under a [sweepstake] table:

  # A) names only — the app draws (pure luck, reproducible from the seed)
  [sweepstake]
  seed = 20260611
  players = ["Alice", "Bob", ...]   # 16 names

  # B) an explicit, already-drawn mapping
  [sweepstake.allocation]
  Alice = ["Brazil", "Japan", "Ghana"]
  Bob   = ["France", "Iran", "Norway"]
  ...

Use draw.py to turn 16 real names into either shape, ready to paste into Secrets.
"""
from __future__ import annotations

import random

DEFAULT_SEED = 20260611  # kick-off day; only used for the Player 1..16 placeholder draw
TEAMS_PER_PLAYER = 3


def placeholder_players(n: int = 16) -> list[str]:
    return [f"Player {i}" for i in range(1, n + 1)]


def draw(players: list[str], team_names: list[str], seed: int) -> dict[str, list[str]]:
    """Deterministically deal `TEAMS_PER_PLAYER` teams to each player. Pure luck, but
    reproducible: same players + same seed + same team list => same allocation."""
    need = len(players) * TEAMS_PER_PLAYER
    if len(team_names) < need:
        raise ValueError(
            f"{len(players)} players need {need} teams but only {len(team_names)} available"
        )
    pool = list(team_names)
    random.Random(seed).shuffle(pool)
    alloc: dict[str, list[str]] = {}
    for i, player in enumerate(players):
        start = i * TEAMS_PER_PLAYER
        alloc[player] = sorted(pool[start : start + TEAMS_PER_PLAYER])
    return alloc


def _from_secrets(team_names: list[str]) -> dict[str, list[str]] | None:
    try:
        import streamlit as st

        if "sweepstake" not in st.secrets:
            return None
        cfg = st.secrets["sweepstake"]
    except Exception:
        return None

    if "allocation" in cfg:  # shape B: explicit mapping
        return {p: list(teams) for p, teams in dict(cfg["allocation"]).items()}
    if "players" in cfg:  # shape A: names + draw
        seed = int(cfg.get("seed", DEFAULT_SEED))
        return draw(list(cfg["players"]), team_names, seed)
    return None


def load_allocation(team_names: list[str]) -> tuple[dict[str, list[str]], bool]:
    """Return (player -> [teams], is_real). is_real is False for the placeholder draw."""
    secret = _from_secrets(team_names)
    if secret:
        return secret, True
    return draw(placeholder_players(), team_names, DEFAULT_SEED), False


def owner_of(allocation: dict[str, list[str]]) -> dict[str, str]:
    """Invert to team -> player."""
    return {team: player for player, teams in allocation.items() for team in teams}
