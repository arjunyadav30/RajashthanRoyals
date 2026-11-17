from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import precompute as P


def _delivery(
    match_id: int,
    innings: int,
    over: int,
    ball_in_over: int,
    innings_ball: int,
    batting_team: int,
    bowling_team: int,
    striker: int,
    bowler: int,
    **overrides,
) -> dict:
    row = {
        "match_id": match_id,
        "innings": innings,
        "overid": over,
        "over_ball_num": ball_in_over,
        "innings_ball_num": innings_ball,
        "batting_team_id": batting_team,
        "bowling_team_id": bowling_team,
        "striker_id": striker,
        "striker_name": f"Player {striker}",
        "bowler_id": bowler,
        "bowler_name": f"Player {bowler}",
        "runs": 0,
        "is_four": False,
        "is_six": False,
        "is_wicket": False,
        "dismissal_type": None,
        "dismissed_player_id": None,
        "extras_type": None,
        "extras1_runs": 0,
        "extras_2_runs": 0,
    }
    row.update(overrides)
    return row


def _innings_rows(
    match_id: int,
    innings: int,
    batting_team: int,
    bowling_team: int,
    striker: int,
    bowler: int,
    runs_by_legal: list[int],
    wicket_at: dict[int, dict] | None = None,
    extras_before: dict[int, list[dict]] | None = None,
) -> list[dict]:
    wicket_at = wicket_at or {}
    extras_before = extras_before or {}
    rows: list[dict] = []
    innings_ball = 0
    for i, runs in enumerate(runs_by_legal):
        over = i // 6 + 1
        ball_in_over = i % 6 + 1
        for extra in extras_before.get(i, []):
            innings_ball += 1
            rows.append(
                _delivery(
                    match_id,
                    innings,
                    over,
                    ball_in_over,
                    innings_ball,
                    batting_team,
                    bowling_team,
                    striker,
                    bowler,
                    **extra,
                )
            )
        innings_ball += 1
        wicket = wicket_at.get(i, {})
        rows.append(
            _delivery(
                match_id,
                innings,
                over,
                ball_in_over,
                innings_ball,
                batting_team,
                bowling_team,
                striker,
                bowler,
                runs=runs,
                is_four=runs == 4,
                is_six=runs == 6,
                **wicket,
            )
        )
    return rows


def _write_pack(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()

    competitions = pd.DataFrame(
        [
            {"comp_id": 1, "comp_name": "IPL 2026", "match_format": "T20", "season": 2026},
            {
                "comp_id": 2,
                "comp_name": "Mens T20 Emerging Teams Asia Cup 2024",
                "match_format": "T20",
                "season": 2024,
            },
        ]
    )
    matches = pd.DataFrame(
        [
            {
                "match_id": 100, "comp_id": 1, "match_date": "2026-01-01",
                "venue_country": "India", "revised_target": None,
                "home_team_id": 1, "away_team_id": 2, "home_team": "Alpha", "away_team": "Beta",
            },
            {
                "match_id": 101, "comp_id": 1, "match_date": "2026-01-02",
                "venue_country": "India", "revised_target": None,
                "home_team_id": 2, "away_team_id": 1, "home_team": "Beta", "away_team": "Alpha",
            },
            {
                "match_id": 102, "comp_id": 1, "match_date": "2026-01-03",
                "venue_country": "India", "revised_target": 90,
                "home_team_id": 1, "away_team_id": 2, "home_team": "Alpha", "away_team": "Beta",
            },
            {
                "match_id": 104, "comp_id": 2, "match_date": "2024-06-01",
                "venue_country": "United Arab Emirates", "revised_target": None,
                "home_team_id": 1, "away_team_id": 2, "home_team": "India A", "away_team": "UAE",
            },
            {
                "match_id": 105, "comp_id": 1, "match_date": "2026-01-05",
                "venue_country": "India", "revised_target": None,
                "home_team_id": 2, "away_team_id": 1, "home_team": "Beta", "away_team": "Alpha",
            },
        ]
    )
    teams = pd.DataFrame(
        [
            {"comp_id": 1, "team_id": 1, "team_name": "Alpha"},
            {"comp_id": 1, "team_id": 2, "team_name": "Beta"},
            {"comp_id": 2, "team_id": 1, "team_name": "India A"},
            {"comp_id": 2, "team_id": 2, "team_name": "UAE"},
        ]
    )

    xi_rows = []
    for match_id, team_id, players in [
        (100, 1, [1, 2, 3, 7]),
        (100, 2, [4, 5, 6]),
        (101, 1, [1, 2, 3]),
        (101, 2, [4, 5, 6]),
        (102, 1, [8]),
        (104, 1, [8]),
        (105, 1, [5]),
        (105, 2, [4]),
    ]:
        for player_id in players:
            xi_rows.append(
                {
                    "match_id": match_id,
                    "team_id": team_id,
                    "player_id": player_id,
                    "batting_order": None,
                    "is_played": True,
                    "is_captain": False,
                    "is_wk": False,
                    "is_impact": 0,
                    "is_impact_off": 0,
                }
            )
    playing_eleven = pd.DataFrame(xi_rows)

    deliveries: list[dict] = []
    # Match 100: a regulation chase. All ones, no wickets -> condition A from over 16.
    deliveries += _innings_rows(100, 1, 1, 2, 1, 4, [1] * 120)
    deliveries += _innings_rows(100, 2, 2, 1, 4, 1, [1] * 120)
    # Super over, must be excluded.
    deliveries += _innings_rows(100, 3, 1, 2, 9, 5, [6] * 6)

    # Match 101: early collapse in innings 1; condition B chase in innings 2.
    deliveries += _innings_rows(
        101, 1, 1, 2, 1, 4, [1] * 120,
        wicket_at={
            6: {"is_wicket": True, "dismissal_type": "Bowled", "dismissed_player_id": 6},
            7: {"is_wicket": True, "dismissal_type": "Bowled", "dismissed_player_id": 5},
            8: {"is_wicket": True, "dismissal_type": "Bowled", "dismissed_player_id": 4},
        },
    )
    chase_runs = [1] * 20 + [0] * 100
    deliveries += _innings_rows(
        101, 2, 2, 1, 4, 1, chase_runs,
        wicket_at={
            42: {"is_wicket": True, "dismissal_type": "RunOut", "dismissed_player_id": 6},
            43: {"is_wicket": True, "dismissal_type": "RunOut", "dismissed_player_id": 6},
            48: {"is_wicket": True, "dismissal_type": "RunOut", "dismissed_player_id": 6},
            49: {"is_wicket": True, "dismissal_type": "RunOut", "dismissed_player_id": 6},
            54: {"is_wicket": True, "dismissal_type": "RunOut", "dismissed_player_id": 6},
            55: {"is_wicket": True, "dismissal_type": "RunOut", "dismissed_player_id": 6},
        },
    )

    # Match 102: DLS, excluded.
    deliveries += _innings_rows(102, 1, 1, 2, 1, 4, [1] * 120)
    deliveries += _innings_rows(102, 2, 2, 1, 4, 1, [1] * 120)
    # Match 104: Emerging tournament, excluded.
    deliveries += _innings_rows(104, 1, 1, 2, 1, 4, [1] * 120)
    deliveries += _innings_rows(104, 2, 2, 1, 4, 1, [1] * 120)

    # Match 105: exact attribution fixture.
    deliveries += _innings_rows(
        105, 1, 2, 1, 4, 5, [1, 4, 0, 0, 0, 0, 0],
        extras_before={
            1: [{"extras_type": "wide", "extras1_runs": 1}],
            2: [{"extras_type": "Overstep", "extras1_runs": 1, "runs": 6, "is_six": True}],
            3: [{"extras_type": "legbyes", "extras1_runs": 4}],
            4: [{"extras_type": "byes", "extras1_runs": 2}],
            5: [{"extras_type": "other", "extras1_runs": 1}],
        },
        wicket_at={
            5: {"is_wicket": True, "dismissal_type": "RunOut", "dismissed_player_id": 6},
            6: {"is_wicket": True, "dismissal_type": "Bowled", "dismissed_player_id": 4},
        },
    )

    ball_by_ball = pd.DataFrame(deliveries)

    mapping = pd.DataFrame(
        [
            {
                "comp_id": 1,
                "comp_name": "IPL 2026",
                "team_id": 1,
                "team_name": "Alpha",
                "player_id": i,
                "player_name": name,
            }
            for i, name in enumerate(
                [
                    "Player One", "Player Two", "Player Three", "Player Four",
                    "Player Five", "Player Six", "Player Seven", "Player Eight", "Player Nine",
                ],
                start=1,
            )
        ]
    )

    competitions.to_csv(raw / "competitions.csv", index=False)
    matches.to_csv(raw / "matches.csv", index=False)
    teams.to_csv(raw / "teams.csv", index=False)
    playing_eleven.to_csv(raw / "playing_eleven.csv", index=False)
    ball_by_ball.to_csv(raw / "ball_by_ball.csv", index=False)
    mapping.to_csv(raw / "competition_team_player_mapping.csv", index=False)
    return raw


def test_pressure_flags_and_exclusions(tmp_path: Path):
    raw = _write_pack(tmp_path)
    df = P.prepare_deliveries(raw)

    assert set(df["match_id"].unique()) == {100, 101, 105}
    assert set(df["innings"].unique()) == {1, 2}

    # Condition A: overs 16-20 of a close chase.
    chase = df[(df["match_id"] == 100) & (df["innings"] == 2)]
    assert int(chase["pressure"].sum()) == 30
    assert chase[chase["overid"] >= 16]["pressure"].all()
    assert not chase[chase["overid"] < 16]["pressure"].any()
    first_innings = df[(df["match_id"] == 100) & (df["innings"] == 1)]
    assert not first_innings["pressure"].any()

    # Condition C: third wicket inside the first six overs.
    collapse = df[(df["match_id"] == 101) & (df["innings"] == 1)]
    wickets = collapse[collapse["is_wicket"]]
    assert not bool(wickets.iloc[1]["pressure"])
    assert bool(wickets.iloc[2]["pressure"])
    assert bool(collapse[(collapse["overid"] == 4)].iloc[0]["pressure"])
    assert not bool(collapse[(collapse["overid"] == 7)].iloc[0]["pressure"])

    # Condition B: required rate above 10 with fewer than five wickets in hand.
    steep = df[(df["match_id"] == 101) & (df["innings"] == 2)]
    assert not bool(steep[steep["overid"] == 8].iloc[0]["pressure"])
    assert bool(steep[steep["overid"] == 11].iloc[0]["pressure"])

    # Attribution fixture has only two wickets, so no pressure there.
    fixture = df[df["match_id"] == 105]
    assert not fixture["pressure"].any()


def test_recent_payload_attribution_and_index(tmp_path: Path):
    raw = _write_pack(tmp_path)
    derived = tmp_path / "derived"
    rankings = tmp_path / "rankings"
    rankings.mkdir()

    summary = P.run_precompute(raw, derived, rankings, data_end="2026-11-01", verbose=False)
    assert summary["players"] == 7

    index = json.loads((derived / "player_index.json").read_text(encoding="utf-8"))
    names = {row["name"] for row in index}
    assert names == {
        "Player 1", "Player Two", "Player Three", "Player 4",
        "Player 5", "Player Six", "Player Seven",
    }
    assert "Player Eight" not in names
    assert "Player Nine" not in names
    assert all(row["ranked_rank"] is None for row in index)

    player4 = next(row for row in index if row["name"] == "Player 4")
    recent4 = json.loads(
        (derived / "recent" / f"{player4['player_id']}.json").read_text(encoding="utf-8")
    )
    assert recent4["profile"]["matches"] == 3
    assert recent4["profile"]["role"] == "both"
    assert recent4["profile"]["latest_team"] == "Beta"
    assert recent4["profile"]["first_match_date"] == "2026-01-01"
    assert recent4["profile"]["last_match_date"] == "2026-01-05"
    assert len(recent4["matches"]) == 3
    assert [m["match_id"] for m in recent4["matches"]] == ["105", "101", "100"]

    fixture = next(m for m in recent4["matches"] if m["match_id"] == "105")
    batting = fixture["batting"]
    assert batting["runs"] == 11
    assert batting["balls"] == 11
    assert batting["strike_rate"] == 100.0
    assert batting["fours"] == 1
    assert batting["sixes"] == 1
    assert batting["boundary_pct"] == 18.2
    assert batting["dots"] == 8
    assert batting["dot_pct"] == 72.7
    assert batting["dismissed"] is True
    assert batting["dismissal"] == "Bowled"
    assert batting["pressure_balls"] == 0
    assert fixture["bowling"] is None
    assert fixture["opponent"] == "Alpha"
    assert fixture["format"] == "IPL"

    player5 = next(row for row in index if row["name"] == "Player 5")
    recent5 = json.loads(
        (derived / "recent" / f"{player5['player_id']}.json").read_text(encoding="utf-8")
    )
    fixture5 = next(m for m in recent5["matches"] if m["match_id"] == "105")
    bowling = fixture5["bowling"]
    assert bowling["legal_balls"] == 10
    assert bowling["runs"] == 14
    assert bowling["economy"] == 8.4
    assert bowling["wickets"] == 1
    assert bowling["dots"] == 7
    assert bowling["dot_pct"] == 70.0
    assert fixture5["batting"] is None

    player7 = next(row for row in index if row["name"] == "Player Seven")
    recent7 = json.loads(
        (derived / "recent" / f"{player7['player_id']}.json").read_text(encoding="utf-8")
    )
    assert recent7["profile"]["matches"] == 1
    assert recent7["profile"]["role"] == "unknown"
    assert recent7["matches"][0]["batting"] is None
    assert recent7["matches"][0]["bowling"] is None

    # No delivery-level keys may leak into the log.
    for match in recent4["matches"]:
        assert "innings_ball_num" not in match
        assert "striker_id" not in match

    # Windows and splits exist with small-sample flags.
    assert recent4["windows"]["career"]["batting"]["balls"] == 251
    assert recent4["windows"]["career"]["bowling"]["legal_balls"] == 240
    assert recent4["windows"]["last5"]["matches"] == 3
    assert set(recent4["phase"]["career"]) == {"powerplay", "middle", "death"}
    assert set(recent4["format_split"]["career"]) == {"IPL", "T20I"}
    assert recent4["windows"]["last5"]["batting"]["small_sample"] is False
