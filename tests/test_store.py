import json
from pathlib import Path

from backend.store import Store


def test_public_status_seed_restores_empty_database_without_overwriting_saved_changes(
    tmp_path: Path,
):
    seed_path = tmp_path / "backend" / "data" / "public_status_seed.json"
    seed_path.parent.mkdir(parents=True)
    seed_path.write_text(
        json.dumps(
            {
                "exported_at": "2026-11-17T00:00:00Z",
                "players": {
                    "Example Player": {
                        "status": "pool",
                        "current_team": "Rajasthan Royals",
                        "current_team_type": "ipl",
                        "note": "Public scouting note",
                        "rr_fit": "Top-order option",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    db_file = tmp_path / "backend" / "data" / "app.db"

    store = Store(root=tmp_path, db_file=db_file)

    assert store.status_map()["Example Player"] == {
        "status": "pool",
        "current_team": "Rajasthan Royals",
        "current_team_type": "ipl",
        "note": "Public scouting note",
        "rr_fit": "Top-order option",
    }

    store.update_status(name="Example Player", status="retained")
    restarted_store = Store(root=tmp_path, db_file=db_file)

    assert restarted_store.status_map()["Example Player"]["status"] == "retained"
