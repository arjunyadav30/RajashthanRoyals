import json
from pathlib import Path

from backend.store import Store, _ConnectionAdapter


def test_postgres_connection_adapter_uses_psycopg_placeholders():
    class RecordingCursor:
        def __init__(self, calls):
            self.calls = calls

        def execute(self, query, parameters):
            self.calls.append(("execute", query, parameters))

        def executemany(self, query, parameters):
            self.calls.append(("executemany", query, parameters))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    class RecordingConnection:
        def __init__(self):
            self.calls = []

        def execute(self, query, parameters):
            self.calls.append(("execute", query, parameters))

        def cursor(self):
            return RecordingCursor(self.calls)

    raw_connection = RecordingConnection()
    connection = _ConnectionAdapter(raw_connection, postgres=True)

    connection.execute("SELECT * FROM player_status WHERE name = ?", ("Player",))
    connection.executemany(
        "INSERT INTO player_status(name) VALUES (?)",
        [("Player 1",), ("Player 2",)],
    )

    assert raw_connection.calls == [
        ("execute", "SELECT * FROM player_status WHERE name = %s", ("Player",)),
        (
            "executemany",
            "INSERT INTO player_status(name) VALUES (%s)",
            [("Player 1",), ("Player 2",)],
        ),
    ]


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
