"""Data loading, exclusions and per-delivery match state for the engine."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from precompute import (
    EMERGING_COMPS,
    _canon_id,
    _name_fallback,
    load_appearances,
    prepare_deliveries,
)

from engine.config import (
    CACHE_DIR,
    DATA_END,
    DATA_START,
    LEAGUES,
    PHASES,
)

STATE_FEATURES = [
    "innings",
    "balls_remaining",
    "wickets_down",
    "team_score",
    "target",
    "runs_needed",
    "required_rate",
    "current_rate",
    "rate_gap",
    "score_minus_par",
    "is_ipl",
]


def _num(series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _is_tie(result: pd.Series) -> pd.Series:
    return result.fillna("").astype(str).str.lower().str.contains("tied", regex=False)


def load_match_table(raw_dir: Path) -> pd.DataFrame:
    comps = pd.read_csv(raw_dir / "competitions.csv")
    matches = pd.read_csv(raw_dir / "matches.csv")
    matches["match_date"] = pd.to_datetime(matches["match_date"], errors="coerce")
    for col in ("revised_target", "first_inn_revised_overs", "second_inn_revised_overs", "win_team_id"):
        if col not in matches.columns:
            matches[col] = np.nan
        matches[col] = _num(matches[col])
    matches = matches.merge(comps, on="comp_id", how="left")
    matches["format"] = np.where(
        matches["comp_name"].astype(str).str.upper().str.startswith("IPL"),
        "IPL",
        np.where(matches["match_format"].astype(str).eq("T20I"), "T20I", "T20"),
    )
    matches["is_tie"] = _is_tie(matches.get("result", pd.Series([""] * len(matches), index=matches.index)))
    return matches


def filter_matches(matches: pd.DataFrame, data_start=DATA_START, data_end=DATA_END) -> pd.DataFrame:
    start = pd.Timestamp(data_start)
    end = pd.Timestamp(data_end)
    keep = (
        (~matches["comp_name"].isin(EMERGING_COMPS))
        & (matches["format"].isin(LEAGUES))
        & (matches["match_date"].notna())
        & (matches["match_date"] >= start)
        & (matches["match_date"] <= end)
        & (matches["revised_target"].isna())
        & (matches["first_inn_revised_overs"].isna())
        & (matches["second_inn_revised_overs"].isna())
        & (matches["win_team_id"].notna())
        & (~matches["is_tie"])
    )
    return matches[keep].copy()


def _flag_innings(df: pd.DataFrame) -> dict:
    """Count innings with more than 120 legal balls or inconsistent states."""
    innings = df.groupby(["match_id", "innings"], sort=False)
    max_legal = innings["legal_before"].max()
    overflow_balls = max_legal[max_legal > 120]
    overflow_wickets = df.loc[df["wickets_before"] > 9].groupby(["match_id", "innings"]).size()
    chase_over = df[(df["innings"] == 2) & (df["runs_needed"].fillna(-1) <= 0)].groupby(
        ["match_id", "innings"]
    ).size()
    missing_target = (
        df[(df["innings"] == 2) & (df["target"].isna())]
        .groupby(["match_id", "innings"])
        .size()
        if len(df)
        else pd.Series(dtype=int)
    )
    return {
        "more_than_120_legal_balls": int(len(overflow_balls)),
        "more_than_10_wickets": int(len(overflow_wickets)),
        "deliveries_after_chase_complete": int(chase_over.sum()) if len(chase_over) else 0,
        "innings_missing_target": int(len(missing_target)),
        "innings_checked": int(df.groupby(["match_id", "innings"]).ngroups),
    }


def build_states(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute clean pre-delivery state on the filtered data."""
    df = df.copy()
    df = df.sort_values(
        ["match_id", "innings", "innings_ball_num", "over_ball_num"], kind="stable"
    ).reset_index(drop=True)

    first_innings = (
        df[df["innings"] == 1].groupby("match_id", as_index=True)["team_runs"].sum()
    )
    df["first_innings_total"] = df["match_id"].map(first_innings)

    grouped = df.groupby(["match_id", "innings"], sort=False)
    df["runs_before"] = grouped["team_runs"].cumsum() - df["team_runs"]
    df["wickets_down"] = grouped["is_wicket"].cumsum() - df["is_wicket"].astype(int)
    df["legal_before"] = grouped["legal_ball"].cumsum() - df["legal_ball"].astype(int)

    df["balls_remaining"] = (120.0 - df["legal_before"]).clip(lower=0.0)
    df["team_score"] = df["runs_before"]
    df["target"] = np.where(df["innings"].eq(2), df["first_innings_total"] + 1.0, np.nan)
    df["runs_needed"] = np.where(
        df["innings"].eq(2), (df["target"] - df["team_score"]).clip(lower=0.0), np.nan
    )
    df["required_rate"] = np.where(
        df["innings"].eq(2),
        df["runs_needed"] / df["balls_remaining"].replace(0, np.nan) * 6.0,
        np.nan,
    )
    df["current_rate"] = df["team_score"] / df["legal_before"].replace(0, np.nan) * 6.0
    df["rate_gap"] = df["required_rate"] - df["current_rate"]
    df["par_score"] = 1.4 * df["legal_before"]
    df["score_minus_par"] = df["team_score"] - df["par_score"]
    df["league"] = df["format"]
    df["is_ipl"] = df["league"].eq("IPL").astype(int)
    df["wicket_bucket"] = np.select(
        [df["wickets_down"] <= 2, df["wickets_down"] <= 5],
        ["0-2", "3-5"],
        default="6+",
    )
    df["phase"] = np.select(
        [df["overid"] <= 6, df["overid"] <= 15], ["powerplay", "middle"], default="death"
    )
    df["pressure_rule"] = df["pressure"].fillna(False).astype(bool)
    df["batting_won"] = (df["win_team_id"].fillna(-1) == df["batting_team_id"].fillna(-2)).astype(int)
    df["season_year"] = df["match_date"].dt.year
    return df


def attach_names_and_teams(df: pd.DataFrame, raw_dir: Path, appearances: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach player names, latest teams and XI-derived flags."""
    mapping_fallback = _name_fallback(raw_dir)
    rows = pd.concat(
        [
            df[["striker_id", "striker_name", "match_date"]].rename(
                columns={"striker_id": "player_id", "striker_name": "name"}
            ),
            df[["bowler_id", "bowler_name", "match_date"]].rename(
                columns={"bowler_id": "player_id", "bowler_name": "name"}
            ),
        ],
        ignore_index=True,
    )
    rows = rows.dropna(subset=["player_id", "name"]).copy()
    rows["player_id"] = rows["player_id"].map(_canon_id)
    rows = rows.dropna(subset=["player_id"]).sort_values(["player_id", "match_date"])
    latest_name = rows.groupby("player_id").tail(1).set_index("player_id")["name"].astype(str).to_dict()

    apps = appearances.copy()
    apps["player_id"] = apps["player_id"].map(_canon_id)
    apps = apps[apps["player_id"].notna()].copy()
    apps["match_date"] = pd.to_datetime(apps["match_date"], errors="coerce")

    latest_team = (
        apps.sort_values(["player_id", "match_date", "match_id"])
        .groupby("player_id")
        .tail(1)
        .set_index("player_id")["player_team"]
    )
    ipl_apps = apps[apps["format"].eq("IPL")]
    latest_ipl_team = (
        ipl_apps.sort_values(["player_id", "match_date", "match_id"])
        .groupby("player_id")
        .tail(1)
        .set_index("player_id")["player_team"]
    )
    ipl_played = ipl_apps.groupby("player_id").size()
    played_2026 = ipl_apps[ipl_apps["season"].astype(str).str.startswith("2026")].groupby("player_id").size()

    players = pd.DataFrame({"player_id": sorted(set(latest_name) | set(latest_team.index))})
    players["name"] = players["player_id"].map(latest_name).fillna(
        players["player_id"].map(mapping_fallback)
    )
    players["name"] = players["name"].fillna(players["player_id"].map(lambda p: f"Player {p}"))
    players["latest_team"] = players["player_id"].map(latest_team)
    players["latest_IPL_team"] = players["player_id"].map(latest_ipl_team)
    players["IPL_PLAYED"] = np.where(players["player_id"].isin(ipl_played.index), "Y", "N")
    players["PLAYED_2026_IPL"] = np.where(players["player_id"].isin(played_2026.index), "Y", "N")
    return df, players


def build_dataset(raw_dir: Path, data_start=DATA_START, data_end=DATA_END, refresh: bool = False):
    """Build (and cache) the filtered delivery table, matches and player metadata."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    deliveries_path = CACHE_DIR / "deliveries.parquet"
    matches_path = CACHE_DIR / "matches.parquet"
    players_path = CACHE_DIR / "players.parquet"
    info_path = CACHE_DIR / "dataset_info.json"

    if not refresh and deliveries_path.exists() and matches_path.exists() and players_path.exists():
        df = pd.read_parquet(deliveries_path)
        matches = pd.read_parquet(matches_path)
        players = pd.read_parquet(players_path)
        info = json.loads(info_path.read_text(encoding="utf-8"))
        return df, matches, players, info

    raw_matches = load_match_table(raw_dir)
    matches = filter_matches(raw_matches, data_start, data_end)
    raw = prepare_deliveries(raw_dir, data_end=data_end)
    df = raw.merge(
        matches[["match_id", "win_team_id", "result", "first_inn_revised_overs", "second_inn_revised_overs"]],
        on="match_id",
        how="inner",
    )
    df = df[
        df["format"].isin(LEAGUES)
        & (df["match_date"] >= pd.Timestamp(data_start))
        & (df["match_date"] <= pd.Timestamp(data_end))
        & df["win_team_id"].notna()
        & (~_is_tie(df["result"]))
        & df["first_inn_revised_overs"].isna()
        & df["second_inn_revised_overs"].isna()
    ].copy()

    df = build_states(df)
    innings_flags = _flag_innings(df)

    appearances = load_appearances(raw_dir)
    appearances = appearances[
        appearances["format"].isin(LEAGUES)
        & (appearances["match_date"] >= pd.Timestamp(data_start))
        & (appearances["match_date"] <= pd.Timestamp(data_end))
        & appearances["match_id"].isin(matches["match_id"])
    ].copy()
    df, players = attach_names_and_teams(df, raw_dir, appearances)

    info = {
        "data_start": str(pd.Timestamp(data_start).date()),
        "data_end": str(pd.Timestamp(data_end).date()),
        "raw_matches": int(len(raw_matches)),
        "eligible_matches": int(df["match_id"].nunique()),
        "eligible_deliveries": int(len(df)),
        "batters": int(df["striker_id"].nunique()),
        "bowlers": int(df["bowler_id"].nunique()),
        "matches_excluded_no_winner": int(
            (raw_matches["win_team_id"].isna() & raw_matches["format"].isin(LEAGUES)).sum()
        ),
        "matches_excluded_tie": int(
            (raw_matches["is_tie"] & raw_matches["format"].isin(LEAGUES)).sum()
        ),
        "innings_flags": innings_flags,
        "seasons": sorted(
            {int(s) for s in df["season_year"].dropna().astype(int).unique()}
        ),
    }

    df.to_parquet(deliveries_path, index=False)
    matches[["match_id", "match_date", "format", "season", "win_team_id", "result"]].to_parquet(
        matches_path, index=False
    )
    players.to_parquet(players_path, index=False)
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return df, matches, players, info


def match_partition(df: pd.DataFrame) -> pd.Series:
    """Return 'train' / 'calibration' / 'test' per delivery using whole matches."""
    season = df["season_year"]
    partition = pd.Series("test", index=df.index, dtype="object")
    partition[season.isin((2022, 2023))] = "train"
    partition[season == 2024] = "calibration"
    return partition


def league_mean(values: pd.Series, weights: pd.Series | None = None) -> float:
    values = pd.to_numeric(values, errors="coerce")
    mask = values.notna()
    if weights is None:
        return float(values[mask].mean()) if mask.any() else 0.0
    w = pd.to_numeric(weights, errors="coerce").fillna(0)[mask]
    total = float(w.sum())
    return float((values[mask] * w).sum() / total) if total > 0 else 0.0


def safe_float(value, digits: int = 2):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)
