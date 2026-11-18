from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


def _db_status(client: TestClient) -> dict:
    db_file = client.app.state.store.db_file
    with sqlite3.connect(db_file) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT name, status, current_team, current_team_type, note, rr_fit FROM player_status"
        ).fetchall()
    return {
        row["name"]: {
            "status": row["status"],
            "current_team": row["current_team"],
            "current_team_type": row["current_team_type"],
            "note": row["note"],
            "rr_fit": row["rr_fit"],
        }
        for row in rows
    }


def _db_history_count(client: TestClient) -> int:
    db_file = client.app.state.store.db_file
    with sqlite3.connect(db_file) as connection:
        return connection.execute("SELECT COUNT(*) FROM status_history").fetchone()[0]


def _ranking_row(player_id: int, rank: int, name: str, player_type: str) -> dict:
    if player_type == "batter":
        team = ["Rajasthan Royals", "Mumbai Indians", "Delhi Capitals"][rank % 3]
        phase = ["Death", "Powerplay", "Middle"][rank % 3]
        role = ["Opener", "Finisher", "Middle order"][rank % 3]
        ipl_balls = rank * 20
        score = 2005.0 if rank == 4 else 2000.0 - rank * 10
    else:
        team = ["Rajasthan Royals", "Chennai Super Kings", "Mumbai Indians"][rank % 3]
        phase = ["Death", "Middle", "Powerplay"][rank % 3]
        role = ["Pace", "Spin", "Death specialist"][rank % 3]
        ipl_balls = rank * 15
        score = 2000.0 - rank * 10

    return {
        "player_type": player_type,
        "rank": rank,
        "player_id": player_id,
        "name": name,
        "score": score,
        "matches": 5 + rank * 3,
        "pressure_balls": 180,
        "IPL_balls": ipl_balls,
        "T20I_balls": 120,
        "impact100": 12.5,
        "wpa100": 3.2,
        "dots_pct": 42.0,
        "boundaries_pct": 18.0,
        "wickets_pct": 4.0,
        "economy": 8.2,
        "economy_above_expected": -0.4,
        "normal_impact": 10.0,
        "delta": 2.5,
        "consistency": 55.0,
        "pressure_matches": 20,
        "eb_weight": 0.7,
        "shrunk_performance": 11.0,
        "shrunk_wpa": 2.8,
        "shrunk_delta": 2.1,
        "dominant_phase": phase,
        "role": role,
        "IPL_PLAYED": "Y",
        "PLAYED_2026_IPL": "Y" if rank % 2 == 0 else "N",
        "IPL_PRESSURE_FLAG": "Y" if rank == 6 else "N",
        "latest_team": team,
        "latest_IPL_team": team,
        "form2026_balls": 100,
        "form2026_impact100": 13.0,
        "RECENT_FORM_FLAG": "Y" if rank == 5 else "N",
        "score_lo": score - 5,
        "score_hi": score + 5,
        "rank_lo": max(1, rank - 2),
        "rank_hi": rank + 3,
        "SAMPLE_FLAG": "Y" if rank == 7 else "N",
    }


@pytest.fixture()
def client(tmp_path: Path):
    rankings = tmp_path / "rankings"
    rankings.mkdir()
    batters = []
    for i in range(1, 26):
        name = "José Accent" if i == 3 else f"Batter {i:02d}"
        batters.append(_ranking_row(i, i, name, "batter"))
    bowlers = [_ranking_row(100 + i, i, f"Bowler {i:02d}", "bowler") for i in range(1, 26)]
    pd.DataFrame(batters).to_csv(rankings / "All_Batter_Rankings.csv", index=False)
    pd.DataFrame(bowlers).to_csv(rankings / "All_Bowler_Rankings.csv", index=False)

    derived = tmp_path / "derived"
    (derived / "recent").mkdir(parents=True)
    index = []
    for i in range(1, 26):
        index.append(
            {
                "player_id": i,
                "name": "José Accent" if i == 3 else f"Batter {i:02d}",
                "role": "batter",
                "latest_team": ["Rajasthan Royals", "Mumbai Indians", "Delhi Capitals"][i % 3],
                "last_match_date": "2026-05-01",
                "ranked_role": None,
                "ranked_rank": None,
            }
        )
    for i in range(1, 26):
        index.append(
            {
                "player_id": 100 + i,
                "name": f"Bowler {i:02d}",
                "role": "bowler",
                "latest_team": ["Rajasthan Royals", "Chennai Super Kings", "Mumbai Indians"][i % 3],
                "last_match_date": "2026-05-01",
                "ranked_role": None,
                "ranked_rank": None,
            }
        )
    (derived / "player_index.json").write_text(json.dumps(index), encoding="utf-8")
    recent_payload = {
        "profile": {
            "player_id": 4,
            "name": "Batter 04",
            "role": "batter",
            "latest_team": "Mumbai Indians",
            "first_match_date": "2022-04-01",
            "last_match_date": "2026-05-01",
            "matches": 60,
            "balls_faced": 900,
            "balls_bowled": 0,
        },
        "matches": [],
        "windows": {},
        "phase": {},
        "format_split": {},
        "notes": {},
    }
    (derived / "recent" / "4.json").write_text(json.dumps(recent_payload), encoding="utf-8")
    (derived / "meta.json").write_text(
        json.dumps({"generated_at": "2026-11-16T00:00:00Z", "players": 50}), encoding="utf-8"
    )

    status = tmp_path / "status.json"
    status.write_text(
        json.dumps(
            {
                "Batter 01": {"status": "retained", "note": "", "rr_fit": ""},
                "Batter 02": {"status": "no_ipl", "note": "", "rr_fit": ""},
                "José Accent": {"status": "pool", "note": "", "rr_fit": "Death-overs enforcer"},
                "Bowler 02": {"status": "retained", "note": "", "rr_fit": ""},
            }
        ),
        encoding="utf-8",
    )

    app = create_app(
        root=tmp_path,
        rankings_dir=rankings,
        derived_dir=derived,
        status_file=status,
    )
    with TestClient(app) as test_client:
        test_client.tmp_path = tmp_path
        login = test_client.post(
            "/api/auth/login",
            json={"password": os.getenv("APP_PASSWORD", "royals2027")},
        )
        assert login.status_code == 200
        yield test_client


def test_health_and_summary(client: TestClient):
    health = client.get("/api/health").json()
    assert health["ready"] is True
    assert health["rankings_loaded"] is True
    assert health["player_index"] is True
    assert health["recent_files"] == 1

    summary = client.get("/api/summary").json()
    assert summary["ready"] is True
    assert summary["qualifying_batters"] == 25
    assert summary["qualifying_bowlers"] == 25
    assert summary["available_pool"] == 47
    assert summary["top5"]["batter"][0]["name"] == "Batter 04"
    assert summary["top5"]["batter"][0]["clean_rank"] == 1
    assert summary["top5"]["bowler"][0]["name"] == "Bowler 01"
    assert summary["last_updated"] == "2026-11-16T00:00:00Z"


def test_rating_out_of_100_and_min_matches(client: TestClient):
    payload = client.get("/api/players", params={"role": "batter"}).json()
    assert payload["rating_meta"]["scale"] == 100
    ratings = [row["rating100"] for row in payload["players"]]
    assert all(isinstance(rating, (int, float)) for rating in ratings)
    assert ratings == sorted(ratings, reverse=True)
    assert ratings[0] == 100.0
    first = payload["players"][0]
    assert 0 <= first["rating100"] <= 100
    assert first["matches"] >= 1
    assert first["experience_marks"] >= 1
    assert first["sample_marks"] is not None

    filtered = client.get(
        "/api/players", params={"role": "batter", "min_matches": 20}
    ).json()
    assert filtered["count"] < payload["count"]
    assert all(row["matches"] >= 20 for row in filtered["players"])

    summary = client.get("/api/summary").json()
    assert summary["rating_meta"]["scale"] == 100


def test_players_include_last_match_date_from_all_match_data(client: TestClient):
    index_path = client.tmp_path / "derived" / "player_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    for entry in index:
        if entry["player_id"] == 1:
            entry["last_match_date"] = "2025-12-30"
        elif entry["player_id"] == 101:
            entry["last_match_date"] = "2026-10-12"
    index_path.write_text(json.dumps(index), encoding="utf-8")

    batters = client.get(
        "/api/players",
        params={"role": "batter", "available_only": "false"},
    ).json()["players"]
    bowlers = client.get(
        "/api/players",
        params={"role": "bowler", "available_only": "false"},
    ).json()["players"]
    batter_by_name = {row["name"]: row for row in batters}
    bowler_by_name = {row["name"]: row for row in bowlers}

    assert batter_by_name["Batter 01"]["last_match_date"] == "2025-12-30"
    assert bowler_by_name["Bowler 01"]["last_match_date"] == "2026-10-12"


def test_players_clean_rank_and_filters(client: TestClient):
    payload = client.get("/api/players", params={"role": "batter"}).json()
    assert payload["ready"] is True
    assert payload["count"] == 23
    names = [row["name"] for row in payload["players"]]
    assert "Batter 01" not in names and "Batter 02" not in names

    first = payload["players"][0]
    assert first["name"] == "Batter 04"
    assert first["clean_rank"] == 1
    assert first["raw_rank"] == 4
    assert first["rank"] == 4
    assert first["rank_interval"] == "2-7"
    assert first["available"] is True
    assert first["status"] == "unknown"

    second = payload["players"][1]
    assert second["name"] == "José Accent"
    assert second["clean_rank"] == 2
    assert second["status"] == "pool"
    assert second["rr_fit"] == "Death-overs enforcer"

    raw = client.get(
        "/api/players", params={"role": "batter", "available_only": "false"}
    ).json()
    assert raw["count"] == 25
    assert raw["players"][0]["name"] == "Batter 01"
    assert all(row["clean_rank"] == row["rank"] for row in raw["players"])

    team = client.get(
        "/api/players", params={"role": "batter", "team": "Rajasthan Royals"}
    ).json()
    assert team["count"] == 8
    assert all(row["team_label"] == "Rajasthan Royals" for row in team["players"])

    phase = client.get(
        "/api/players", params={"role": "batter", "phase": "death"}
    ).json()
    assert phase["count"] == 8
    assert all(row["dominant_phase"] == "Death" for row in phase["players"])

    balls = client.get(
        "/api/players", params={"role": "batter", "min_ipl_balls": 300}
    ).json()
    assert balls["count"] == 11
    assert all(row["IPL_balls"] >= 300 for row in balls["players"])

    bad = client.get("/api/players", params={"role": "keeper"})
    assert bad.status_code == 400


def test_shortlist_and_player_endpoints(client: TestClient):
    shortlist = client.get("/api/shortlist", params={"role": "batter"}).json()
    assert shortlist["ready"] is True
    assert len(shortlist["shortlist"]) == 10
    assert len(shortlist["reserves"]) == 10
    assert [row["clean_rank"] for row in shortlist["shortlist"]] == list(range(1, 11))
    assert [row["clean_rank"] for row in shortlist["reserves"]] == list(range(11, 21))
    assert shortlist["shortlist"][0]["name"] == "Batter 04"

    player = client.get("/api/player/batter/4").json()
    assert player["ready"] is True
    assert player["player"]["name"] == "Batter 04"
    assert player["player"]["clean_rank"] == 1
    assert player["modules"] == []

    assert client.get("/api/player/bowler/4").status_code == 404
    assert client.get("/api/player/batter/999").status_code == 404
    assert client.get("/api/shortlist", params={"role": "keeper"}).status_code == 400


def test_status_update_and_availability(client: TestClient):
    status = client.get("/api/status").json()
    assert "retained" in status["allowed_statuses"]
    assert status["players"]["José Accent"]["status"] == "pool"

    updated = client.put(
        "/api/status",
        json={
            "name": "Batter 04",
            "status": "retained",
            "rr_fit": "Too expensive for the plan",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["players"]["Batter 04"]["status"] == "retained"

    persisted = _db_status(client)
    assert persisted["Batter 04"]["rr_fit"] == "Too expensive for the plan"

    payload = client.get("/api/players", params={"role": "batter"}).json()
    assert payload["players"][0]["name"] == "José Accent"
    assert payload["players"][0]["clean_rank"] == 1
    assert "Batter 04" not in [row["name"] for row in payload["players"]]

    player = client.get("/api/player/batter/4").json()
    assert player["player"]["status"] == "retained"
    assert player["player"]["clean_rank"] is None

    assert (
        client.put("/api/status", json={"name": "Batter 04", "status": "available"}).status_code
        == 400
    )
    assert client.put("/api/status", json={"name": "Batter 04"}).status_code == 400
    assert client.put("/api/status", json={"name": "", "status": "pool"}).status_code == 422


def test_search_is_accent_insensitive_and_ranked(client: TestClient):
    for query in ("jose", "JOSÉ", "accent"):
        payload = client.get("/api/search", params={"q": query}).json()
        assert payload["ready"] is True
        assert payload["results"][0]["name"] == "José Accent"
        assert payload["results"][0]["ranked"] is True
        assert payload["results"][0]["ranked_rank"] == 3
        assert payload["results"][0]["latest_team"] == "Rajasthan Royals"

    exact = client.get("/api/search", params={"q": "batter 04"}).json()
    assert exact["results"][0]["name"] == "Batter 04"
    assert exact["results"][0]["ranked_rank"] == 4

    none = client.get("/api/search", params={"q": "zzzz"}).json()
    assert none["results"] == []


def test_recent_includes_ranking_and_status(client: TestClient):
    payload = client.get("/api/recent/4").json()
    assert payload["ranked"] is True
    assert payload["ranking"]["name"] == "Batter 04"
    assert payload["player"]["profile"]["name"] == "Batter 04"
    assert payload["status"] == "unknown"

    client.put(
        "/api/status",
        json={"name": "Batter 04", "status": "pool", "rr_fit": "Top-order option"},
    )
    payload = client.get("/api/recent/4").json()
    assert payload["status"] == "pool"
    assert payload["rr_fit"] == "Top-order option"

    assert client.get("/api/recent/999").status_code == 404


def test_missing_rankings_does_not_break_search(tmp_path: Path):
    rankings = tmp_path / "empty_rankings"
    rankings.mkdir()
    derived = tmp_path / "derived"
    (derived / "recent").mkdir(parents=True)
    (derived / "player_index.json").write_text(
        json.dumps(
            [
                {
                    "player_id": 3,
                    "name": "José Accent",
                    "role": "batter",
                    "latest_team": "Rajasthan Royals",
                    "last_match_date": "2026-05-01",
                    "ranked_role": None,
                    "ranked_rank": None,
                }
            ]
        ),
        encoding="utf-8",
    )
    (derived / "recent" / "3.json").write_text(
        json.dumps({"profile": {"name": "José Accent"}, "matches": []}), encoding="utf-8"
    )
    status = tmp_path / "status.json"
    status.write_text("{}", encoding="utf-8")

    app = create_app(
        root=tmp_path,
        rankings_dir=rankings,
        derived_dir=derived,
        status_file=status,
    )
    with TestClient(app) as client:
        summary = client.get("/api/summary").json()
        assert summary["ready"] is False
        assert summary["qualifying_batters"] == 0

        players = client.get("/api/players", params={"role": "batter"}).json()
        assert players["ready"] is False
        assert players["players"] == []

        search = client.get("/api/search", params={"q": "jose"}).json()
        assert search["ready"] is True
        assert search["results"][0]["ranked"] is False

        recent = client.get("/api/recent/3").json()
        assert recent["ranked"] is False
        assert recent["ranking"] is None


def test_suggestion_rules_cover_all_teams():
    from backend.store import (
        IPL_TEAMS,
        NO_TEAM,
        RELEASED_TEAM,
        suggest_status_for_team,
    )

    assert suggest_status_for_team("Rajasthan Royals") == "rr_own"
    for team in IPL_TEAMS:
        if team != "Rajasthan Royals":
            assert suggest_status_for_team(team) == "retained"
    assert suggest_status_for_team(RELEASED_TEAM) == "pool"
    assert suggest_status_for_team(NO_TEAM) == "no_ipl"
    assert suggest_status_for_team("Surrey") is None
    assert suggest_status_for_team(None) is None


def test_current_team_validation_and_suggestion(client: TestClient):
    response = client.put(
        "/api/status/Batter%2005", json={"current_team": "Mumbai Indians"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["players"]["Batter 05"]["current_team"] == "Mumbai Indians"
    assert payload["players"]["Batter 05"]["current_team_type"] == "ipl"
    assert payload["players"]["Batter 05"]["status"] == "retained"
    assert payload["suggestion"]["status"] == "retained"
    assert "Mumbai Indians" in payload["current_team_options"]["ipl_teams"]

    rr = client.put(
        "/api/status/Batter%2005", json={"current_team": "Rajasthan Royals"}
    ).json()
    assert rr["suggestion"]["status"] == "rr_own"
    assert rr["players"]["Batter 05"]["current_team_type"] == "ipl"
    assert rr["players"]["Batter 05"]["status"] == "rr_own"

    released = client.put(
        "/api/status/Batter%2005",
        json={"current_team": "Released / in auction pool"},
    ).json()
    assert released["suggestion"]["status"] == "pool"
    assert released["players"]["Batter 05"]["current_team_type"] is None
    assert released["players"]["Batter 05"]["status"] == "pool"

    no_team = client.put(
        "/api/status/Batter%2005",
        json={"current_team": "No team / not playing IPL"},
    ).json()
    assert no_team["suggestion"]["status"] == "no_ipl"
    assert no_team["players"]["Batter 05"]["status"] == "no_ipl"

    other = client.put(
        "/api/status/Batter%2005",
        json={"current_team": "Surrey", "current_team_type": "other"},
    ).json()
    assert other["suggestion"] is None
    assert other["players"]["Batter 05"]["current_team_type"] == "other"
    assert other["players"]["Batter 05"]["status"] == "no_ipl"
    assert "Surrey" in other["typed_teams"]

    invalid_type = client.put(
        "/api/status/Batter%2005",
        json={"current_team": "Mumbai Indians", "current_team_type": "other"},
    )
    assert invalid_type.status_code == 400
    missing_type = client.put(
        "/api/status/Batter%2005", json={"current_team_type": "ipl"}
    )
    assert missing_type.status_code == 400
    empty_team = client.put(
        "/api/status/Batter%2005", json={"current_team": "   "}
    )
    assert empty_team.status_code == 400
    bad_status = client.put(
        "/api/status/Batter%2005",
        json={"current_team": "Mumbai Indians", "status": "available"},
    )
    assert bad_status.status_code == 400

    cleared = client.put(
        "/api/status/Batter%2005", json={"current_team": None}
    ).json()
    assert cleared["players"]["Batter 05"]["current_team"] is None
    assert cleared["players"]["Batter 05"]["current_team_type"] is None


def test_setting_no_ipl_moves_player_out_of_retained_team(client: TestClient):
    client.put(
        "/api/status/Batter%2005",
        json={"current_team": "Mumbai Indians"},
    )

    single = client.put(
        "/api/status/Batter%2005",
        json={"status": "no_ipl"},
    )
    assert single.status_code == 200
    player = single.json()["players"]["Batter 05"]
    assert player["status"] == "no_ipl"
    assert player["current_team"] == "No team / not playing IPL"
    assert player["current_team_type"] is None

    client.put(
        "/api/status/Batter%2006",
        json={"current_team": "Delhi Capitals"},
    )
    bulk = client.put(
        "/api/status/bulk",
        json={"names": ["Batter 06"], "status": "no_ipl"},
    )
    assert bulk.status_code == 200
    player = client.get("/api/status").json()["players"]["Batter 06"]
    assert player["status"] == "no_ipl"
    assert player["current_team"] == "No team / not playing IPL"
    assert player["current_team_type"] is None


def test_team_filter_uses_current_team_with_data_fallback(client: TestClient):
    client.put(
        "/api/status",
        json={"name": "Batter 05", "current_team": "Mumbai Indians"},
    )

    players = client.get(
        "/api/players",
        params={"role": "batter", "available_only": "false"},
    ).json()["players"]
    by_name = {row["name"]: row for row in players}
    assert by_name["Batter 05"]["team_label"] == "Delhi Capitals"
    assert by_name["Batter 05"]["current_team"] == "Mumbai Indians"
    assert by_name["Batter 05"]["effective_team"] == "Mumbai Indians"
    assert by_name["Batter 05"]["team_source"] == "manual"
    assert by_name["Batter 06"]["team_label"] == "Rajasthan Royals"
    assert by_name["Batter 06"]["current_team"] is None
    assert by_name["Batter 06"]["effective_team"] == "Rajasthan Royals"
    assert by_name["Batter 06"]["team_source"] == "data"

    mumbai = client.get(
        "/api/players",
        params={"role": "batter", "available_only": "false", "team": "Mumbai Indians"},
    ).json()["players"]
    assert "Batter 05" in [row["name"] for row in mumbai]
    delhi = client.get(
        "/api/players",
        params={"role": "batter", "available_only": "false", "team": "Delhi Capitals"},
    ).json()["players"]
    assert "Batter 05" not in [row["name"] for row in delhi]
    rajasthan = client.get(
        "/api/players",
        params={"role": "batter", "available_only": "false", "team": "Rajasthan Royals"},
    ).json()["players"]
    assert "Batter 06" in [row["name"] for row in rajasthan]

    unset = client.get(
        "/api/players",
        params={
            "role": "batter",
            "available_only": "false",
            "current_team_unset": "true",
        },
    ).json()["players"]
    names = [row["name"] for row in unset]
    assert "Batter 05" not in names
    assert "Batter 06" in names


def test_bulk_edit_changes_only_different_rows(client: TestClient):
    response = client.put(
        "/api/status/bulk",
        json={
            "names": ["Batter 06", "Batter 07", "Batter 06"],
            "current_team": "Royal Challengers Bengaluru",
            "status": "retained",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["requested"] == 2
    assert payload["changed"] == 2
    assert payload["unchanged"] == 0
    assert payload["suggestion"]["status"] == "retained"

    persisted = _db_status(client)
    for name in ("Batter 06", "Batter 07"):
        assert persisted[name]["status"] == "retained"
        assert persisted[name]["current_team"] == "Royal Challengers Bengaluru"
        assert persisted[name]["current_team_type"] == "ipl"

    repeat = client.put(
        "/api/status/bulk",
        json={
            "names": ["Batter 06", "Batter 07"],
            "current_team": "Royal Challengers Bengaluru",
            "status": "retained",
        },
    ).json()
    assert repeat["changed"] == 0
    assert repeat["unchanged"] == 2

    empty = client.put("/api/status/bulk", json={"names": ["  "], "status": "pool"})
    assert empty.status_code == 400
    missing = client.put("/api/status/bulk", json={"names": ["Batter 06"]})
    assert missing.status_code == 400


def test_history_and_undo(client: TestClient):
    client.put("/api/status", json={"name": "Batter 04", "note": "first"})
    client.put(
        "/api/status",
        json={"name": "Batter 04", "current_team": "Mumbai Indians"},
    )
    history = client.get("/api/status/history/Batter%2004").json()
    assert history["player"] == "Batter 04"
    assert len(history["entries"]) == 2
    assert len(history["last"]) == 2
    last = history["entries"][-1]
    fields = {change["field"] for change in last["changes"]}
    assert fields == {"current_team", "current_team_type", "status"}
    assert _db_history_count(client) >= 2

    undo = client.post("/api/status/undo/Batter%2004")
    assert undo.status_code == 200
    payload = undo.json()
    assert payload["players"]["Batter 04"]["current_team"] is None
    assert payload["undone"]["changes"][0]["field"] == "current_team"
    assert len(client.get("/api/status/history/Batter%2004").json()["entries"]) == 1

    status = _db_status(client)
    assert status["Batter 04"]["note"] == "first"
    assert status["Batter 04"]["current_team"] is None

    again = client.post("/api/status/undo/Batter%2004")
    assert again.status_code == 200
    assert again.json()["players"]["Batter 04"]["note"] == ""
    assert client.post("/api/status/undo/Batter%2004").status_code == 400


def test_bulk_undo_reverts_selected_players_and_skips_missing_history(client: TestClient):
    client.put("/api/status", json={"name": "Batter 04", "note": "before"})
    client.put(
        "/api/status",
        json={
            "name": "Batter 04",
            "current_team": "Mumbai Indians",
            "note": "after",
        },
    )
    client.put("/api/status", json={"name": "Batter 05", "status": "pool"})

    response = client.post(
        "/api/status/undo-bulk",
        json={"names": ["Batter 04", "Batter 05", "Batter 06"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert set(payload["undone"]) == {"Batter 04", "Batter 05"}
    assert payload["skipped"] == ["Batter 06"]
    assert payload["players"]["Batter 04"]["note"] == "before"
    assert payload["players"]["Batter 04"]["current_team"] is None
    assert payload["players"]["Batter 04"]["status"] == "unknown"
    assert payload["players"]["Batter 05"]["status"] == "unknown"
    assert len(client.get("/api/status/history/Batter%2004").json()["entries"]) == 1
    assert client.get("/api/status/history/Batter%2005").json()["entries"] == []

    no_history = client.post(
        "/api/status/undo-bulk", json={"names": ["Batter 06"]}
    )
    assert no_history.status_code == 400


def test_edit_persists_across_app_restart(client: TestClient):
    client.put(
        "/api/status",
        json={"name": "Batter 11", "status": "pool", "note": "survives restart"},
    )
    tmp_path = client.tmp_path
    restarted = create_app(
        root=tmp_path,
        rankings_dir=tmp_path / "rankings",
        derived_dir=tmp_path / "derived",
    )
    with TestClient(restarted) as second:
        payload = second.get("/api/status").json()
        assert payload["players"]["Batter 11"]["status"] == "pool"
        assert payload["players"]["Batter 11"]["note"] == "survives restart"


def test_import_dry_run_then_merge_and_export(client: TestClient):
    import_payload = {
        "players": {
            "Batter 08": {
                "status": "pool",
                "current_team": "Chennai Super Kings",
                "current_team_type": "ipl",
                "note": "",
                "rr_fit": "",
            },
            "Batter 09": {
                "status": "no_ipl",
                "current_team": None,
                "current_team_type": None,
                "note": "imported",
                "rr_fit": "",
            },
        }
    }
    before = _db_status(client)
    preview = client.post(
        "/api/status/import", params={"dry_run": "true"}, json=import_payload
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["dry_run"] is True
    assert preview_payload["changed"] == 2
    assert _db_status(client) == before

    applied = client.post("/api/status/import", json=import_payload)
    assert applied.status_code == 200
    applied_payload = applied.json()
    assert applied_payload["dry_run"] is True
    assert applied_payload["changed"] == 2

    applied = client.post(
        "/api/status/import",
        json={**import_payload, "dry_run": False},
    ).json()
    assert applied["dry_run"] is False
    assert applied["changed"] == 2
    persisted = _db_status(client)
    assert persisted["Batter 08"]["current_team"] == "Chennai Super Kings"
    assert persisted["Batter 09"]["status"] == "no_ipl"
    assert len(client.get("/api/status/history/Batter%2008").json()["entries"]) == 1

    repeat = client.post(
        "/api/status/import",
        json={**import_payload, "dry_run": True},
    ).json()
    assert repeat["changed"] == 0

    json_export = client.get("/api/status/export")
    assert json_export.status_code == 200
    assert json_export.headers["content-disposition"].startswith("attachment;")
    exported = json_export.json()
    assert exported["players"]["Batter 08"]["current_team"] == "Chennai Super Kings"
    assert exported["roles"]["Batter 08"] == "batter"

    csv_export = client.get("/api/status/export", params={"format": "csv"})
    assert csv_export.status_code == 200
    assert csv_export.text.lstrip("\ufeff").splitlines()[0] == (
        "player,role,status,current_team,current_team_type,note,rr_fit"
    )
    assert "Batter 08,batter,pool,Chennai Super Kings,ipl" in csv_export.text

    csv_import = client.post(
        "/api/status/import",
        params={"dry_run": "true"},
        json={
            "csv": (
                "player,role,status,current_team,current_team_type,note,rr_fit\n"
                "Batter 10,batter,unknown,Mumbai Indians,ipl,,\n"
            )
        },
    )
    assert csv_import.status_code == 200
    assert csv_import.json()["changed"] == 1

    invalid = client.post(
        "/api/status/import",
        params={"dry_run": "true"},
        json={"players": {"Batter 11": {"status": "available"}}},
    )
    assert invalid.status_code == 400
    assert "Batter 11" in invalid.json()["detail"]


def test_recent_exposes_current_team(client: TestClient):
    client.put(
        "/api/status",
        json={
            "name": "Batter 04",
            "current_team": "Rajasthan Royals",
            "current_team_type": "ipl",
        },
    )
    payload = client.get("/api/recent/4").json()
    assert payload["current_team"] == "Rajasthan Royals"
    assert payload["current_team_type"] == "ipl"
    assert payload["team_source"] == "manual"
    assert payload["effective_team"] == "Rajasthan Royals"
    assert payload["ranking"]["current_team"] == "Rajasthan Royals"



def test_auth_required_for_edits_and_downloads(client: TestClient):
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json()["authenticated"] is False
    public_players = client.get("/api/players?role=batter&available_only=false")
    assert public_players.status_code == 200
    assert len(public_players.json()["players"]) == 25
    public_status = client.get("/api/status")
    assert public_status.status_code == 200
    assert public_status.json()["players"]
    assert (
        client.put("/api/status", json={"name": "Batter 01", "note": "x"}).status_code
        == 401
    )
    assert (
        client.put(
            "/api/status/bulk",
            json={"names": ["Batter 01"], "status": "pool"},
        ).status_code
        == 401
    )
    assert client.get("/api/status/export").status_code == 401
    assert client.post("/api/status/undo/Batter%2001").status_code == 401
    assert client.post(
        "/api/status/undo-bulk", json={"names": ["Batter 01"]}
    ).status_code == 401
    wrong = client.post("/api/auth/login", json={"password": "definitely-wrong"})
    assert wrong.status_code == 401
    ok = client.post(
        "/api/auth/login",
        json={"password": os.getenv("APP_PASSWORD", "royals2027")},
    )
    assert ok.status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is True
    assert client.get("/api/status/export").status_code == 200


def test_team_xi_editor_roundtrip(client: TestClient):
    batters = client.get("/api/players", params={"role": "batter"}).json()["players"][:6]
    bowlers = client.get("/api/players", params={"role": "bowler"}).json()["players"][:6]
    names = [row["name"] for row in batters + bowlers]
    bulk = client.put(
        "/api/status/bulk",
        json={"names": names, "current_team": "Rajasthan Royals"},
    )
    assert bulk.status_code == 200
    # A retained player at another franchise must never appear as a best fit.
    client.put(
        "/api/status",
        json={"name": "Bowler 07", "current_team": "Mumbai Indians"},
    )

    detail = client.get("/api/teams/rajasthan-royals").json()
    xi = [row["name"] for row in detail["xi"]]
    assert len(xi) == 11
    assert detail["xi_source"] == "auto"
    assert detail["fit_options"]
    assert detail["pool_fit"]

    sources = {
        option["source"]
        for slot in detail["fit_options"].values()
        for option in slot["players"]
    }
    assert sources <= {"squad", "pool"}
    pool_rows = [row for role in detail["pool_fit"].values() for row in role]
    assert pool_rows
    assert all(row["current_team"] is None for row in pool_rows)
    assert all(row["status"] in {"pool", "unknown"} for row in pool_rows)
    assert "Bowler 07" not in {row["name"] for row in pool_rows}

    reordered = list(reversed(xi))
    saved = client.put(
        "/api/teams/rajasthan-royals/xi",
        json={"players": reordered},
    )
    assert saved.status_code == 200
    saved_body = saved.json()
    assert saved_body["xi_source"] == "custom"
    assert [row["name"] for row in saved_body["xi"]] == reordered
    assert saved_body["xi_updated_at"]

    same_order = client.put(
        "/api/teams/rajasthan-royals/xi",
        json={"players": reordered[:5]},
    )
    assert same_order.status_code == 422
    unknown = client.put(
        "/api/teams/rajasthan-royals/xi",
        json={"players": reordered[:10] + ["Not A Player"]},
    )
    assert unknown.status_code == 400

    reset = client.delete("/api/teams/rajasthan-royals/xi")
    assert reset.status_code == 200
    assert reset.json()["xi_source"] == "auto"

    client.post("/api/auth/logout")
    assert (
        client.put(
            "/api/teams/rajasthan-royals/xi",
            json={"players": reordered},
        ).status_code
        == 401
    )
    assert client.delete("/api/teams/rajasthan-royals/xi").status_code == 401
