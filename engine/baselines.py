"""Opposition tiers and expected-runs/expected-wicket baselines (2022-2024)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.config import PSEUDO_BASELINE_BALLS, PSEUDO_TIER_BALLS, TRAIN_SEASONS

TRAIN = tuple(TRAIN_SEASONS)


def _league_key(league: str) -> str:
    return str(league)


def _smooth_rate(numerator, balls, prior_rate, pseudo=PSEUDO_TIER_BALLS):
    numerator = float(numerator)
    balls = float(balls)
    return (numerator + pseudo * prior_rate) / (balls + pseudo) if balls + pseudo > 0 else prior_rate


def _tiers(rates: pd.Series, fallback: int = 1) -> dict[str, int]:
    """Split teams into tertiles; lowest rate -> tier 0."""
    rates = rates.dropna()
    if rates.empty:
        return {}
    ordered = rates.sort_values(kind="stable")
    n = len(ordered)
    if n < 3:
        return {team: 1 for team in ordered.index}
    ranks = pd.Series(np.arange(n), index=ordered.index)
    tiers = pd.qcut(ranks, 3, labels=[0, 1, 2]).astype(int)
    return {str(team): int(tier) for team, tier in tiers.items()} | {"_fallback": fallback}


def build_tiers(df: pd.DataFrame) -> dict:
    train = df[df["season_year"].isin(TRAIN)]
    t20 = train[train["league"].eq("T20I")]
    bowling = t20[t20["legal_ball"].fillna(False).astype(bool)]
    bowling_totals = bowling.groupby("bowling_team").agg(
        runs=("bowler_runs", "sum"), balls=("legal_ball", "sum")
    )
    league_bowl = (
        float(bowling["bowler_runs"].sum()) / float(bowling["legal_ball"].sum())
        if len(bowling) and bowling["legal_ball"].sum()
        else 0.0
    )
    bowl_rates = bowling_totals.apply(
        lambda r: _smooth_rate(r["runs"], r["balls"], league_bowl), axis=1
    )
    bowl_tiers = _tiers(bowl_rates)

    batting = t20[t20["legal_ball"].fillna(False).astype(bool)]
    batting_totals = batting.groupby("batting_team").agg(
        runs=("team_runs", "sum"), balls=("legal_ball", "sum")
    )
    league_bat = (
        float(batting["team_runs"].sum()) / float(batting["legal_ball"].sum())
        if len(batting) and batting["legal_ball"].sum()
        else 0.0
    )
    bat_rates = batting_totals.apply(
        lambda r: _smooth_rate(r["runs"], r["balls"], league_bat), axis=1
    )
    bat_tiers = _tiers(bat_rates)

    return {
        "bowling_conceded_per_ball": {k: float(v) for k, v in bowl_rates.items()},
        "batting_runs_per_ball": {k: float(v) for k, v in bat_rates.items()},
        "bowling_tier": {k: v for k, v in bowl_tiers.items() if k != "_fallback"},
        "batting_tier": {k: v for k, v in bat_tiers.items() if k != "_fallback"},
        "league_bowling_mean": league_bowl,
        "league_batting_mean": league_bat,
    }


def _cell_key(league, innings, phase, bucket, tier) -> str:
    return f"{league}|{int(innings)}|{phase}|{bucket}|{tier}"


def build_baselines(df: pd.DataFrame, tiers: dict) -> dict:
    train = df[df["season_year"].isin(TRAIN)].copy()
    train["bowl_tier"] = np.where(
        train["league"].eq("IPL"),
        "neutral",
        train["bowling_team"].map(tiers["bowling_tier"]).fillna(1).astype(int).astype(str),
    )
    train["bat_tier"] = np.where(
        train["league"].eq("IPL"),
        "neutral",
        train["batting_team"].map(tiers["batting_tier"]).fillna(1).astype(int).astype(str),
    )

    # League priors over the training window.
    bat = train[train["ball_faced"].fillna(False).astype(bool)]
    bowl = train[train["legal_ball"].fillna(False).astype(bool)]
    league_priors = {}
    for league in ("IPL", "T20I"):
        b = bat[bat["league"].eq(league)]
        w = bowl[bowl["league"].eq(league)]
        league_priors[league] = {
            "bat_runs_per_ball": float(b["bat_runs"].sum() / len(b)) if len(b) else 0.0,
            "bat_wicket_rate": float(b["striker_dismissed"].sum() / len(b)) if len(b) else 0.05,
            "bowl_runs_per_ball": float(w["bowler_runs"].sum() / len(w)) if len(w) else 0.0,
            "bowl_wicket_rate": float(w["bowler_wicket"].sum() / len(w)) if len(w) else 0.05,
        }

    bat_cells = {}
    bat["cell"] = [
        _cell_key(r.league, r.innings, r.phase, r.wicket_bucket, r.bat_tier)
        for r in bat.itertuples()
    ]
    grouped = bat.groupby("cell").agg(
        balls=("bat_runs", "size"), runs=("bat_runs", "sum"), wkts=("striker_dismissed", "sum")
    )
    for cell, row in grouped.iterrows():
        league = cell.split("|", 1)[0]
        prior = league_priors.get(league, league_priors["T20I"])
        bat_cells[cell] = {
            "balls": int(row["balls"]),
            "expected_runs": _smooth_rate(
                row["runs"], row["balls"], prior["bat_runs_per_ball"], PSEUDO_BASELINE_BALLS
            ),
            "expected_wicket": _smooth_rate(
                row["wkts"], row["balls"], prior["bat_wicket_rate"], PSEUDO_BASELINE_BALLS
            ),
        }

    bowl_cells = {}
    bowl["cell"] = [
        _cell_key(r.league, r.innings, r.phase, r.wicket_bucket, r.bowl_tier)
        for r in bowl.itertuples()
    ]
    grouped = bowl.groupby("cell").agg(
        balls=("bowler_runs", "size"),
        runs=("bowler_runs", "sum"),
        wkts=("bowler_wicket", "sum"),
    )
    for cell, row in grouped.iterrows():
        league = cell.split("|", 1)[0]
        prior = league_priors.get(league, league_priors["T20I"])
        bowl_cells[cell] = {
            "balls": int(row["balls"]),
            "expected_runs": _smooth_rate(
                row["runs"], row["balls"], prior["bowl_runs_per_ball"], PSEUDO_BASELINE_BALLS
            ),
            "expected_wicket": _smooth_rate(
                row["wkts"], row["balls"], prior["bowl_wicket_rate"], PSEUDO_BASELINE_BALLS
            ),
        }

    return {
        "league_priors": league_priors,
        "batting_cells": bat_cells,
        "bowling_cells": bowl_cells,
        "training_matches": int(train["match_id"].nunique()),
        "training_deliveries": int(len(train)),
    }


def attach_baselines(df: pd.DataFrame, tiers: dict, baselines: dict) -> pd.DataFrame:
    out = df.copy()
    out["bowl_tier"] = np.where(
        out["league"].eq("IPL"),
        "neutral",
        out["bowling_team"].map(tiers["bowling_tier"]).fillna(1).astype(int).astype(str),
    )
    out["bat_tier"] = np.where(
        out["league"].eq("IPL"),
        "neutral",
        out["batting_team"].map(tiers["batting_tier"]).fillna(1).astype(int).astype(str),
    )
    bat_cells = baselines["batting_cells"]
    bowl_cells = baselines["bowling_cells"]
    priors = baselines["league_priors"]

    def bat_values(row):
        cell = _cell_key(row.league, row.innings, row.phase, row.wicket_bucket, row.bat_tier)
        values = bat_cells.get(cell)
        prior = priors.get(row.league, priors["T20I"])
        if values is None:
            return prior["bat_runs_per_ball"], prior["bat_wicket_rate"]
        return values["expected_runs"], values["expected_wicket"]

    def bowl_values(row):
        cell = _cell_key(row.league, row.innings, row.phase, row.wicket_bucket, row.bowl_tier)
        values = bowl_cells.get(cell)
        prior = priors.get(row.league, priors["T20I"])
        if values is None:
            return prior["bowl_runs_per_ball"], prior["bowl_wicket_rate"]
        return values["expected_runs"], values["expected_wicket"]

    bat_values_all = [bat_values(r) for r in out.itertuples()]
    bowl_values_all = [bowl_values(r) for r in out.itertuples()]
    out["exp_bat_runs"] = [v[0] for v in bat_values_all]
    out["exp_bat_wicket"] = [v[1] for v in bat_values_all]
    out["exp_bowl_runs"] = [v[0] for v in bowl_values_all]
    out["exp_bowl_wicket"] = [v[1] for v in bowl_values_all]

    faced = out["ball_faced"].fillna(False).astype(bool)
    legal = out["legal_ball"].fillna(False).astype(bool)
    # Bat impact is only defined on balls faced; bowler impact only on legal balls.
    out["bat_impact"] = np.where(faced, out["bat_runs"] - out["exp_bat_runs"], 0.0)
    out["bowl_impact_q"] = np.where(
        legal,
        out["exp_bowl_runs"]
        - out["bowler_runs"]
        + 20.0 * (out["bowler_wicket"].astype(int) - out["exp_bowl_wicket"]),
        0.0,
    )
    return out
