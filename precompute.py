"""Offline precompute for the RR pressure dashboard.

Reads the confidential data pack in ``data_raw/`` and writes only small
derived aggregates to ``data_derived/``. It never emits delivery-level rows
and never recomputes the headline composite score, rank or win-probability
model.

Current derived outputs (Add-on 3):
  data_derived/recent/{player_id}.json  -- profile, 25-match log, form windows,
                                           phase and IPL/T20I splits
  data_derived/player_index.json        -- search/autocomplete index
  data_derived/meta.json                -- build metadata

Run locally:
    python precompute.py

Shared rules implemented here (and reused by the rest of the project):
  * Super overs (innings 3 and 4) are excluded.
  * The two Emerging tournaments are excluded.
  * DLS / shortened matches (non-null ``revised_target``) are excluded.
  * A legal ball is any delivery whose extras_type is not wide or Overstep.
  * A batter's balls faced exclude wides but include no-balls.
  * Bat runs are the ``runs`` column (the pack stores bat runs there).
  * A bowler is charged bat runs plus extras1 on wide/Overstep/other; not
    byes, leg-byes or penalties.
  * Bowlers are not credited with run-outs, retired-outs or obstruction.
  * Rule-based descriptive pressure:
      A) 2nd innings, overs 16-20, 0.8-2.0 runs needed per remaining ball.
      B) 2nd innings, required rate > 10 with fewer than 5 wickets in hand.
      C) 3+ wickets down inside the first six overs (either innings).
    This is deliberately different from the leverage-based headline model.
"""

from __future__ import annotations

import argparse
import json
import math
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from stats_engine import build_stats

PROJECT_ROOT = Path(__file__).resolve().parent

EMERGING_COMPS = {
    "Mens T20 Emerging Teams Asia Cup 2024",
    "Asia Cup Rising Stars 2025",
}

# Bowler-credited dismissals. Run-outs, retired-outs and obstruction are not
# credited, per the competition rules used across this project.
BOWLER_CREDIT_DISMISSALS = {
    "caught",
    "bowled",
    "lbw",
    "stump",
    "stumped",
    "hit wicket",
}

SMALL_SAMPLE_BALLS = 30
DEFAULT_DATA_END = "2026-11-01"

REQUIRED_BB = [
    "match_id",
    "innings",
    "overid",
    "over_ball_num",
    "innings_ball_num",
    "batting_team_id",
    "bowling_team_id",
    "striker_id",
    "striker_name",
    "bowler_id",
    "bowler_name",
    "runs",
    "is_four",
    "is_six",
    "is_wicket",
    "dismissal_type",
    "dismissed_player_id",
    "extras_type",
    "extras1_runs",
    "extras_2_runs",
]

REQUIRED_MATCHES = [
    "match_id",
    "comp_id",
    "match_date",
    "venue_country",
    "revised_target",
    "home_team_id",
    "away_team_id",
    "home_team",
    "away_team",
]

REQUIRED_COMPS = ["comp_id", "comp_name", "match_format", "season"]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _read_csv(path: Path, required: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    df = pd.read_csv(path)
    if required:
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"{path.name} is missing required columns: {missing}")
    return df


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _canon_id(value) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if pd.isna(value):
        return None
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        text = str(value).strip()
        return text or None


def _rate(num, den, scale: float = 100.0, digits: int = 1):
    if den is None or den <= 0:
        return None
    try:
        value = float(num) * scale / float(den)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if not math.isfinite(value):
        return None
    return round(value, digits)


def _r1(value):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return round(value, 1)


def _date_str(value):
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _normalise_name(name: str) -> str:
    """Accent-insensitive, case-insensitive search key."""
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Raw loading and rule preparation
# ---------------------------------------------------------------------------


def load_raw(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    comps = _read_csv(raw_dir / "competitions.csv", REQUIRED_COMPS)
    matches = _read_csv(raw_dir / "matches.csv", REQUIRED_MATCHES)
    teams = _read_csv(raw_dir / "teams.csv", ["comp_id", "team_id", "team_name"])
    xi = _read_csv(raw_dir / "playing_eleven.csv", ["match_id", "team_id", "player_id"])
    bb = _read_csv(raw_dir / "ball_by_ball.csv", REQUIRED_BB)

    comps = comps.copy()
    comps["comp_id"] = _num(comps["comp_id"])
    comps["comp_name"] = comps["comp_name"].astype(str).str.strip()
    comps["match_format"] = comps["match_format"].astype(str).str.strip()

    matches = matches.copy()
    matches["match_id"] = _num(matches["match_id"])
    matches["comp_id"] = _num(matches["comp_id"])
    matches["match_date"] = pd.to_datetime(matches["match_date"], errors="coerce")
    matches["revised_target"] = _num(matches["revised_target"])

    teams = teams.copy()
    teams["comp_id"] = _num(teams["comp_id"])
    teams["team_id"] = _num(teams["team_id"])
    teams["team_name"] = teams["team_name"].astype(str).str.strip()

    bb = bb.copy()
    for col in ("match_id", "innings", "overid", "over_ball_num", "innings_ball_num"):
        bb[col] = _num(bb[col])
    for col in ("batting_team_id", "bowling_team_id", "striker_id", "bowler_id", "dismissed_player_id"):
        bb[col] = _num(bb[col])
    for col in ("runs", "extras1_runs", "extras_2_runs"):
        bb[col] = _num(bb[col]).fillna(0)
    for col in ("is_four", "is_six", "is_wicket"):
        bb[col] = bb[col].fillna(False).astype(bool)

    return comps, matches, teams, xi, bb


def prepare_deliveries(raw_dir: Path, data_end: str | pd.Timestamp = DEFAULT_DATA_END):
    """Load, filter and annotate deliveries with the project's shared rules."""
    comps, matches, teams, _xi, bb = load_raw(raw_dir)

    match_meta = matches.merge(comps, on="comp_id", how="left")
    match_meta = match_meta[
        (~match_meta["comp_name"].isin(EMERGING_COMPS))
        & (match_meta["revised_target"].isna())
    ].copy()

    df = bb.merge(
        match_meta[
            [
                "match_id",
                "comp_id",
                "comp_name",
                "match_format",
                "season",
                "match_date",
                "venue_country",
                "revised_target",
            ]
        ],
        on="match_id",
        how="inner",
    )
    df = df[df["innings"].isin([1, 2])].copy()
    df = df[df["match_date"].notna()].copy()

    # Team names are scoped by competition in the supplied pack.
    team_map = (
        teams.drop_duplicates(["comp_id", "team_id"])
        .assign(_key=lambda d: d["comp_id"].astype(str) + ":" + d["team_id"].astype(str))
        .set_index("_key")["team_name"]
    )

    def lookup(comp_ids, team_ids):
        keys = comp_ids.astype(str) + ":" + team_ids.astype(str)
        return keys.map(team_map)

    df["batting_team"] = lookup(df["comp_id"], df["batting_team_id"])
    df["bowling_team"] = lookup(df["comp_id"], df["bowling_team_id"])

    # Format label used by the UI: IPL or T20I (Emerging T20s are excluded).
    is_ipl = df["comp_name"].str.upper().str.startswith("IPL")
    df["format"] = np.where(is_ipl, "IPL", np.where(df["match_format"].eq("T20I"), "T20I", "T20"))

    extras = df["extras_type"].fillna("").astype(str).str.strip().str.lower()
    df["extras_key"] = extras
    df["is_wide"] = extras.eq("wide")
    df["is_overstep"] = extras.eq("overstep")
    df["legal_ball"] = ~extras.isin(["wide", "overstep"])
    df["ball_faced"] = ~df["is_wide"]

    # The pack stores bat runs in `runs`; extras are separate columns.
    df["bat_runs"] = df["runs"]
    chargeable = extras.isin(["wide", "overstep", "other"])
    df["bowler_runs"] = df["runs"] + np.where(chargeable, df["extras1_runs"], 0.0)
    df["team_runs"] = df["runs"] + df["extras1_runs"] + df["extras_2_runs"]

    dismissal_key = df["dismissal_type"].fillna("").astype(str).str.strip().str.lower()
    df["bowler_wicket"] = df["is_wicket"] & dismissal_key.isin(BOWLER_CREDIT_DISMISSALS)
    df["striker_dismissed"] = df["is_wicket"] & (
        df["dismissed_player_id"].fillna(-1) == df["striker_id"].fillna(-2)
    )
    df["batter_dismissal"] = np.where(df["striker_dismissed"], df["dismissal_type"], None)

    df["phase"] = np.select(
        [df["overid"] <= 6, df["overid"] <= 15],
        ["powerplay", "middle"],
        default="death",
    )

    df = df.sort_values(
        ["match_id", "innings", "innings_ball_num", "over_ball_num"], kind="stable"
    ).reset_index(drop=True)

    # First-innings total (runs + all extras) is the chase target base. Matches
    # with a revised target were removed above.
    first_innings = (
        df[df["innings"] == 1]
        .groupby("match_id", as_index=True)["team_runs"]
        .sum()
        .rename("first_innings_total")
    )
    df = df.merge(first_innings, left_on="match_id", right_index=True, how="left")

    grouped = df.groupby(["match_id", "innings"], sort=False)
    df["runs_before"] = grouped["team_runs"].cumsum() - df["team_runs"]
    df["wickets_before"] = grouped["is_wicket"].cumsum() - df["is_wicket"].astype(int)
    df["legal_before"] = grouped["legal_ball"].cumsum() - df["legal_ball"].astype(int)

    df["target"] = df["first_innings_total"] + 1.0
    df["legal_remaining"] = (120.0 - df["legal_before"]).clip(lower=1.0)
    df["runs_needed"] = (df["target"] - df["runs_before"]).clip(lower=0.0)
    df["runs_per_ball_needed"] = df["runs_needed"] / df["legal_remaining"]
    df["required_rate"] = df["runs_needed"] / (df["legal_remaining"] / 6.0)
    df["wickets_in_hand"] = 10 - df["wickets_before"]

    chase_close = (
        df["innings"].eq(2)
        & df["overid"].ge(16)
        & df["runs_per_ball_needed"].ge(0.8)
        & df["runs_per_ball_needed"].le(2.0)
    )
    chase_steep = (
        df["innings"].eq(2)
        & df["required_rate"].gt(10.0)
        & df["wickets_in_hand"].lt(5)
    )
    early_collapse = df["overid"].le(6) & (
        df["wickets_before"].ge(3)
        | (df["is_wicket"] & df["wickets_before"].eq(2))
    )
    df["pressure"] = chase_close | chase_steep | early_collapse

    return df


def load_appearances(raw_dir: Path) -> pd.DataFrame:
    """Eligible XI appearances, used so ``matches`` counts games played.

    A player can appear in a match without batting or bowling; the per-match
    log still gets a row for that game with null batting/bowling sections.
    """
    comps = _read_csv(raw_dir / "competitions.csv", REQUIRED_COMPS)
    matches = _read_csv(raw_dir / "matches.csv", REQUIRED_MATCHES)
    teams = _read_csv(raw_dir / "teams.csv", ["comp_id", "team_id", "team_name"])
    xi = _read_csv(
        raw_dir / "playing_eleven.csv",
        [
            "match_id",
            "team_id",
            "player_id",
            "batting_order",
            "is_played",
            "is_captain",
            "is_wk",
            "is_impact",
            "is_impact_off",
        ],
    )

    comps["comp_id"] = _num(comps["comp_id"])
    comps["comp_name"] = comps["comp_name"].astype(str).str.strip()
    matches["match_id"] = _num(matches["match_id"])
    matches["comp_id"] = _num(matches["comp_id"])
    matches["match_date"] = pd.to_datetime(matches["match_date"], errors="coerce")
    matches["revised_target"] = _num(matches["revised_target"])
    for col in ("home_team_id", "away_team_id", "win_team_id", "man_of_the_match"):
        if col in matches.columns:
            matches[col] = _num(matches[col])
    teams["comp_id"] = _num(teams["comp_id"])
    teams["team_id"] = _num(teams["team_id"])
    teams["team_name"] = teams["team_name"].astype(str).str.strip()

    xi["match_id"] = _num(xi["match_id"])
    xi["team_id"] = _num(xi["team_id"])
    xi["batting_order"] = _num(xi["batting_order"])
    xi["is_played"] = (
        xi["is_played"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "y", "yes"])
    )
    for col in ("is_captain", "is_wk", "is_impact", "is_impact_off"):
        if col in xi.columns:
            xi[col] = (
                xi[col]
                .astype(str)
                .str.strip()
                .str.lower()
                .isin(["true", "1", "y", "yes"])
            )
        else:
            xi[col] = False
    xi = xi[xi["is_played"]].copy()

    meta = matches.merge(comps, on="comp_id", how="left")
    meta = meta[
        (~meta["comp_name"].isin(EMERGING_COMPS)) & (meta["revised_target"].isna())
    ].copy()
    meta["format"] = np.where(
        meta["comp_name"].str.upper().str.startswith("IPL"),
        "IPL",
        np.where(meta["match_format"].eq("T20I"), "T20I", "T20"),
    )
    for col in ("win_team_id", "man_of_the_match"):
        if col not in meta.columns:
            meta[col] = np.nan

    team_map = (
        teams.drop_duplicates(["comp_id", "team_id"])
        .assign(_key=lambda d: d["comp_id"].astype(str) + ":" + d["team_id"].astype(str))
        .set_index("_key")["team_name"]
    )
    xi = xi.merge(
        meta[
            [
                "match_id",
                "comp_id",
                "comp_name",
                "format",
                "season",
                "match_date",
                "venue_country",
                "home_team_id",
                "away_team_id",
                "home_team",
                "away_team",
                "win_team_id",
                "man_of_the_match",
            ]
        ],
        on="match_id",
        how="inner",
    )
    xi["player_id"] = xi["player_id"].map(_canon_id)
    xi = xi[xi["player_id"].notna()].copy()
    keys = xi["comp_id"].astype(str) + ":" + xi["team_id"].astype(str)
    fallback_team = pd.Series(
        np.where(xi["team_id"].eq(xi["home_team_id"]), xi["home_team"], xi["away_team"]),
        index=xi.index,
    )
    xi["player_team"] = keys.map(team_map).combine_first(fallback_team)
    xi["opponent"] = np.where(
        xi["team_id"].eq(xi["home_team_id"]), xi["away_team"], xi["home_team"]
    )
    xi = xi.drop_duplicates(["player_id", "match_id"])
    return xi[
        [
            "player_id",
            "match_id",
            "team_id",
            "player_team",
            "opponent",
            "match_date",
            "comp_name",
            "format",
            "season",
            "venue_country",
            "batting_order",
            "is_captain",
            "is_wk",
            "is_impact",
            "is_impact_off",
            "win_team_id",
            "man_of_the_match",
        ]
    ].copy()


def _merge_appearances(match_agg: pd.DataFrame, appearances: pd.DataFrame) -> pd.DataFrame:
    """Add zero-stat rows for XI appearances without a bat/bowl involvement."""
    if appearances.empty:
        return match_agg
    extra = appearances.merge(
        match_agg[["player_id", "match_id"]], on=["player_id", "match_id"], how="left", indicator=True
    )
    extra = extra[extra["_merge"] == "left_only"].drop(columns=["_merge"]).copy()
    if extra.empty:
        return match_agg

    for col in BAT_SUM_COLS + BOWL_SUM_COLS:
        extra[col] = 0
    extra["innings"] = None
    extra["dismissal_type"] = None
    extra["batting_innings"] = None
    extra["bowling_innings"] = None
    extra["opponent_bat"] = None
    extra["opponent_bowl"] = None
    extra["team_bat"] = None
    extra["team_bowl"] = None
    extra["match_date"] = pd.to_datetime(extra["match_date"], errors="coerce")
    extra = extra.reindex(columns=match_agg.columns)
    return pd.concat([match_agg, extra], ignore_index=True)


# ---------------------------------------------------------------------------
# Batting / bowling fact tables and stat builders
# ---------------------------------------------------------------------------


BAT_SUM_COLS = [
    "b_balls",
    "b_runs",
    "b_fours",
    "b_sixes",
    "b_dots",
    "b_dismissals",
    "b_p_balls",
    "b_p_runs",
    "b_p_fours",
    "b_p_sixes",
    "b_p_dots",
    "b_p_dismissals",
]

BOWL_SUM_COLS = [
    "w_balls",
    "w_runs",
    "w_wickets",
    "w_dots",
    "w_p_balls",
    "w_p_runs",
    "w_p_wickets",
    "w_p_dots",
]


def build_fact_tables(df: pd.DataFrame):
    bat = df[df["striker_id"].notna()].copy()
    bat["player_id"] = bat["striker_id"].map(_canon_id)
    bat = bat[bat["player_id"].notna()]
    bat["b_ball"] = bat["ball_faced"].astype(int)
    bat["b_runs"] = bat["bat_runs"].fillna(0)
    bat["b_four"] = (bat["ball_faced"] & bat["is_four"]).astype(int)
    bat["b_six"] = (bat["ball_faced"] & bat["is_six"]).astype(int)
    bat["b_dot"] = (bat["ball_faced"] & bat["bat_runs"].fillna(0).eq(0)).astype(int)
    bat["b_dismissal"] = bat["striker_dismissed"].astype(int)
    p = bat["pressure"]
    bat["b_p_ball"] = (p & bat["ball_faced"]).astype(int)
    bat["b_p_run"] = np.where(p, bat["bat_runs"].fillna(0), 0.0)
    bat["b_p_four"] = (p & bat["ball_faced"] & bat["is_four"]).astype(int)
    bat["b_p_six"] = (p & bat["ball_faced"] & bat["is_six"]).astype(int)
    bat["b_p_dot"] = (p & bat["ball_faced"] & bat["bat_runs"].fillna(0).eq(0)).astype(int)
    bat["b_p_dismissal"] = (p & bat["striker_dismissed"]).astype(int)

    bowl = df[df["bowler_id"].notna()].copy()
    bowl["player_id"] = bowl["bowler_id"].map(_canon_id)
    bowl = bowl[bowl["player_id"].notna()]
    bowl["w_legal"] = bowl["legal_ball"].astype(int)
    bowl["w_run"] = bowl["bowler_runs"].fillna(0)
    bowl["w_wicket"] = bowl["bowler_wicket"].astype(int)
    bowl["w_dot"] = (bowl["legal_ball"] & bowl["bowler_runs"].fillna(0).eq(0)).astype(int)
    p = bowl["pressure"]
    bowl["w_p_legal"] = (p & bowl["legal_ball"]).astype(int)
    bowl["w_p_run"] = np.where(p, bowl["bowler_runs"].fillna(0), 0.0)
    bowl["w_p_wicket"] = (p & bowl["bowler_wicket"]).astype(int)
    bowl["w_p_dot"] = (p & bowl["legal_ball"] & bowl["bowler_runs"].fillna(0).eq(0)).astype(int)

    return bat, bowl


def _bat_stats(sums: dict) -> dict | None:
    s = {c: int(sums.get(c, 0) or 0) for c in BAT_SUM_COLS}
    if s["b_balls"] == 0 and s["b_dismissals"] == 0:
        return None
    runs = s["b_runs"]
    balls = s["b_balls"]
    boundaries = s["b_fours"] + s["b_sixes"]
    pressure = {
        "balls": s["b_p_balls"],
        "runs": s["b_p_runs"],
        "strike_rate": _rate(s["b_p_runs"], s["b_p_balls"]),
        "boundary_pct": _rate(s["b_p_fours"] + s["b_p_sixes"], s["b_p_balls"]),
        "dot_pct": _rate(s["b_p_dots"], s["b_p_balls"]),
        "dismissals": s["b_p_dismissals"],
        "dismissal_pct": _rate(s["b_p_dismissals"], s["b_p_balls"]),
        "small_sample": s["b_p_balls"] < SMALL_SAMPLE_BALLS,
    }
    return {
        "balls": balls,
        "runs": int(runs),
        "strike_rate": _rate(runs, balls),
        "fours": s["b_fours"],
        "sixes": s["b_sixes"],
        "boundary_pct": _rate(boundaries, balls),
        "dots": s["b_dots"],
        "dot_pct": _rate(s["b_dots"], balls),
        "dismissals": s["b_dismissals"],
        "dismissal_pct": _rate(s["b_dismissals"], balls),
        "small_sample": balls < SMALL_SAMPLE_BALLS,
        "pressure": pressure,
    }


def _bowl_stats(sums: dict) -> dict | None:
    s = {c: int(sums.get(c, 0) or 0) for c in BOWL_SUM_COLS}
    if s["w_balls"] == 0 and s["w_wickets"] == 0 and s["w_runs"] == 0:
        return None
    balls = s["w_balls"]
    runs = s["w_runs"]
    pressure = {
        "balls": s["w_p_balls"],
        "runs": s["w_p_runs"],
        "economy": _rate(s["w_p_runs"], s["w_p_balls"], scale=6.0),
        "wickets": s["w_p_wickets"],
        "wicket_pct": _rate(s["w_p_wickets"], s["w_p_balls"]),
        "dot_pct": _rate(s["w_p_dots"], s["w_p_balls"]),
        "small_sample": s["w_p_balls"] < SMALL_SAMPLE_BALLS,
    }
    return {
        "legal_balls": balls,
        "runs": int(runs),
        "economy": _rate(runs, balls, scale=6.0),
        "wickets": s["w_wickets"],
        "wicket_pct": _rate(s["w_wickets"], balls),
        "dots": s["w_dots"],
        "dot_pct": _rate(s["w_dots"], balls),
        "small_sample": balls < SMALL_SAMPLE_BALLS,
        "pressure": pressure,
    }


def _sum_columns(frame: pd.DataFrame, cols: list[str]) -> dict:
    if frame.empty:
        return {c: 0 for c in cols}
    return {c: frame[c].sum() for c in cols}


def _window_stats(frame: pd.DataFrame) -> dict:
    return {
        "matches": int(len(frame)),
        "batting": _bat_stats(_sum_columns(frame, BAT_SUM_COLS)),
        "bowling": _bowl_stats(_sum_columns(frame, BOWL_SUM_COLS)),
    }


# ---------------------------------------------------------------------------
# Per-player assembly
# ---------------------------------------------------------------------------


def _build_match_table(bat: pd.DataFrame, bowl: pd.DataFrame) -> pd.DataFrame:
    bat_match = bat.groupby(["player_id", "match_id"], as_index=False).agg(
        **{c: (c, "sum") for c in [
            "b_ball", "b_runs", "b_four", "b_six", "b_dot", "b_dismissal",
            "b_p_ball", "b_p_run", "b_p_four", "b_p_six", "b_p_dot", "b_p_dismissal",
        ]},
        match_date=("match_date", "first"),
        comp_name=("comp_name", "first"),
        format=("format", "first"),
        venue_country=("venue_country", "first"),
        opponent_bat=("bowling_team", "first"),
        team_bat=("batting_team", "first"),
        batting_innings=("innings", "first"),
        dismissal_type=("batter_dismissal", lambda s: next((x for x in reversed(list(s)) if pd.notna(x)), None)),
    ).rename(
        columns={
            "b_ball": "b_balls",
            "b_four": "b_fours",
            "b_six": "b_sixes",
            "b_dot": "b_dots",
            "b_dismissal": "b_dismissals",
            "b_p_ball": "b_p_balls",
            "b_p_run": "b_p_runs",
            "b_p_four": "b_p_fours",
            "b_p_six": "b_p_sixes",
            "b_p_dot": "b_p_dots",
            "b_p_dismissal": "b_p_dismissals",
        }
    )

    bowl_match = bowl.groupby(["player_id", "match_id"], as_index=False).agg(
        **{c: (c, "sum") for c in [
            "w_legal", "w_run", "w_wicket", "w_dot",
            "w_p_legal", "w_p_run", "w_p_wicket", "w_p_dot",
        ]},
        match_date=("match_date", "first"),
        comp_name=("comp_name", "first"),
        format=("format", "first"),
        venue_country=("venue_country", "first"),
        opponent_bowl=("batting_team", "first"),
        team_bowl=("bowling_team", "first"),
        bowling_innings=("innings", "first"),
    ).rename(
        columns={
            "w_legal": "w_balls",
            "w_run": "w_runs",
            "w_wicket": "w_wickets",
            "w_dot": "w_dots",
            "w_p_legal": "w_p_balls",
            "w_p_run": "w_p_runs",
            "w_p_wicket": "w_p_wickets",
            "w_p_dot": "w_p_dots",
        }
    )

    merged = bat_match.merge(
        bowl_match, on=["player_id", "match_id"], how="outer", suffixes=("_bat", "_bowl")
    )
    for col in ["match_date", "comp_name", "format", "venue_country"]:
        merged[col] = merged[f"{col}_bat"].combine_first(merged[f"{col}_bowl"])
    merged["opponent"] = merged["opponent_bat"].combine_first(merged["opponent_bowl"])
    merged["player_team"] = merged["team_bat"].combine_first(merged["team_bowl"])
    merged["innings"] = merged["batting_innings"].combine_first(merged["bowling_innings"])

    for col in BAT_SUM_COLS + BOWL_SUM_COLS:
        if col not in merged.columns:
            merged[col] = 0
        merged[col] = merged[col].fillna(0)

    merged["match_date"] = pd.to_datetime(merged["match_date"], errors="coerce")
    return merged.sort_values(["player_id", "match_date", "match_id"]).reset_index(drop=True)


def _name_fallback(raw_dir: Path) -> dict[str, str]:
    path = raw_dir / "competition_team_player_mapping.csv"
    if not path.exists():
        return {}
    try:
        mapping = pd.read_csv(path)
    except Exception:
        return {}
    if not {"player_id", "player_name"}.issubset(mapping.columns):
        return {}
    mapping = mapping.dropna(subset=["player_id", "player_name"]).copy()
    mapping["player_id"] = mapping["player_id"].map(_canon_id)
    mapping = mapping[mapping["player_id"].notna()]
    mapping["player_name"] = mapping["player_name"].astype(str)
    return mapping.drop_duplicates("player_id").set_index("player_id")["player_name"].to_dict()


def _latest_names(df: pd.DataFrame) -> dict[str, str]:
    rows = pd.concat(
        [
            df[["striker_id", "striker_name", "match_date"]].rename(
                columns={"striker_id": "pid", "striker_name": "name"}
            ),
            df[["bowler_id", "bowler_name", "match_date"]].rename(
                columns={"bowler_id": "pid", "bowler_name": "name"}
            ),
        ],
        ignore_index=True,
    )
    rows = rows.dropna(subset=["pid", "name"]).copy()
    rows["player_id"] = rows["pid"].map(_canon_id)
    rows = rows.dropna(subset=["player_id"]).sort_values(["player_id", "match_date"])
    latest = rows.groupby("player_id", as_index=True).tail(1)
    return latest.set_index("player_id")["name"].astype(str).to_dict()


def _guess_role(balls_faced: int, balls_bowled: int) -> str:
    if balls_faced <= 0 and balls_bowled <= 0:
        return "unknown"
    if balls_faced <= 0:
        return "bowler"
    if balls_bowled <= 0:
        return "batter"
    minor, major = min(balls_faced, balls_bowled), max(balls_faced, balls_bowled)
    if minor >= 50 and minor / major >= 0.25:
        return "both"
    return "batter" if balls_faced >= balls_bowled else "bowler"


def _match_log_row(row: pd.Series) -> dict:
    bat = _bat_stats({c: row.get(c, 0) for c in BAT_SUM_COLS})
    bowl = _bowl_stats({c: row.get(c, 0) for c in BOWL_SUM_COLS})

    batting = None
    if bat is not None:
        batting = {
            "runs": bat["runs"],
            "balls": bat["balls"],
            "strike_rate": bat["strike_rate"],
            "fours": bat["fours"],
            "sixes": bat["sixes"],
            "boundary_pct": bat["boundary_pct"],
            "dots": bat["dots"],
            "dot_pct": bat["dot_pct"],
            "dismissed": bool(int(row.get("b_dismissals", 0) or 0) > 0),
            "dismissal": None if pd.isna(row.get("dismissal_type")) else str(row.get("dismissal_type")),
            "pressure_balls": bat["pressure"]["balls"],
            "pressure_runs": bat["pressure"]["runs"],
            "pressure_strike_rate": bat["pressure"]["strike_rate"],
            "pressure_fours": int(row.get("b_p_fours", 0) or 0),
            "pressure_sixes": int(row.get("b_p_sixes", 0) or 0),
            "pressure_boundary_pct": _rate(
                int(row.get("b_p_fours", 0) or 0) + int(row.get("b_p_sixes", 0) or 0),
                int(row.get("b_p_balls", 0) or 0),
            ),
            "pressure_dots": int(row.get("b_p_dots", 0) or 0),
            "pressure_dot_pct": _rate(
                int(row.get("b_p_dots", 0) or 0), int(row.get("b_p_balls", 0) or 0)
            ),
            "pressure_dismissals": bat["pressure"]["dismissals"],
            "pressure_dismissed": bool(bat["pressure"]["dismissals"] > 0),
        }

    bowling = None
    if bowl is not None:
        bowling = {
            "legal_balls": bowl["legal_balls"],
            "runs": bowl["runs"],
            "wickets": bowl["wickets"],
            "economy": bowl["economy"],
            "wicket_pct": bowl["wicket_pct"],
            "dots": bowl["dots"],
            "dot_pct": bowl["dot_pct"],
            "pressure_balls": bowl["pressure"]["balls"],
            "pressure_runs": bowl["pressure"]["runs"],
            "pressure_wickets": bowl["pressure"]["wickets"],
            "pressure_economy": bowl["pressure"]["economy"],
            "pressure_wicket_pct": bowl["pressure"]["wicket_pct"],
            "pressure_dots": int(row.get("w_p_dots", 0) or 0),
            "pressure_dot_pct": _rate(
                int(row.get("w_p_dots", 0) or 0), int(row.get("w_p_balls", 0) or 0)
            ),
        }

    return {
        "match_id": _canon_id(row.get("match_id")),
        "match_date": _date_str(row.get("match_date")),
        "competition": None if pd.isna(row.get("comp_name")) else str(row.get("comp_name")),
        "format": None if pd.isna(row.get("format")) else str(row.get("format")),
        "opponent": None if pd.isna(row.get("opponent")) else str(row.get("opponent")),
        "venue_country": None if pd.isna(row.get("venue_country")) else str(row.get("venue_country")),
        "innings": None if pd.isna(row.get("innings")) else int(row.get("innings")),
        "batting": batting,
        "bowling": bowling,
    }


def _nested_splits(
    bat: pd.DataFrame,
    bowl: pd.DataFrame,
    keys: list[str],
    key_values: list[str],
) -> dict[str, dict]:
    """Return {player_id: {value: {batting, bowling}}} for consistent keys."""
    out: dict[str, dict] = {}
    if bat.empty and bowl.empty:
        return out

    bat_groups = bat.groupby(["player_id"] + keys, dropna=False) if not bat.empty else []
    bowl_groups = bowl.groupby(["player_id"] + keys, dropna=False) if not bowl.empty else []

    bat_stats_by_key: dict[tuple, dict] = {}
    for key, frame in bat_groups:
        sums = {
            "b_balls": frame["b_ball"].sum(),
            "b_runs": frame["b_runs"].sum(),
            "b_fours": frame["b_four"].sum(),
            "b_sixes": frame["b_six"].sum(),
            "b_dots": frame["b_dot"].sum(),
            "b_dismissals": frame["b_dismissal"].sum(),
            "b_p_balls": frame["b_p_ball"].sum(),
            "b_p_runs": frame["b_p_run"].sum(),
            "b_p_fours": frame["b_p_four"].sum(),
            "b_p_sixes": frame["b_p_six"].sum(),
            "b_p_dots": frame["b_p_dot"].sum(),
            "b_p_dismissals": frame["b_p_dismissal"].sum(),
        }
        bat_stats_by_key[key if isinstance(key, tuple) else (key,)] = _bat_stats(sums)

    bowl_stats_by_key: dict[tuple, dict] = {}
    for key, frame in bowl_groups:
        sums = {
            "w_balls": frame["w_legal"].sum(),
            "w_runs": frame["w_run"].sum(),
            "w_wickets": frame["w_wicket"].sum(),
            "w_dots": frame["w_dot"].sum(),
            "w_p_balls": frame["w_p_legal"].sum(),
            "w_p_runs": frame["w_p_run"].sum(),
            "w_p_wickets": frame["w_p_wicket"].sum(),
            "w_p_dots": frame["w_p_dot"].sum(),
        }
        bowl_stats_by_key[key if isinstance(key, tuple) else (key,)] = _bowl_stats(sums)

    all_pids = set(k[0] if isinstance(k, tuple) else k for k in bat_stats_by_key) | set(
        k[0] if isinstance(k, tuple) else k for k in bowl_stats_by_key
    )
    for pid in all_pids:
        pid = str(pid)
        out.setdefault(pid, {})
        for value in key_values:
            base_key = (pid,) + tuple([value] * len(keys))
            out[pid][value] = {
                "batting": bat_stats_by_key.get(base_key),
                "bowling": bowl_stats_by_key.get(base_key),
            }
    return out


def _phase_split(bat: pd.DataFrame, bowl: pd.DataFrame) -> dict[str, dict]:
    return _nested_splits(bat, bowl, ["phase"], ["powerplay", "middle", "death"])


def _format_split(bat: pd.DataFrame, bowl: pd.DataFrame) -> dict[str, dict]:
    return _nested_splits(bat, bowl, ["format"], ["IPL", "T20I"])


def _filter_pairs(frame: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or pairs.empty:
        return frame.iloc[0:0]
    return frame.merge(pairs[["player_id", "match_id"]], on=["player_id", "match_id"], how="inner")


def _load_ranking_overlay(rankings_dir: Path) -> dict[str, dict]:
    """Small player_id -> ranked role/rank overlay for player_index."""
    overlay: dict[str, dict] = {}
    files = [
        (rankings_dir / "All_Batter_Rankings.csv", "batter"),
        (rankings_dir / "All_Bowler_Rankings.csv", "bowler"),
    ]
    for path, fallback_role in files:
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if "player_id" not in df.columns or "rank" not in df.columns:
            continue
        for _, row in df.iterrows():
            pid = _canon_id(row.get("player_id"))
            rank = pd.to_numeric(pd.Series([row.get("rank")]), errors="coerce").iloc[0]
            if pid is None or pd.isna(rank):
                continue
            role = str(row.get("player_type", fallback_role)).strip().lower()
            if role not in ("batter", "bowler"):
                role = fallback_role
            existing = overlay.get(pid)
            if existing is None or int(rank) < int(existing["ranked_rank"]):
                overlay[pid] = {"ranked_role": role, "ranked_rank": int(rank)}
    return overlay


def run_precompute(
    raw_dir: str | Path | None = None,
    derived_dir: str | Path | None = None,
    rankings_dir: str | Path | None = None,
    data_end: str = DEFAULT_DATA_END,
    verbose: bool = True,
) -> dict:
    raw_dir = Path(raw_dir) if raw_dir else PROJECT_ROOT / "data_raw"
    derived_dir = Path(derived_dir) if derived_dir else PROJECT_ROOT / "data_derived"
    rankings_dir = Path(rankings_dir) if rankings_dir else PROJECT_ROOT / "data_rankings"

    data_end_ts = pd.Timestamp(data_end)
    twelve_month_cutoff = data_end_ts - pd.DateOffset(months=12)

    df = prepare_deliveries(raw_dir, data_end=data_end)
    bat, bowl = build_fact_tables(df)
    match_agg = _build_match_table(bat, bowl)
    appearances = load_appearances(raw_dir)
    match_agg = _merge_appearances(match_agg, appearances).sort_values(
        ["player_id", "match_date", "match_id"]
    ).reset_index(drop=True)

    recent_dir = derived_dir / "recent"
    recent_dir.mkdir(parents=True, exist_ok=True)
    for stale in recent_dir.glob("*.json"):
        stale.unlink()

    latest_names = _latest_names(df)
    name_fallback = _name_fallback(raw_dir)
    overlay = _load_ranking_overlay(rankings_dir)

    # Last-20 match pairs per player, used by phase/format splits.
    last20_pairs = (
        match_agg.sort_values(["player_id", "match_date"], ascending=[True, False])
        .groupby("player_id", as_index=False)
        .head(20)[["player_id", "match_id"]]
    )
    bat_last20 = _filter_pairs(bat, last20_pairs)
    bowl_last20 = _filter_pairs(bowl, last20_pairs)

    career_phase = _phase_split(bat, bowl)
    last20_phase = _phase_split(bat_last20, bowl_last20)
    career_format = _format_split(bat, bowl)
    last20_format = _format_split(bat_last20, bowl_last20)

    index_rows: list[dict] = []
    written = 0

    for pid, player_matches in match_agg.groupby("player_id", sort=False):
        pid = str(pid)
        player_matches = player_matches.sort_values(
            ["match_date", "match_id"], ascending=[False, False]
        )

        balls_faced = int(player_matches["b_balls"].sum())
        balls_bowled = int(player_matches["w_balls"].sum())
        role = _guess_role(balls_faced, balls_bowled)
        latest = player_matches.iloc[0]

        last12 = player_matches[
            player_matches["match_date"] >= twelve_month_cutoff
        ]
        windows = {
            "last5": _window_stats(player_matches.head(5)),
            "last10": _window_stats(player_matches.head(10)),
            "last20": _window_stats(player_matches.head(20)),
            "last12m": _window_stats(last12),
            "career": _window_stats(player_matches),
        }
        for window_name, subset in (
            ("last5", player_matches.head(5)),
            ("last10", player_matches.head(10)),
            ("last20", player_matches.head(20)),
            ("last12m", last12),
            ("career", player_matches),
        ):
            windows[window_name]["from_date"] = _date_str(subset["match_date"].min())
            windows[window_name]["to_date"] = _date_str(subset["match_date"].max())

        profile = {
            "player_id": int(pid) if pid.isdigit() else pid,
            "name": latest_names.get(pid) or name_fallback.get(pid) or f"Player {pid}",
            "role": role,
            "latest_team": None if pd.isna(latest.get("player_team")) else str(latest.get("player_team")),
            "first_match_date": _date_str(player_matches["match_date"].min()),
            "last_match_date": _date_str(player_matches["match_date"].max()),
            "matches": int(len(player_matches)),
            "balls_faced": balls_faced,
            "balls_bowled": balls_bowled,
            "batting_innings": int((player_matches["b_balls"] > 0).sum()),
            "bowling_innings": int((player_matches["w_balls"] > 0).sum()),
            "data_window": {
                "from": _date_str(player_matches["match_date"].min()),
                "to": _date_str(player_matches["match_date"].max()),
                "as_of": data_end_ts.strftime("%Y-%m-%d"),
            },
        }

        log = [_match_log_row(row) for _, row in player_matches.head(25).iterrows()]

        payload = {
            "profile": profile,
            "matches": log,
            "windows": windows,
            "phase": {
                "last20": last20_phase.get(pid, {}),
                "career": career_phase.get(pid, {}),
            },
            "format_split": {
                "last20": last20_format.get(pid, {}),
                "career": career_format.get(pid, {}),
            },
            "notes": {
                "pressure_definition": (
                    "Rule-based descriptive pressure: 2nd innings overs 16-20 with "
                    "0.8-2.0 runs needed per remaining ball; or 2nd innings required "
                    "rate > 10 with fewer than 5 wickets in hand; or 3+ wickets down "
                    "in overs 1-6. Not the leverage-based headline score."
                ),
                "match_population": (
                    "Matches are those in which the player batted or bowled, after "
                    "excluding super overs, the two Emerging tournaments and "
                    "DLS/shortened matches."
                ),
                "windows": "Form windows are by matches; last12m uses a 12-month cutoff.",
                "small_sample_threshold_balls": SMALL_SAMPLE_BALLS,
            },
        }

        out_path = recent_dir / f"{pid}.json"
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
            encoding="utf-8",
        )
        written += 1

        rank_info = overlay.get(pid, {})
        index_rows.append(
            {
                "player_id": int(pid) if pid.isdigit() else pid,
                "name": profile["name"],
                "role": role,
                "latest_team": profile["latest_team"],
                "last_match_date": profile["last_match_date"],
                "ranked_role": rank_info.get("ranked_role"),
                "ranked_rank": rank_info.get("ranked_rank"),
            }
        )

    index_rows.sort(key=lambda r: _normalise_name(r["name"]))
    (derived_dir / "player_index.json").write_text(
        json.dumps(index_rows, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )

    stats_meta = build_stats(
        df,
        appearances,
        derived_dir / "stats",
        latest_names=latest_names,
        name_fallback=name_fallback,
        overlay=overlay,
    )

    meta = {
        "generated_at": _utc_now(),
        "data_end": data_end_ts.strftime("%Y-%m-%d"),
        "twelve_month_cutoff": twelve_month_cutoff.strftime("%Y-%m-%d"),
        "players": written,
        "eligible_matches": int(df["match_id"].nunique()),
        "eligible_deliveries": int(len(df)),
        "exclusions": {
            "super_overs": "innings 3 and 4 removed",
            "emerging_tournaments": sorted(EMERGING_COMPS),
            "dls_or_shortened": "matches with non-null revised_target removed",
        },
        "pressure_definition": (
            "2nd innings overs 16-20 with 0.8-2.0 runs needed per remaining ball; "
            "or 2nd innings required rate > 10 with fewer than 5 wickets in hand; "
            "or 3+ wickets down in overs 1-6."
        ),
        "stats": stats_meta,
    }
    (derived_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if verbose:
        print(
            f"Wrote {written} recent player files, player_index.json and meta.json "
            f"to {derived_dir}"
        )
        print(
            f"Wrote {stats_meta['players']} stats player files and stats/index.json "
            f"to {derived_dir / 'stats'}"
        )
        print(
            f"Rows in scope: {len(df):,} deliveries across "
            f"{df['match_id'].nunique():,} matches."
        )

    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", default=str(PROJECT_ROOT / "data_raw"), help="Raw data pack directory")
    parser.add_argument("--derived", default=str(PROJECT_ROOT / "data_derived"), help="Derived output directory")
    parser.add_argument("--rankings", default=str(PROJECT_ROOT / "data_rankings"), help="Ranking CSV directory")
    parser.add_argument("--data-end", default=DEFAULT_DATA_END, help="Last data date (YYYY-MM-DD)")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    args = parser.parse_args(argv)
    run_precompute(
        raw_dir=args.raw,
        derived_dir=args.derived,
        rankings_dir=args.rankings,
        data_end=args.data_end,
        verbose=not args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
