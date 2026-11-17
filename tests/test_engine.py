from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from precompute import prepare_deliveries

from engine.baselines import attach_baselines
from engine.config import CACHE_DIR, COMPOSITE_WEIGHTS
from engine.data import build_states
from engine.eb import add_components, add_ranks, bootstrap_ranks
from engine.leverage import EVENTS, event_probabilities


def _raw_pack(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    pd.DataFrame(
        [{"comp_id": 1, "comp_name": "IPL 2023", "match_format": "T20", "season": 2023}]
    ).to_csv(raw / "competitions.csv", index=False)
    pd.DataFrame(
        [
            {
                "match_id": 1,
                "comp_id": 1,
                "match_date": "2023-04-01",
                "venue_country": "India",
                "revised_target": None,
                "first_inn_revised_overs": None,
                "second_inn_revised_overs": None,
                "home_team_id": 1,
                "away_team_id": 2,
                "home_team": "Alpha",
                "away_team": "Beta",
                "win_team_id": 1,
                "result": "Alpha won",
            }
        ]
    ).to_csv(raw / "matches.csv", index=False)
    pd.DataFrame(
        [
            {"comp_id": 1, "team_id": 1, "team_name": "Alpha"},
            {"comp_id": 1, "team_id": 2, "team_name": "Beta"},
        ]
    ).to_csv(raw / "teams.csv", index=False)
    pd.DataFrame(
        [
            {"match_id": 1, "team_id": 1, "player_id": 1},
            {"match_id": 1, "team_id": 2, "player_id": 2},
        ]
    ).to_csv(raw / "playing_eleven.csv", index=False)

    rows = []

    def ball(innings, n, runs, **extra):
        row = {
            "match_id": 1,
            "innings": innings,
            "overid": (n - 1) // 6 + 1,
            "over_ball_num": (n - 1) % 6 + 1,
            "innings_ball_num": n,
            "batting_team_id": 1 if innings == 1 else 2,
            "bowling_team_id": 2 if innings == 1 else 1,
            "striker_id": 11 if innings == 1 else 22,
            "striker_name": "Alpha Batter" if innings == 1 else "Beta Batter",
            "bowler_id": 2 if innings == 1 else 1,
            "bowler_name": "Beta Bowler" if innings == 1 else "Alpha Bowler",
            "runs": runs,
            "is_four": runs == 4,
            "is_six": runs == 6,
            "is_wicket": False,
            "dismissal_type": None,
            "dismissed_player_id": None,
            "extras_type": None,
            "extras1_runs": 0,
            "extras_2_runs": 0,
        }
        row.update(extra)
        rows.append(row)

    n = 1
    for runs in (1, 4, 0, 0, 0):
        ball(1, n, runs)
        n += 1
    ball(1, n, 0, extras_type="wide", extras1_runs=1)
    n += 1
    ball(1, n, 1, extras_type="Overstep", extras1_runs=1)
    n += 1
    ball(1, n, 0, extras_type="legbyes", extras1_runs=2)
    n += 1
    ball(1, n, 0, extras_type="byes", extras1_runs=1)
    n += 1
    for runs in (6, 6, 0, 0, 0):
        ball(2, n, runs)
        n += 1
    pd.DataFrame(rows).to_csv(raw / "ball_by_ball.csv", index=False)
    return raw


def _tiny_dataset(tmp_path: Path) -> pd.DataFrame:
    df = prepare_deliveries(_raw_pack(tmp_path))
    df["win_team_id"] = 1.0
    df["match_date"] = pd.to_datetime(df["match_date"])
    df["season_year"] = df["match_date"].dt.year
    return build_states(df)


def test_legal_balls_extras_and_state(tmp_path: Path):
    df = _tiny_dataset(tmp_path)
    wide = df[df["extras_key"].eq("wide")].iloc[0]
    overstep = df[df["extras_key"].eq("overstep")].iloc[0]
    byes = df[df["extras_key"].eq("byes")].iloc[0]
    legbyes = df[df["extras_key"].eq("legbyes")].iloc[0]

    assert wide["legal_ball"] == False and wide["ball_faced"] == False
    assert wide["bowler_runs"] == 1 and wide["team_runs"] == 1
    assert overstep["legal_ball"] == False and overstep["ball_faced"] == True
    assert overstep["bowler_runs"] == 2 and overstep["team_runs"] == 2
    assert byes["legal_ball"] == True and byes["bowler_runs"] == 0 and byes["team_runs"] == 1
    assert legbyes["legal_ball"] == True and legbyes["bowler_runs"] == 0 and legbyes["team_runs"] == 2

    first = df[df["innings"] == 1]
    total = int(first["team_runs"].sum())
    second = df[df["innings"] == 2]
    assert second["target"].dropna().eq(total + 1).all()
    assert second["balls_remaining"].iloc[0] == 120
    assert second["runs_needed"].iloc[0] == total + 1
    assert first["target"].isna().all()
    assert first["legal_before"].iloc[0] == 0
    assert first["score_minus_par"].iloc[0] == 0


def test_leverage_event_probabilities_are_distributions(tmp_path: Path):
    df = _tiny_dataset(tmp_path)
    distributions, global_probs, balls = event_probabilities(df)
    assert balls > 0
    assert global_probs.shape == (len(EVENTS),)
    assert pytest.approx(float(global_probs.sum())) == 1.0
    assert (global_probs >= 0).all()
    for probs in distributions.values():
        assert probs.shape == (len(EVENTS),)
        assert (probs >= 0).all()
        assert pytest.approx(float(probs.sum())) == 1.0


def test_baseline_fallback_to_league_prior():
    df = pd.DataFrame(
        {
            "league": ["IPL", "T20I"],
            "innings": [1, 2],
            "phase": ["powerplay", "death"],
            "wicket_bucket": ["0-2", "6+"],
            "batting_team": ["Alpha", "Unknown"],
            "bowling_team": ["Beta", "Unknown"],
            "ball_faced": [True, True],
            "legal_ball": [True, True],
            "bat_runs": [1, 0],
            "bowler_runs": [1, 0],
            "striker_dismissed": [False, False],
            "bowler_wicket": [False, False],
            "team_runs": [1, 0],
        }
    )
    priors = {
        "IPL": {"bat_runs_per_ball": 1.4, "bat_wicket_rate": 0.05, "bowl_runs_per_ball": 1.4, "bowl_wicket_rate": 0.05},
        "T20I": {"bat_runs_per_ball": 1.2, "bat_wicket_rate": 0.06, "bowl_runs_per_ball": 1.2, "bowl_wicket_rate": 0.06},
    }
    baselines = {
        "league_priors": priors,
        "batting_cells": {"IPL|1|powerplay|0-2|neutral": {"balls": 10, "expected_runs": 2.0, "expected_wicket": 0.02}},
        "bowling_cells": {"IPL|1|powerplay|0-2|neutral": {"balls": 10, "expected_runs": 1.0, "expected_wicket": 0.03}},
    }
    tiers = {"bowling_tier": {}, "batting_tier": {}}
    out = attach_baselines(df, tiers, baselines)
    assert out["exp_bat_runs"].iloc[0] == 2.0
    assert out["exp_bat_runs"].iloc[1] == priors["T20I"]["bat_runs_per_ball"]
    assert out["exp_bowl_runs"].iloc[0] == 1.0
    assert out["exp_bowl_runs"].iloc[1] == priors["T20I"]["bowl_runs_per_ball"]


def _scoring_frame():
    return pd.DataFrame(
        {
            "player_id": ["1", "2", "3", "4"],
            "name": ["A", "B", "C", "D"],
            "pressure_balls": [0, 120, 300, 500],
            "impact100": [None, 20.0, 40.0, 10.0],
            "wpa100": [None, 0.5, 1.5, -0.5],
            "delta": [None, 5.0, 15.0, -5.0],
            "normal_impact": [5.0, 10.0, 10.0, 10.0],
            "consistency": [0.5, 0.6, 0.7, 0.4],
        }
    )


def _params():
    return {
        "k": 100.0,
        "ref": {"impact100": 20.0, "wpa100": 0.5, "delta": 5.0, "consistency": 0.55},
        "sd": {"impact100": 10.0, "wpa100": 0.5, "delta": 5.0, "consistency": 0.1},
    }


def test_shrinkage_weights_and_composite_formula():
    frame = _scoring_frame()
    params = _params()
    scored = add_components(frame, params, COMPOSITE_WEIGHTS["primary"])
    assert scored["eb_weight"].tolist()[0] == 0.0
    assert scored.loc[0, "shrunk_performance"] == params["ref"]["impact100"]
    assert scored.loc[1, "eb_weight"] == pytest.approx(120 / 220, abs=1e-3)
    assert scored.loc[2, "eb_weight"] == pytest.approx(300 / 400, abs=1e-3)
    assert scored.loc[2, "shrunk_performance"] == pytest.approx(0.75 * 40 + 0.25 * 20)
    expected = 50 + 10 * (
        0.45 * scored.loc[2, "z_performance"]
        + 0.25 * scored.loc[2, "z_wpa"]
        + 0.20 * scored.loc[2, "z_delta"]
        + 0.10 * scored.loc[2, "z_consistency"]
    )
    assert scored.loc[2, "score"] == pytest.approx(round(expected, 2), abs=0.01)
    assert scored.loc[2, "score"] > scored.loc[1, "score"] > scored.loc[0, "score"]


def test_ranks_and_qualification():
    frame = _scoring_frame()
    scored = add_components(frame, _params())
    ranked = add_ranks(scored, min_balls=150)
    assert sorted(ranked["all_rank"].tolist()) == [1, 2, 3, 4]
    assert ranked["score"].is_monotonic_decreasing
    status = ranked.set_index("player_id")["qualification_status"]
    assert status["1"] == "BELOW_MIN" and status["2"] == "BELOW_MIN"
    assert status["3"] == "QUALIFIED" and status["4"] == "QUALIFIED"
    assert ranked["qualified_rank"].dropna().tolist() == [1, 2]
    assert ranked["qualified_rank"].isna().sum() == 2


def _pm_frames():
    index = pd.MultiIndex.from_tuples(
        [("1", 1), ("2", 1), ("2", 2), ("3", 1), ("3", 2), ("4", 1)],
        names=["pid", "match_id"],
    )
    pm = pd.DataFrame(
        {
            "impact_sum": [0.0, 10.0, 12.0, 30.0, 20.0, 15.0],
            "balls": [0, 60, 60, 150, 150, 400],
            "wpa_sum": [0.0, 0.2, 0.3, 0.5, 0.4, -0.2],
            "positive": [0, 1, 1, 1, 1, 0],
        },
        index=index,
    )
    pnormal = pd.DataFrame(
        {"normal_impact_sum": [0.0, 5.0, 5.0, 10.0], "normal_balls": [10, 60, 200, 400]},
        index=pd.MultiIndex.from_tuples(
            [("1", 1), ("2", 1), ("3", 1), ("4", 1)], names=["pid", "match_id"]
        ),
    )
    return pm, pnormal


def test_bootstrap_is_reproducible():
    frame = _scoring_frame()
    params = _params()
    pm, pnormal = _pm_frames()
    scored = add_ranks(add_components(frame, params), min_balls=150)
    first = bootstrap_ranks(scored, pm, pnormal, params, np.array([1, 2]), min_balls=150, reps=8, seed=7)
    second = bootstrap_ranks(scored, pm, pnormal, params, np.array([1, 2]), min_balls=150, reps=8, seed=7)
    for column in ("score_lo", "score_hi", "rank_lo", "rank_hi"):
        assert first[column].tolist() == second[column].tolist()


def test_real_match_reconciliation():
    path = CACHE_DIR / "deliveries.parquet"
    if not path.exists():
        pytest.skip("delivery cache not built")
    df = pd.read_parquet(path)
    df["byes"] = np.where(df["extras_key"].eq("byes"), df["extras1_runs"], 0.0)
    df["legbyes"] = np.where(df["extras_key"].eq("legbyes"), df["extras1_runs"], 0.0)
    sums = df.groupby(["match_id", "innings"]).agg(
        team=("team_runs", "sum"),
        bat=("bat_runs", "sum"),
        extras1=("extras1_runs", "sum"),
        extras2=("extras_2_runs", "sum"),
        charged=("bowler_runs", "sum"),
        byes=("byes", "sum"),
        legbyes=("legbyes", "sum"),
    )
    candidates = sums[(sums["extras2"] == 0) & (sums["team"] > 0)]
    assert not candidates.empty
    match_id = candidates.index.get_level_values(0)[0]
    for (_, innings), row in candidates.loc[[match_id]].iterrows():
        assert row["team"] == pytest.approx(row["bat"] + row["extras1"] + row["extras2"])
        assert row["team"] == pytest.approx(row["charged"] + row["byes"] + row["legbyes"])
