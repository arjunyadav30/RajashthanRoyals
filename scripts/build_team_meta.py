"""Build the small overseas/nationality table used by team profiles.

Reads the T20I team mappings in data_raw and writes one derived record per
player. No match rows, scores or delivery data are copied.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IPL_TEAMS = {
    "Chennai Super Kings",
    "Delhi Capitals",
    "Gujarat Titans",
    "Kolkata Knight Riders",
    "Lucknow Super Giants",
    "Mumbai Indians",
    "Punjab Kings",
    "Rajasthan Royals",
    "Royal Challengers Bengaluru",
    "Sunrisers Hyderabad",
}


def _season_key(value: str) -> int:
    first = str(value or "").split("/")[0]
    digits = "".join(ch for ch in first if ch.isdigit())
    return int(digits) if digits else 0


def build(raw_dir: Path, derived_dir: Path) -> dict:
    competitions = pd.read_csv(raw_dir / "competitions.csv")
    mapping = pd.read_csv(raw_dir / "competition_team_player_mapping.csv")
    teams = pd.read_csv(raw_dir / "teams.csv")

    t20i = competitions[competitions["match_format"] == "T20I"][
        ["comp_id", "season"]
    ]
    frame = mapping.merge(t20i, on="comp_id", how="inner")
    frame = frame.dropna(subset=["team_name"])
    frame["season_key"] = frame["season"].map(_season_key)
    frame = frame.sort_values(["player_id", "season_key", "comp_id"])

    players: dict[str, dict] = {}
    for pid, group in frame.groupby("player_id"):
        latest = group.iloc[-1]
        country = str(latest["team_name"])
        base = country.removesuffix(" A").strip()
        players[str(int(pid))] = {
            "country": base,
            "overseas": base not in ("India",),
            "source": "t20i",
        }

    index_path = derived_dir / "player_index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        national = set(teams["team_name"].dropna()) - IPL_TEAMS
        national = {name for name in national if not name.endswith(" A")}
        for entry in index:
            pid = str(entry.get("player_id") or "")
            if not pid or pid in players:
                continue
            latest_team = str(entry.get("latest_team") or "")
            if latest_team in national:
                players[pid] = {
                    "country": latest_team,
                    "overseas": latest_team != "India",
                    "source": "latest_team",
                }
            else:
                players[pid] = {
                    "country": None,
                    "overseas": False,
                    "source": "ipl_only",
                }

    out_dir = derived_dir / "teams"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "players": players,
        "counts": {
            "players": len(players),
            "overseas": sum(1 for p in players.values() if p["overseas"]),
            "t20i_mapped": sum(1 for p in players.values() if p["source"] == "t20i"),
        },
    }
    (out_dir / "player_meta.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default=str(ROOT / "data_raw"))
    parser.add_argument("--derived-dir", default=str(ROOT / "data_derived"))
    args = parser.parse_args()
    payload = build(Path(args.raw_dir), Path(args.derived_dir))
    print(
        f"Wrote data_derived/teams/player_meta.json: "
        f"{payload['counts']['players']} players, "
        f"{payload['counts']['overseas']} overseas, "
        f"{payload['counts']['t20i_mapped']} mapped from T20I teams."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
