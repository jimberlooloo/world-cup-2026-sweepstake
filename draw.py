#!/usr/bin/env python3
"""Run the real sweepstake draw and print a ready-to-paste Streamlit Secrets block.

The repo never stores real names. You run this locally once with your 16 family names;
it draws 3 teams each (pure luck, reproducible from the seed) and prints a [sweepstake]
block. Paste that into the Streamlit Cloud app's Secrets panel (or a local
.streamlit/secrets.toml, which is gitignored).

Usage:
  python draw.py "Alice, Bob, Carol, ... (16 names)"
  python draw.py --names-file names.txt          # one name per line
  python draw.py "...names..." --seed 20260611    # pin the seed for a re-runnable draw
  python draw.py "...names..." --explicit         # emit the fixed mapping instead of names+seed

Teams are fetched live from the same openfootball feed the app uses, so the draw is over
the real 48 World Cup 2026 teams.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "app"))
import allocation as alloc  # noqa: E402
import data as feed  # noqa: E402


def _toml_list(items: list[str]) -> str:
    return "[" + ", ".join(f'"{i}"' for i in items) + "]"


def main() -> None:
    ap = argparse.ArgumentParser(description="Draw the World Cup 2026 sweepstake.")
    ap.add_argument("names", nargs="?", help="comma-separated player names")
    ap.add_argument("--names-file", help="file with one name per line")
    ap.add_argument("--seed", type=int, default=alloc.DEFAULT_SEED)
    ap.add_argument("--explicit", action="store_true", help="emit the fixed mapping (shape B)")
    args = ap.parse_args()

    if args.names_file:
        with open(args.names_file) as f:
            players = [ln.strip() for ln in f if ln.strip()]
    elif args.names:
        players = [n.strip() for n in args.names.split(",") if n.strip()]
    else:
        ap.error("provide names as an argument or via --names-file")

    team_names = [t["name"] for t in feed.fetch_teams()]
    result = alloc.draw(players, team_names, args.seed)

    print(f"# {len(players)} players · {len(team_names)} teams · seed {args.seed}")
    print("# Paste the block below into Streamlit Secrets (or .streamlit/secrets.toml).\n")
    if args.explicit:
        print("[sweepstake.allocation]")
        for player, teams in result.items():
            print(f'"{player}" = {_toml_list(teams)}')
    else:
        print("[sweepstake]")
        print(f"seed = {args.seed}")
        print(f"players = {_toml_list(players)}")
        print("\n# Resulting draw (for your reference):")
        for player, teams in result.items():
            print(f"#   {player}: {', '.join(teams)}")


if __name__ == "__main__":
    main()
