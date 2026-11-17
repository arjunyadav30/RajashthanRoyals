"""Build aggregate batter-vs-bowler and bowler-vs-batter matchup tables.

Reads the same cleaned delivery cache as the scoring engine and writes one small
aggregate JSON per player. No delivery-level rows, match IDs or raw-file contents
are written. Run from the project root:

    python scripts/build_matchups.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.config import DATA_END, DATA_START, DEFAULT_DERIVED_DIR, DEFAULT_RAW_DIR
from engine.data import build_dataset

MIN_BALLS = 6


def _num(value, digits=1):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return round(float(value), digits)


def _int(value):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 0
    return int(value)


def _records(grouped: pd.DataFrame, side: str, min_balls: int) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for row in grouped.itertuples(index=False):
        balls = int(row.balls)
        if balls < min_balls:
            continue
        pid = str(row.player_id)
        if side == "batting":
            record = {
                "opponent_id": str(row.opponent_id),
                "opponent": row.opponent,
                "balls": balls,
                "runs": _int(row.runs),
                "dismissals": _int(row.dismissals),
                "strike_rate": _num(row.runs / balls * 100 if balls else None),
                "dots": _int(row.dots),
                "dot_pct": _num(row.dots / row.legal * 100 if row.legal else None),
                "boundaries": _int(row.boundaries),
                "boundary_pct": _num(row.boundaries / balls * 100 if balls else None),
                "pressure_balls": _int(row.pressure_balls),
                "pressure_runs": _int(row.pressure_runs),
                "pressure_dismissals": _int(row.pressure_dismissals),
                "ipl_balls": _int(row.ipl_balls),
                "t20i_balls": _int(row.t20i_balls),
            }
        else:
            record = {
                "opponent_id": str(row.opponent_id),
                "opponent": row.opponent,
                "balls": balls,
                "runs": _int(row.runs),
                "wickets": _int(row.wickets),
                "economy": _num(row.runs / balls * 6 if balls else None, 2),
                "dots": _int(row.dots),
                "dot_pct": _num(row.dots / balls * 100 if balls else None),
                "boundaries": _int(row.boundaries),
                "boundary_pct": _num(row.boundaries / balls * 100 if balls else None),
                "pressure_balls": _int(row.pressure_balls),
                "pressure_runs": _int(row.pressure_runs),
                "pressure_wickets": _int(row.pressure_wickets),
                "ipl_balls": _int(row.ipl_balls),
                "t20i_balls": _int(row.t20i_balls),
            }
        out.setdefault(pid, []).append(record)
    for rows in out.values():
        rows.sort(key=lambda r: (-r["balls"], r["opponent"]))
    return out


def build_matchup_tables(df: pd.DataFrame, min_balls: int = MIN_BALLS):
    bat = df[df["ball_faced"].fillna(False)].copy()
    bat_pressure = bat["pressure"].fillna(False).astype(bool)
    bat["pressure_flag"] = bat_pressure.astype(int)
    bat["dot"] = bat["legal_ball"].fillna(False) & bat["bat_runs"].fillna(0).eq(0)
    bat["boundary"] = bat["is_four"].fillna(False).astype(bool) | bat["is_six"].fillna(False).astype(bool)
    bat["pressure_runs"] = np.where(bat_pressure, bat["bat_runs"].fillna(0), 0.0)
    bat["pressure_dismissals"] = np.where(
        bat_pressure, bat["striker_dismissed"].fillna(False), False
    )
    bat["ipl_balls"] = bat["league"].eq("IPL").astype(int)
    bat["t20i_balls"] = bat["league"].eq("T20I").astype(int)
    batting = (
        bat.groupby(["striker_id", "bowler_id"], as_index=False)
        .agg(
            player_id=("striker_id", "first"),
            opponent_id=("bowler_id", "first"),
            opponent=("bowler_name", "first"),
            balls=("ball_faced", "size"),
            legal=("legal_ball", "sum"),
            runs=("bat_runs", "sum"),
            dismissals=("striker_dismissed", "sum"),
            dots=("dot", "sum"),
            boundaries=("boundary", "sum"),
            pressure_balls=("pressure_flag", "sum"),
            pressure_runs=("pressure_runs", "sum"),
            pressure_dismissals=("pressure_dismissals", "sum"),
            ipl_balls=("ipl_balls", "sum"),
            t20i_balls=("t20i_balls", "sum"),
        )
        .drop(columns=["striker_id", "bowler_id"])
    )
    batting["opponent"] = batting["opponent"].fillna("Unknown")

    bowl = df[df["legal_ball"].fillna(False)].copy()
    bowl_pressure = bowl["pressure"].fillna(False).astype(bool)
    bowl["pressure_flag"] = bowl_pressure.astype(int)
    bowl["dot"] = bowl["bowler_runs"].fillna(0).eq(0)
    bowl["boundary"] = bowl["is_four"].fillna(False).astype(bool) | bowl["is_six"].fillna(False).astype(bool)
    bowl["pressure_runs"] = np.where(bowl_pressure, bowl["bowler_runs"].fillna(0), 0.0)
    bowl["pressure_wickets"] = np.where(
        bowl_pressure, bowl["bowler_wicket"].fillna(False), False
    )
    bowl["ipl_balls"] = bowl["league"].eq("IPL").astype(int)
    bowl["t20i_balls"] = bowl["league"].eq("T20I").astype(int)
    bowling = (
        bowl.groupby(["bowler_id", "striker_id"], as_index=False)
        .agg(
            player_id=("bowler_id", "first"),
            opponent_id=("striker_id", "first"),
            opponent=("striker_name", "first"),
            balls=("legal_ball", "size"),
            runs=("bowler_runs", "sum"),
            wickets=("bowler_wicket", "sum"),
            dots=("dot", "sum"),
            boundaries=("boundary", "sum"),
            pressure_balls=("pressure_flag", "sum"),
            pressure_runs=("pressure_runs", "sum"),
            pressure_wickets=("pressure_wickets", "sum"),
            ipl_balls=("ipl_balls", "sum"),
            t20i_balls=("t20i_balls", "sum"),
        )
        .drop(columns=["bowler_id", "striker_id"])
    )
    bowling["opponent"] = bowling["opponent"].fillna("Unknown")

    bat_rows = _records(batting, "batting", min_balls)
    bowl_rows = _records(bowling, "bowling", min_balls)
    return bat_rows, bowl_rows, len(batting), len(bowling)


def _names(df: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for id_col, name_col in (("striker_id", "striker_name"), ("bowler_id", "bowler_name")):
        part = df[[id_col, name_col]].dropna()
        for pid, name in part.itertuples(index=False):
            mapping.setdefault(str(pid), str(name))
    return mapping


def write_matchups(df: pd.DataFrame, out_dir: Path, min_balls: int = MIN_BALLS) -> dict:
    bat_rows, bowl_rows, bat_pairs, bowl_pairs = build_matchup_tables(df, min_balls)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = _names(df)
    players = sorted(set(df["striker_id"].dropna().astype(str)) | set(df["bowler_id"].dropna().astype(str)))
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    for pid in players:
        payload = {
            "player_id": pid,
            "name": names.get(pid, pid),
            "generated_at": generated_at,
            "data_window": {"start": DATA_START, "end": DATA_END},
            "min_balls": min_balls,
            "batting": bat_rows.get(pid, []),
            "bowling": bowl_rows.get(pid, []),
        }
        (out_dir / f"{pid}.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    index = {
        "generated_at": generated_at,
        "data_window": {"start": DATA_START, "end": DATA_END},
        "min_balls": min_balls,
        "players": len(players),
        "batting_pairs": int(sum(len(v) for v in bat_rows.values())),
        "bowling_pairs": int(sum(len(v) for v in bowl_rows.values())),
        "source_deliveries": int(len(df)),
        "source_pairs": {"batting": int(bat_pairs), "bowling": int(bowl_pairs)},
    }
    (out_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build aggregate head-to-head matchup tables.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--derived-dir", type=Path, default=DEFAULT_DERIVED_DIR)
    parser.add_argument("--min-balls", type=int, default=MIN_BALLS)
    parser.add_argument("--refresh", action="store_true", help="rebuild the engine delivery cache")
    args = parser.parse_args(argv)

    df, _matches, _players, info = build_dataset(
        args.raw_dir, DATA_START, DATA_END, refresh=args.refresh
    )
    index = write_matchups(df, args.derived_dir / "matchups", args.min_balls)
    print(json.dumps(index, indent=2))
    print(f"Wrote {args.derived_dir / 'matchups'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
