from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from precompute import BOWLER_CREDIT_DISMISSALS, prepare_deliveries
from stats_engine import compute_stats

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data_raw"


def _delivery(**overrides) -> dict:
    row = {
        "match_id": "9001",
        "innings": 1,
        "overid": 1,
        "over_ball_num": 1,
        "match_date": "2026-05-01",
        "season": "2026",
        "format": "T20I",
        "phase": "powerplay",
        "pressure": False,
        "batting_type": "RHB",
        "pace_or_spin": "Pace",
        "stroke": "Cover Drive",
        "on_or_off": "Off-side",
        "ball_faced": True,
        "bat_runs": 0.0,
        "is_four": 0,
        "is_six": 0,
        "striker_dismissed": False,
        "batter_dismissal": None,
        "legal_ball": True,
        "extras_key": "",
        "extras1_runs": 0.0,
        "extras_2_runs": 0.0,
        "bowler_runs": 0.0,
        "bowler_wicket": False,
        "delivery_style": "Straight",
        "over_or_around": "Over",
        "bowl_speed": 0.0,
        "dismissal_type": None,
        "striker_id": "1",
        "bowler_id": "2",
    }
    row.update(overrides)
    return row


def _appearance(player_id, match_id, team_id, **overrides) -> dict:
    row = {
        "player_id": player_id,
        "match_id": match_id,
        "match_date": "2026-05-01",
        "team_id": team_id,
        "win_team_id": 10,
        "man_of_the_match": None,
        "batting_order": 3,
        "is_impact": 0,
        "is_captain": 0,
        "is_wk": 0,
        "season": "2026",
        "format": "T20I",
        "player_team": f"Team {team_id}",
        "opponent": "Other",
    }
    row.update(overrides)
    return row


def _career(df: pd.DataFrame, appearances: pd.DataFrame) -> dict[str, dict]:
    players, _index, _meta = compute_stats(df, pd.DataFrame(appearances), latest_names={"1": "Batter A", "2": "Bowler B", "3": "Batter C"})
    return {pid: payload["splits"]["career"] for pid, payload in players.items()}


def test_legal_balls_extras_and_hand_verified_totals():
    deliveries = [
        _delivery(over_ball_num=1, extras_key="wide", legal_ball=False, ball_faced=False, extras1_runs=1, bowler_runs=1),
        _delivery(over_ball_num=1, extras_key="overstep", legal_ball=False, bat_runs=2, extras1_runs=1, bowler_runs=3),
        _delivery(over_ball_num=1, bat_runs=4, is_four=1, bowler_runs=4),
        _delivery(over_ball_num=2, striker_dismissed=True, batter_dismissal="Bowled", dismissal_type="Bowled", bowler_wicket=True),
        _delivery(over_ball_num=3, bat_runs=1, bowler_runs=1),
        _delivery(over_ball_num=4, extras_key="byes", extras1_runs=2),
        _delivery(over_ball_num=5, bat_runs=6, is_six=1, bowler_runs=6),
        _delivery(over_ball_num=6),
    ]
    appearances = [
        _appearance(1, "9001", 10, man_of_the_match=1),
        _appearance(2, "9001", 20),
    ]
    career = _career(pd.DataFrame(deliveries), appearances)

    batting = career["1"]["batting"]
    assert batting["matches"] == 1
    assert batting["innings"] == 1
    assert batting["not_outs"] == 0
    assert batting["runs"] == 13
    assert batting["balls"] == 7  # wide excluded, Overstep included
    assert batting["strike_rate"] == pytest.approx(185.7)
    assert batting["average"] == pytest.approx(13.0)
    assert batting["highest"] == 13
    assert batting["fours"] == 1
    assert batting["sixes"] == 1
    assert batting["boundary_pct"] == pytest.approx(76.9)
    assert batting["balls_per_boundary"] == pytest.approx(3.5)
    assert batting["dot_pct"] == pytest.approx(42.9)  # includes the byes ball
    assert batting["singles"] == 1
    assert batting["twos"] == 1
    assert batting["balls_per_dismissal"] == pytest.approx(7.0)
    assert batting["small_sample"] is True

    bowling = career["2"]["bowling"]
    assert bowling["matches"] == 1
    assert bowling["legal_balls"] == 6
    assert bowling["overs"] == "1.0"
    assert bowling["runs"] == 15  # bat runs + wide + Overstep extras; byes not charged
    assert bowling["wickets"] == 1
    assert bowling["economy"] == pytest.approx(15.0)
    assert bowling["average"] == pytest.approx(15.0)
    assert bowling["strike_rate"] == pytest.approx(6.0)
    assert bowling["dot_pct"] == pytest.approx(50.0)
    assert bowling["fours"] == 1
    assert bowling["sixes"] == 1
    assert bowling["balls_per_boundary"] == pytest.approx(3.0)
    assert bowling["wides"] == 1
    assert bowling["no_balls"] == 1
    assert bowling["total_extras"] == 2
    assert bowling["byes_legbyes"] == 2
    assert bowling["maidens"] == 0
    assert bowling["best"] == {"wickets": 1, "runs": 15, "balls": 6}
    assert bowling["runs_per_over"] == [{"runs": 15, "count": 1}]
    assert bowling["wicket_types"] == {"Bowled": 1}


def test_maidens_hauls_runouts_and_not_outs():
    deliveries = [
        _delivery(match_id="9002", overid=1, over_ball_num=1, bowler_wicket=True, dismissal_type="Bowled"),
        _delivery(match_id="9002", overid=1, over_ball_num=2, bowler_wicket=True, dismissal_type="Bowled"),
        _delivery(match_id="9002", overid=1, over_ball_num=3, bowler_wicket=True, dismissal_type="Bowled"),
        _delivery(match_id="9002", overid=1, over_ball_num=4, bowler_wicket=True, dismissal_type="Bowled"),
        _delivery(match_id="9002", overid=1, over_ball_num=5, bowler_wicket=True, dismissal_type="Bowled"),
        _delivery(match_id="9002", overid=1, over_ball_num=6),
        # Golden duck, then a not-out innings in the next match.
        _delivery(match_id="9003", striker_id="3", bowler_id="4", striker_dismissed=True, batter_dismissal="Bowled", dismissal_type="Bowled", bowler_wicket=True),
        _delivery(match_id="9004", striker_id="3", bowler_id="4", bat_runs=5, bowler_runs=5),
        _delivery(match_id="9004", striker_id="3", bowler_id="4", over_ball_num=2),
        _delivery(match_id="9004", striker_id="3", bowler_id="4", over_ball_num=3),
        # Run out: striker out, no wicket credited to the bowler.
        _delivery(
            match_id="9005",
            striker_id="3",
            bowler_id="4",
            striker_dismissed=True,
            batter_dismissal="RunOut",
            dismissal_type="RunOut",
            bowler_wicket=False,
        ),
    ]
    appearances = [
        _appearance(2, "9002", 20),
        _appearance(3, "9003", 30),
        _appearance(3, "9004", 30, match_date="2026-05-05"),
        _appearance(3, "9005", 30, match_date="2026-05-09"),
    ]
    career = _career(pd.DataFrame(deliveries), appearances)

    bowling = career["2"]["bowling"]
    assert bowling["legal_balls"] == 6
    assert bowling["runs"] == 0
    assert bowling["wickets"] == 5
    assert bowling["maidens"] == 1
    assert bowling["best"] == {"wickets": 5, "runs": 0, "balls": 6}
    assert bowling["five_w"] == 1
    assert bowling["four_w"] == 1
    assert bowling["three_w"] == 1
    assert bowling["two_w"] == 1

    batting = career["3"]["batting"]
    assert batting["matches"] == 3
    assert batting["innings"] == 3
    assert batting["not_outs"] == 1  # the run-out innings counts as a dismissal
    assert batting["runs"] == 5
    assert batting["highest"] == 5
    assert batting["ducks"] == 2
    assert batting["golden_ducks"] == 2
    assert batting["average"] == pytest.approx(2.5)
    assert career["3"]["bowling"] is None

    assert "runout" not in BOWLER_CREDIT_DISMISSALS
    assert "retire out" not in BOWLER_CREDIT_DISMISSALS
    assert "obstructing the field" not in BOWLER_CREDIT_DISMISSALS
    assert "stumped" in BOWLER_CREDIT_DISMISSALS


@pytest.mark.skipif(not (RAW_DIR / "ball_by_ball.csv").exists(), reason="confidential raw pack not available")
def test_real_match_reconciliation():
    df = prepare_deliveries(RAW_DIR)
    extras = df["extras1_runs"].fillna(0) + df["extras_2_runs"].fillna(0)
    team_runs = df["bat_runs"] + extras
    charged = df["bowler_runs"] + extras.where(df["extras_key"].isin(["byes", "legbyes"]), 0)
    grouped = (
        pd.DataFrame(
            {
                "match_id": df["match_id"],
                "innings": df["innings"],
                "team_runs": team_runs,
                "reconciled": charged,
                "deliveries": 1,
            }
        )
        .groupby(["match_id", "innings"])
        .sum()
    )

    chosen = None
    for match_id, innings in grouped.groupby(level=0):
        if (
            len(innings) == 2
            and innings["deliveries"].min() >= 60
            and (innings["team_runs"] == innings["reconciled"]).all()
        ):
            chosen = innings
            break
    assert chosen is not None, "no clean match found for reconciliation"
    for _, row in chosen.iterrows():
        assert row["team_runs"] == row["reconciled"]
        assert row["team_runs"] > 0


def _stats_index_payload() -> dict:
    return {
        "generated_at": "2026-11-16T00:00:00Z",
        "players": [
            {
                "player_id": 11,
                "name": "Test Batter",
                "role": "batter",
                "latest_team": "Rajasthan Royals",
                "seasons": ["2024"],
                "competitions": ["IPL"],
                "batting": {"balls": 150, "runs": 120, "strike_rate": 80.0, "average": 30.0},
                "bowling": None,
                "ranked_role": None,
                "ranked_rank": None,
            },
            {
                "player_id": 12,
                "name": "Test Bowler",
                "role": "bowler",
                "latest_team": "Mumbai Indians",
                "seasons": ["2025"],
                "competitions": ["T20I"],
                "batting": None,
                "bowling": {"legal_balls": 130, "runs": 100, "wickets": 10, "economy": 7.5},
                "ranked_role": None,
                "ranked_rank": None,
            },
        ],
        "options": {
            "teams": ["Mumbai Indians", "Rajasthan Royals"],
            "seasons": ["2024", "2025"],
            "competitions": ["IPL", "T20I"],
            "roles": ["batter", "bowler"],
        },
        "meta": {"players": 2, "splits": 22},
    }


def _stats_player_payload(pid: int, name: str, role: str) -> dict:
    batting = {
        "matches": 10,
        "innings": 10,
        "not_outs": 2,
        "runs": 120,
        "balls": 150,
        "strike_rate": 80.0,
        "average": 30.0,
        "highest": 45,
        "fifties": 0,
        "hundreds": 0,
        "boundary_pct": 20.0,
        "dot_pct": 40.0,
    }
    bowling = {
        "matches": 10,
        "innings": 10,
        "legal_balls": 130,
        "overs": "21.4",
        "runs": 100,
        "wickets": 10,
        "economy": 7.5,
        "average": 10.0,
        "strike_rate": 13.0,
        "dot_pct": 35.0,
        "maidens": 0,
        "four_w": 1,
        "five_w": 0,
    }
    splits = {
        "career": {
            "label": "Career",
            "batting": batting if role != "bowler" else None,
            "bowling": bowling if role != "batter" else None,
        },
        "IPL": {
            "label": "IPL",
            "batting": batting if role != "bowler" else None,
            "bowling": bowling if role != "batter" else None,
        },
    }
    return {
        "player_id": pid,
        "name": name,
        "latest_team": "Rajasthan Royals",
        "role": role,
        "small_sample_threshold_balls": 30,
        "splits": splits,
        "notes": {},
        "definitions": {"batting": {"runs": "Bat runs only."}, "bowling": {"economy": "Runs per over."}},
    }


def test_stats_api(tmp_path: Path):
    derived = tmp_path / "derived"
    stats_dir = derived / "stats"
    stats_dir.mkdir(parents=True)
    (stats_dir / "index.json").write_text(json.dumps(_stats_index_payload()), encoding="utf-8")
    (stats_dir / "11.json").write_text(
        json.dumps(_stats_player_payload(11, "Test Batter", "batter")), encoding="utf-8"
    )
    (stats_dir / "12.json").write_text(
        json.dumps(_stats_player_payload(12, "Test Bowler", "bowler")), encoding="utf-8"
    )

    app = create_app(root=tmp_path, rankings_dir=tmp_path / "rankings", derived_dir=derived)
    with TestClient(app) as client:
        index = client.get("/api/stats-index", params={"role": "batter", "min_balls": 100})
        assert index.status_code == 200
        assert index.json()["count"] == 1
        assert index.json()["threshold_balls"] == 100

        empty = client.get("/api/stats-index", params={"role": "batter", "min_balls": 200})
        assert empty.json()["count"] == 0

        bowler_index = client.get("/api/stats-index", params={"role": "bowler", "min_balls": 120})
        assert bowler_index.json()["count"] == 1

        player = client.get("/api/stats/11", params={"split": "career"})
        assert player.status_code == 200
        payload = player.json()
        assert payload["split"] == "career"
        assert payload["batting"]["runs"] == 120
        assert payload["percentiles"]["batting"]["runs"] == 50.0  # single-value cohort
        assert {entry["key"] for entry in payload["available_splits"]} == {"career", "IPL"}

        bowler = client.get("/api/stats/12").json()
        assert bowler["bowling"]["economy"] == 7.5
        assert bowler["percentiles"]["bowling"]["economy"] == 50.0

        assert client.get("/api/stats/999").status_code == 404
        assert client.get("/api/stats-index", params={"role": "nope"}).status_code == 422
