from __future__ import annotations

import csv
import json
from pathlib import Path

from backend.store import Store


def _master_row(
    *,
    player_id: int,
    name: str,
    batter_rank: int | None = None,
    batter_score: float | None = None,
    batter_qualification: str = "",
    batter_qualified_rank: int | None = None,
    bowler_rank: int | None = None,
    bowler_score: float | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "player_id": player_id,
        "name": name,
        "data_scope": "IPL 2022-2026 + T20I competitions in supplied pack",
        "analysis_version": "Rebuilt from raw ball-by-ball",
        "player_role": "All-rounder",
        "latest_team": "India",
        "latest_ipl_team": "Rajasthan Royals",
        "played_ipl_2022_2026": "Yes",
        "batter_rank_all": batter_rank or "",
        "batter_rank_qualified": batter_qualified_rank or "",
        "batter_qualification_status": batter_qualification,
        "batter_score_100": batter_score or "",
        "batter_data_confidence_100": 90 if batter_score is not None else "",
        "batter_matches": 20 if batter_score is not None else "",
        "batter_pressure_matches": 8 if batter_score is not None else "",
        "batter_balls_faced": 400 if batter_score is not None else "",
        "batter_pressure_balls": 100 if batter_score is not None else "",
        "batter_runs": 500 if batter_score is not None else "",
        "batter_innings": 20 if batter_score is not None else "",
        "batter_average": 25 if batter_score is not None else "",
        "batter_strike_rate": 125 if batter_score is not None else "",
        "batter_dominant_phase": "death" if batter_score is not None else "",
        "batter_experience_marks_7": 3 if batter_score is not None else "",
        "batter_sample_size_marks_6": 4 if batter_score is not None else "",
        "bowler_rank_all": bowler_rank or "",
        "bowler_rank_qualified": "",
        "bowler_qualification_status": "QUALIFIED" if bowler_score is not None else "",
        "bowler_score_100": bowler_score or "",
        "bowler_data_confidence_100": 80 if bowler_score is not None else "",
        "bowler_matches": 18 if bowler_score is not None else "",
        "bowler_pressure_matches": 6 if bowler_score is not None else "",
        "bowler_legal_balls": 300 if bowler_score is not None else "",
        "bowler_pressure_legal_balls": 70 if bowler_score is not None else "",
        "bowler_runs_conceded": 400 if bowler_score is not None else "",
        "bowler_innings": 18 if bowler_score is not None else "",
        "bowler_wickets": 22 if bowler_score is not None else "",
        "bowler_economy": 8 if bowler_score is not None else "",
        "bowler_dominant_phase": "powerplay" if bowler_score is not None else "",
        "bowler_experience_marks_7": 3 if bowler_score is not None else "",
        "bowler_sample_size_marks_6": 4 if bowler_score is not None else "",
    }
    return row


def test_master_csv_drives_role_ranks_and_scores(tmp_path: Path):
    source_dir = tmp_path / "data_rankings"
    source_dir.mkdir()
    rows = [
        _master_row(
            player_id=7,
            name="Second Batter",
            batter_rank=2,
            batter_score=74.25,
            batter_qualification="LOW SAMPLE",
        ),
        _master_row(
            player_id=8,
            name="Top Batter",
            batter_rank=1,
            batter_score=91.5,
            batter_qualification="QUALIFIED",
            batter_qualified_rank=1,
            bowler_rank=1,
            bowler_score=83.75,
        ),
    ]
    with (source_dir / "RR_2027_All_838_Players_Master.csv").open(
        "w", encoding="utf-8", newline=""
    ) as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    store = Store(root=tmp_path)

    batters = store.players(role="batter", available_only=False)["players"]
    assert [row["name"] for row in batters] == ["Top Batter", "Second Batter"]
    assert batters[0]["rank"] == batters[0]["all_rank"] == 1
    assert batters[0]["score"] == batters[0]["rating100"] == 91.5
    assert batters[0]["qualified_rank"] == 1
    assert batters[1]["qualification_status"] == "BELOW_MIN"
    assert batters[1]["source_qualification_status"] == "LOW SAMPLE"

    bowlers = store.players(role="bowler", available_only=False)["players"]
    assert len(bowlers) == 1
    assert bowlers[0]["name"] == "Top Batter"
    assert bowlers[0]["score"] == bowlers[0]["rating100"] == 83.75

    stats_dir = tmp_path / "data_derived" / "stats"
    stats_dir.mkdir(parents=True)
    (stats_dir / "index.json").write_text(
        json.dumps(
            {
                "players": [
                    {
                        "player_id": 8,
                        "name": "Top Batter",
                        "role": "both",
                        "ranked_role": "bowler",
                        "ranked_rank": 99,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    stats_row = store.stats_index()["rows"][0]
    assert stats_row["ranked_role"] == "batter"
    assert stats_row["ranked_rank"] == 1
