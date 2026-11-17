"""Data access, availability status and clean-ranking logic."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import sqlite3
import threading
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .textnorm import compact_name, normalise_name

ALLOWED_STATUSES = ("retained", "rr_own", "no_ipl", "pool", "unknown")
AVAILABLE_STATUSES = frozenset({"pool", "unknown"})

IPL_TEAMS = (
    "Chennai Super Kings",
    "Delhi Capitals",
    "Gujarat Titans",
    "Kolkata Knight Riders",
    "Lucknow Super Giants",
    "Mumbai Indians",
    "Punjab Kings",
    "Rajasthan Royals",
    "Royal Challengers Bengaluru",
    "Sunrisers Hyderabad",
)
RELEASED_TEAM = "Released / in auction pool"
NO_TEAM = "No team / not playing IPL"
SPECIAL_CURRENT_TEAMS = (RELEASED_TEAM, NO_TEAM)
CURRENT_TEAM_TYPES = ("ipl", "other")
MAX_TEAM_LENGTH = 80
STATUS_FIELDS = ("status", "current_team", "current_team_type", "note", "rr_fit")
DEFAULT_ENTRY = {
    "status": "unknown",
    "current_team": None,
    "current_team_type": None,
    "note": "",
    "rr_fit": "",
}

_UNSET = object()


class _ConnectionAdapter:
    def __init__(self, connection, postgres: bool):
        self.connection = connection
        self.postgres = postgres

    def execute(self, query: str, parameters=()):
        if self.postgres:
            query = query.replace("?", "%s")
        return self.connection.execute(query, parameters)

    def executemany(self, query: str, parameters):
        if self.postgres:
            query = query.replace("?", "%s")
            with self.connection.cursor() as cursor:
                cursor.executemany(query, parameters)
            return
        return self.connection.executemany(query, parameters)


def suggest_status_for_team(team: str | None) -> str | None:
    """Return the one-click status suggestion for a chosen team, never apply it."""
    if not team:
        return None
    if team == "Rajasthan Royals":
        return "rr_own"
    if team in IPL_TEAMS:
        return "retained"
    if team == RELEASED_TEAM:
        return "pool"
    if team == NO_TEAM:
        return "no_ipl"
    return None


def status_suggestion(team: str | None) -> dict | None:
    suggested = suggest_status_for_team(team)
    if not suggested:
        return None
    return {
        "current_team": team,
        "status": suggested,
        "prompt": f"Set status to {suggested}?",
    }


def _default_entry(status: str = "unknown") -> dict:
    entry = dict(DEFAULT_ENTRY)
    entry["status"] = status
    return entry


def _validate_team(team, team_type):
    """Validate current_team/current_team_type and infer the type when omitted."""
    if team is None:
        if team_type is not None:
            raise ValueError("current_team_type must be null when current_team is null")
        return None, None
    if not isinstance(team, str):
        raise ValueError("current_team must be a string or null")
    team = team.strip()
    if not team:
        raise ValueError("current_team cannot be empty; use null to clear it")
    if len(team) > MAX_TEAM_LENGTH:
        raise ValueError(f"current_team must be at most {MAX_TEAM_LENGTH} characters")
    if team_type is not None:
        team_type = str(team_type).strip().lower()
        if team_type not in CURRENT_TEAM_TYPES:
            raise ValueError(
                f"Invalid current_team_type '{team_type}'. Allowed: {', '.join(CURRENT_TEAM_TYPES)}"
            )
    if team in IPL_TEAMS:
        if team_type not in (None, "ipl"):
            raise ValueError(f"'{team}' is an IPL franchise, so current_team_type must be 'ipl'")
        return team, "ipl"
    if team in SPECIAL_CURRENT_TEAMS:
        if team_type is not None:
            raise ValueError(
                f"'{team}' is a special value and must use current_team_type null"
            )
        return team, None
    if team_type == "ipl":
        raise ValueError(f"'{team}' is not one of the 10 allowed IPL franchises")
    return team, "other"


def _normalise_entry(entry: dict | None) -> dict:
    if not isinstance(entry, dict):
        return _default_entry()
    status = str(entry.get("status", "unknown")).strip().lower()
    if status not in ALLOWED_STATUSES:
        status = "unknown"
    try:
        team, team_type = _validate_team(
            entry.get("current_team"), entry.get("current_team_type")
        )
    except ValueError:
        team, team_type = None, None
    return {
        "status": status,
        "current_team": team,
        "current_team_type": team_type,
        "note": str(entry.get("note") or ""),
        "rr_fit": str(entry.get("rr_fit") or ""),
    }

RANKING_FILES = (
    ("batters.json", "All_Batter_Rankings.csv", "batter"),
    ("bowlers.json", "All_Bowler_Rankings.csv", "bowler"),
)

NUMERIC_RANKING_COLUMNS = {
    "rank",
    "all_rank",
    "qualified_rank",
    "score",
    "pressure_balls",
    "IPL_balls",
    "T20I_balls",
    "pressure",
    "runs",
    "dots",
    "boundaries",
    "wickets",
    "impact",
    "wpa",
    "expected",
    "run_rate",
    "impact100",
    "wpa100",
    "dots_pct",
    "boundaries_pct",
    "wickets_pct",
    "expected100",
    "economy",
    "economy_above_expected",
    "normal_impact",
    "delta",
    "consistency",
    "pressure_matches",
    "eb_weight",
    "shrunk_performance",
    "shrunk_wpa",
    "shrunk_delta",
    "form2026_balls",
    "form2026_impact100",
    "score_lo",
    "score_hi",
    "rank_lo",
    "rank_hi",
    "IPL_impact100",
    "T20I_impact100",
    "IPL_wpa100",
    "T20I_wpa100",
    "matches",
    "fours",
    "sixes",
    "dismissals",
    "strike_rate",
    "wides",
    "no_balls",
    "other_extras",
    "positive_matches",
    "exposed_matches",
    "stability",
}

MODULE_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")

EXPERIENCE_TABLE = (
    (76, 7, "Veteran"),
    (51, 6, "Experienced"),
    (31, 5, "Regular"),
    (21, 4, "Developing"),
    (11, 3, "Fringe"),
    (6, 2, "Newcomer"),
    (1, 1, "Debutant"),
)


def experience_from_matches(matches) -> tuple[int, str]:
    try:
        value = int(matches or 0)
    except (TypeError, ValueError):
        value = 0
    for threshold, marks, label in EXPERIENCE_TABLE:
        if value >= threshold:
            return marks, label
    return 0, "No matches"


def _score_percentiles(rows: list[dict]) -> dict[int, float]:
    scored = [
        (row.get("score"), index)
        for index, row in enumerate(rows)
        if row.get("score") is not None
    ]
    scored.sort(key=lambda item: -item[0])
    total = len(scored)
    result: dict[int, float] = {}
    for position, (_, index) in enumerate(scored):
        result[index] = (
            100.0
            if total <= 1
            else 100.0 * (total - 1 - position) / (total - 1)
        )
    return result



def _canon_id(value) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        text = str(value).strip()
        return text or None


def _json_scalar(value):
    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return None if not math.isfinite(number) else number
    if isinstance(value, str):
        return value.strip()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _float_or_none(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _int_or_none(value):
    number = _float_or_none(value)
    return None if number is None else int(round(number))


def _flag(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return str(value).strip().lower() in {"y", "yes", "true", "1", "t"}


def default_status(ipl_played) -> str:
    if ipl_played is None:
        return "unknown"
    try:
        if pd.isna(ipl_played):
            return "unknown"
    except (TypeError, ValueError):
        pass
    return "no_ipl" if str(ipl_played).strip().upper() in {"N", "NO", "FALSE", "0"} else "unknown"


def _utc_from_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return stamp.isoformat(timespec="seconds").replace("+00:00", "Z")


class Store:
    def __init__(
        self,
        root: str | Path | None = None,
        rankings_dir: str | Path | None = None,
        derived_dir: str | Path | None = None,
        status_file: str | Path | None = None,
        history_file: str | Path | None = None,
        db_file: str | Path | None = None,
        database_url: str | None = None,
    ):
        self.root = Path(root) if root else Path(__file__).resolve().parents[1]
        self.rankings_dir = (
            Path(rankings_dir) if rankings_dir else self.root / "data_derived" / "scores"
        )
        self.master_rankings_path = (
            self.root / "data_rankings" / "RR_2027_All_838_Players_Master.csv"
        )
        self.derived_dir = Path(derived_dir) if derived_dir else self.root / "data_derived"
        # status_file/history_file are legacy JSON locations used once to seed the
        # database. The live store is always the SQLite file.
        self.status_file = Path(status_file) if status_file else self.root / "status.json"
        self.seed_status_file = self.root / "backend" / "data" / "public_status_seed.json"
        self.history_file = (
            Path(history_file) if history_file else self.root / "status_history.json"
        )
        self.database_url = database_url or (
            None if db_file else os.getenv("DATABASE_URL")
        )
        if self.database_url and self.database_url.startswith("postgres://"):
            self.database_url = "postgresql://" + self.database_url[len("postgres://") :]
        self.db_file = (
            None
            if self.database_url
            else Path(db_file)
            if db_file
            else Path(os.getenv("RR_STATUS_DB") or self.root / "backend" / "data" / "app.db")
        )

        self._lock = threading.RLock()
        self._rankings: list[dict] = []
        self._rankings_stamp = None
        self._rankings_message = ""
        self._rankings_loaded = False
        self._rating_meta: dict = {}

        self._index: list[dict] = []
        self._index_stamp = None

        self._init_db()

    # ------------------------------------------------------------------
    # File stamps / reloads
    # ------------------------------------------------------------------

    @staticmethod
    def _stamp(paths: list[Path]):
        stamp = []
        for path in paths:
            exists = path.exists()
            stamp.append(
                (
                    str(path),
                    exists,
                    path.stat().st_mtime_ns if exists else None,
                )
            )
        return tuple(stamp)

    def _ranking_paths(self) -> list[Path]:
        paths = []
        for filename, legacy, _ in RANKING_FILES:
            paths.extend((self.rankings_dir / filename, self.rankings_dir / legacy))
        paths.append(self.rankings_dir / "rubric.json")
        paths.append(self.master_rankings_path)
        return paths

    def rankings(self) -> list[dict]:
        with self._lock:
            stamp = self._stamp(self._ranking_paths())
            if stamp != self._rankings_stamp:
                self._load_rankings()
                self._rankings_stamp = stamp
            return self._rankings

    def _apply_rubric(self, rows: list[dict]) -> None:
        rubric: dict = {}
        meta: dict = {"generated_at": None, "scale": 100, "weights": {}, "experience_table": []}
        master_rows = any(row.get("ranking_source") == "rr_2027_master" for row in rows)
        if master_rows:
            meta["source"] = rows[0].get("data_scope")
            meta["analysis_version"] = rows[0].get("analysis_version")
        else:
            path = self.rankings_dir / "rubric.json"
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    payload = {}
                if isinstance(payload, dict):
                    rubric = payload.get("players") or {}
                    meta = {
                        "generated_at": payload.get("generated_at"),
                        "scale": payload.get("scale", 100),
                        "weights": payload.get("weights") or {},
                        "experience_table": payload.get("experience_table") or [],
                    }
        self._rating_meta = meta

        for row in rows:
            is_master = row.get("ranking_source") == "rr_2027_master"
            entry = None if is_master else rubric.get(f"{row['player_type']}:{row['player_id']}")
            matches = int(row.get("matches") or 0)
            marks, label = experience_from_matches(matches)
            row["matches"] = matches
            row["experience"] = row.get("experience") or label
            row["experience_marks"] = (
                row.get("experience_marks") if is_master else marks
            )
            row["rating100"] = row.get("score") if is_master else None
            row["role_fit"] = None
            row["rubric"] = None
            row["risk"] = None
            row["strengths"] = []
            row["weaknesses"] = []
            if not is_master:
                row["sample_marks"] = None
                row["career_innings"] = None
                row["career_runs"] = None
                row["career_wickets"] = None
                row["career_average"] = None
                row["career_sr"] = None
                row["career_econ"] = None
                row["career_dot_pct"] = None
                row["career_fours"] = None
                row["career_sixes"] = None
                row["balls_per_boundary"] = None
            if entry:
                row["rating100"] = entry.get("total")
                row["role_fit"] = entry.get("role_fit")
                row["rubric"] = entry
                row["risk"] = entry.get("risk")
                row["strengths"] = entry.get("strengths") or []
                row["weaknesses"] = entry.get("weaknesses") or []
                row["sample_marks"] = entry.get("sample_marks")
                row["matches"] = int(entry.get("matches") or matches)
                row["experience"] = entry.get("experience") or label
                row["experience_marks"] = entry.get("experience_marks") or marks
                row["career_innings"] = entry.get("innings")
                row["career_runs"] = entry.get("runs")
                row["career_wickets"] = entry.get("wickets")
                row["career_average"] = entry.get("average")
                row["career_sr"] = entry.get("strike_rate")
                row["career_econ"] = entry.get("economy")
                row["career_dot_pct"] = entry.get("dot_pct")
                row["career_fours"] = entry.get("fours")
                row["career_sixes"] = entry.get("sixes")
                row["balls_per_boundary"] = entry.get("balls_per_boundary")

        by_role: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            by_role[row["player_type"]].append(row)
        for group in by_role.values():
            percentiles = _score_percentiles(group)
            for index, row in enumerate(group):
                if row["rating100"] is not None:
                    continue
                row["rating100"] = round(percentiles.get(index, 0.0), 1)
                pressure_balls = _float_or_none(row.get("pressure_balls")) or 0
                row["sample_marks"] = round(6.0 * min(1.0, pressure_balls / 300.0), 1)

    def _load_master_rankings(self) -> list[dict]:
        df = pd.read_csv(self.master_rankings_path)
        required = {
            "player_id",
            "name",
            "data_scope",
            "analysis_version",
            "player_role",
            "latest_team",
            "latest_ipl_team",
            "played_ipl_2022_2026",
        }
        for role in ("batter", "bowler"):
            required.update(
                {
                    f"{role}_rank_all",
                    f"{role}_rank_qualified",
                    f"{role}_qualification_status",
                    f"{role}_score_100",
                    f"{role}_data_confidence_100",
                    f"{role}_matches",
                    f"{role}_pressure_matches",
                }
            )
        missing = sorted(required.difference(df.columns))
        if missing:
            raise ValueError(f"master rankings CSV is missing required columns: {missing}")

        rows = []
        for _, source in df.iterrows():
            for player_type in ("batter", "bowler"):
                prefix = player_type

                def value(field):
                    return _float_or_none(source.get(f"{prefix}_{field}"))

                player_id = _canon_id(source.get("player_id"))
                rank = _int_or_none(source.get(f"{prefix}_rank_all"))
                score = value("score_100")
                if player_id is None or rank is None or score is None:
                    continue

                qualification_status = str(
                    source.get(f"{prefix}_qualification_status") or ""
                ).strip().upper()
                qualification_status = (
                    "QUALIFIED" if qualification_status == "QUALIFIED" else "BELOW_MIN"
                )
                balls = value("balls_faced" if player_type == "batter" else "legal_balls")
                pressure_balls = value(
                    "pressure_balls" if player_type == "batter" else "pressure_legal_balls"
                )
                matches = value("matches") or 0
                runs = value("runs" if player_type == "batter" else "runs_conceded")
                wickets = value("wickets") if player_type == "bowler" else None
                fours = value("fours") if player_type == "batter" else None
                sixes = value("sixes") if player_type == "batter" else None
                boundaries = value("boundaries") if player_type == "batter" else None
                dot_pct = value("dot_ball_pct")
                dot_balls = (
                    round((dot_pct or 0) * (balls or 0) / 100)
                    if player_type == "batter"
                    else value("dot_balls")
                )
                pressure_impact = (
                    value("pressure_strike_rate")
                    if player_type == "batter"
                    else value("pressure_wickets_per100")
                )
                normal_impact = (
                    value("normal_strike_rate")
                    if player_type == "batter"
                    else value("normal_economy")
                )
                phase = str(source.get(f"{prefix}_dominant_phase") or "").strip().title()
                consistency = value("consistency_component_pct")
                qualification_rank = _int_or_none(
                    source.get(f"{prefix}_rank_qualified")
                )
                record = {
                    "player_type": player_type,
                    "ranking_source": "rr_2027_master",
                    "rank": rank,
                    "raw_rank": rank,
                    "all_rank": rank,
                    "qualified_rank": qualification_rank,
                    "qualification_status": qualification_status,
                    "source_qualification_status": str(
                        source.get(f"{prefix}_qualification_status") or ""
                    ),
                    "player_id": int(player_id) if player_id.isdigit() else player_id,
                    "name": str(source.get("name") or "").strip(),
                    "role": str(source.get("player_role") or player_type).strip(),
                    "score": score,
                    "score_lo": None,
                    "score_hi": None,
                    "rank_lo": None,
                    "rank_hi": None,
                    "rank_interval": None,
                    "data_confidence_100": value("data_confidence_100"),
                    "data_scope": str(source.get("data_scope") or ""),
                    "analysis_version": str(source.get("analysis_version") or ""),
                    "pressure_balls": pressure_balls,
                    "IPL_balls": balls,
                    "T20I_balls": None,
                    "pressure": value(
                        "pressure_runs"
                        if player_type == "batter"
                        else "pressure_runs_conceded"
                    ),
                    "runs": runs,
                    "dots": dot_balls,
                    "boundaries": boundaries,
                    "wickets": wickets,
                    "impact100": pressure_impact,
                    "normal_impact": normal_impact,
                    "delta": value(
                        "pressure_sr_uplift"
                        if player_type == "batter"
                        else "pressure_economy_improvement_raw"
                    ),
                    "consistency": (
                        consistency / 100 if consistency is not None else None
                    ),
                    "dots_pct": dot_pct,
                    "boundaries_pct": (
                        boundaries / balls * 100
                        if boundaries is not None and balls
                        else None
                    ),
                    "wickets_pct": (
                        wickets / balls * 100
                        if wickets is not None and balls
                        else None
                    ),
                    "economy": value("economy"),
                    "economy_above_expected": (
                        value("pressure_economy_adjusted") - normal_impact
                        if player_type == "bowler"
                        and value("pressure_economy_adjusted") is not None
                        and normal_impact is not None
                        else None
                    ),
                    "dominant_phase": phase or None,
                    "pressure_matches": value("pressure_matches"),
                    "matches": matches,
                    "career_innings": value("innings"),
                    "career_runs": runs if player_type == "batter" else None,
                    "career_wickets": wickets,
                    "career_average": value("average"),
                    "career_sr": value("strike_rate") if player_type == "batter" else None,
                    "career_econ": value("economy") if player_type == "bowler" else None,
                    "career_dot_pct": dot_pct,
                    "career_fours": fours,
                    "career_sixes": sixes,
                    "balls_per_boundary": value("balls_per_boundary"),
                    "sample_marks": value("sample_size_marks_6"),
                    "experience_marks": value("experience_marks_7"),
                    "latest_team": _json_scalar(source.get("latest_team")),
                    "latest_IPL_team": _json_scalar(source.get("latest_ipl_team")),
                    "IPL_PLAYED": _json_scalar(source.get("played_ipl_2022_2026")),
                    "RECENT_FORM_FLAG": None,
                    "IPL_PRESSURE_FLAG": None,
                    "SAMPLE_FLAG": None,
                    "PLAYED_2026_IPL": None,
                    "rank_variants": {},
                }
                rows.append(record)

        if not rows:
            raise ValueError("master rankings CSV contains no ranked batter or bowler rows")
        rows.sort(key=lambda row: (row["player_type"], row["rank"], row["name"]))
        return rows

    def _load_rankings(self):
        if self.master_rankings_path.exists():
            try:
                rows = self._load_master_rankings()
            except (OSError, ValueError, pd.errors.ParserError) as exc:
                with self._lock:
                    self._rankings = []
                    self._rankings_loaded = False
                    self._rankings_message = (
                        f"{self.master_rankings_path.name} could not be loaded: {exc}"
                    )
                return

            self._apply_rubric(rows)
            with self._lock:
                self._rankings = rows
                self._rankings_loaded = True
                self._rankings_message = (
                    f"Loaded RR 2027 master rankings ({len(rows)} role rankings): "
                    f"{rows[0].get('data_scope')}."
                )
            return

        rows: list[dict] = []
        messages: list[str] = []
        seen: set[tuple[str, str]] = set()
        used_engine = False

        for json_name, csv_name, fallback_role in RANKING_FILES:
            json_path = self.rankings_dir / json_name
            csv_path = self.rankings_dir / csv_name
            source_label = json_name
            if json_path.exists():
                try:
                    payload = json.loads(json_path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict):
                        payload = payload.get("players") or payload.get("rows") or []
                    df = pd.DataFrame(payload)
                    used_engine = True
                except Exception as exc:  # pragma: no cover - surfaced via API
                    messages.append(f"{json_name} could not be read: {exc}")
                    continue
            elif csv_path.exists():
                source_label = csv_name
                try:
                    df = pd.read_csv(csv_path)
                except Exception as exc:  # pragma: no cover - surfaced via API
                    messages.append(f"{csv_name} could not be read: {exc}")
                    continue
            else:
                messages.append(f"{json_name} not found")
                continue

            missing = [c for c in ("player_id", "name", "score", "rank") if c not in df.columns]
            if missing:
                messages.append(f"{source_label} is missing required columns: {missing}")
                continue

            for col in NUMERIC_RANKING_COLUMNS:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            for _, source in df.iterrows():
                pid = _canon_id(source.get("player_id"))
                rank = _int_or_none(source.get("rank"))
                score = _float_or_none(source.get("score"))
                if pid is None or rank is None or score is None:
                    continue

                player_type = str(source.get("player_type") or fallback_role).strip().lower()
                if player_type not in ("batter", "bowler"):
                    player_type = fallback_role

                key = (player_type, pid)
                if key in seen:
                    continue
                seen.add(key)

                record = {
                    col: _json_scalar(source.get(col))
                    for col in df.columns
                }
                record["player_id"] = int(pid) if pid.isdigit() else pid
                record["player_type"] = player_type
                record["rank"] = rank
                record["raw_rank"] = rank
                record["all_rank"] = _int_or_none(source.get("all_rank")) or rank
                record["qualified_rank"] = _int_or_none(source.get("qualified_rank"))
                pressure_balls = _int_or_none(source.get("pressure_balls"))
                status = str(source.get("qualification_status") or "").strip().upper()
                if status not in ("QUALIFIED", "BELOW_MIN"):
                    status = "QUALIFIED" if (pressure_balls or 0) >= 150 else "BELOW_MIN"
                record["qualification_status"] = status
                record["rank_variants"] = (
                    source.get("rank_variants")
                    if isinstance(source.get("rank_variants"), dict)
                    else {}
                )
                record["score"] = score
                record["name"] = str(source.get("name") or "").strip()
                record["role"] = str(source.get("role") or player_type).strip()
                record["latest_team"] = _json_scalar(source.get("latest_team"))
                record["latest_IPL_team"] = _json_scalar(source.get("latest_IPL_team"))
                record["team_label"] = (
                    record["latest_IPL_team"] or record["latest_team"]
                )
                record["rank_lo"] = _int_or_none(source.get("rank_lo"))
                record["rank_hi"] = _int_or_none(source.get("rank_hi"))
                if record["rank_lo"] is not None and record["rank_hi"] is not None:
                    record["rank_interval"] = f"{record['rank_lo']}-{record['rank_hi']}"
                else:
                    record["rank_interval"] = None
                record["score_lo"] = _float_or_none(source.get("score_lo"))
                record["score_hi"] = _float_or_none(source.get("score_hi"))
                record["flags"] = {
                    "recent_form": _flag(source.get("RECENT_FORM_FLAG")),
                    "ipl_pressure": _flag(source.get("IPL_PRESSURE_FLAG")),
                    "sample": _flag(source.get("SAMPLE_FLAG")),
                    "played_2026": _flag(source.get("PLAYED_2026_IPL")),
                }
                rows.append(record)

        rows.sort(key=lambda r: (r["player_type"], r["rank"], r["name"]))
        self._apply_rubric(rows)
        with self._lock:
            self._rankings = rows
            self._rankings_loaded = bool(rows)
            if rows and not messages:
                self._rankings_message = (
                    "Loaded engine scores from data_derived/scores."
                    if used_engine
                    else "Loaded headline rankings."
                )
            elif rows:
                self._rankings_message = "Loaded with warnings: " + "; ".join(messages)
            else:
                self._rankings_message = (
                    "No score tables loaded. Run python engine/run_all.py to write "
                    "data_derived/scores/batters.json and bowlers.json. " + "; ".join(messages)
                ).strip()

    @property
    def rankings_loaded(self) -> bool:
        self.rankings()
        return self._rankings_loaded

    @property
    def rankings_message(self) -> str:
        self.rankings()
        return self._rankings_message

    # ------------------------------------------------------------------
    # Status store
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self):
        if self.database_url:
            import psycopg
            from psycopg.rows import dict_row

            connection = psycopg.connect(self.database_url, row_factory=dict_row)
        else:
            connection = sqlite3.connect(self.db_file, timeout=30)
            connection.row_factory = sqlite3.Row
        try:
            yield _ConnectionAdapter(connection, postgres=bool(self.database_url))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _init_db(self) -> None:
        if self.db_file:
            self.db_file.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as connection:
            if not self.database_url:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA busy_timeout=30000")
            history_id = (
                "BIGSERIAL PRIMARY KEY"
                if self.database_url
                else "INTEGER PRIMARY KEY AUTOINCREMENT"
            )
            for statement in (
                """
                CREATE TABLE IF NOT EXISTS player_status (
                    name TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    current_team TEXT,
                    current_team_type TEXT,
                    note TEXT NOT NULL DEFAULT '',
                    rr_fit TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )
                """,
                f"""
                CREATE TABLE IF NOT EXISTS status_history (
                    id {history_id},
                    name TEXT NOT NULL,
                    field TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    changed_at TEXT NOT NULL
                )
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_status_history_name
                    ON status_history(name, id);
                """,
                """
                CREATE TABLE IF NOT EXISTS team_xi (
                    slug TEXT PRIMARY KEY,
                    players TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
            ):
                connection.execute(statement)
            count = connection.execute(
                "SELECT COUNT(*) AS player_count FROM player_status"
            ).fetchone()["player_count"]
            if count == 0:
                self._seed_from_json(connection)

    def database_available(self) -> bool:
        with self._lock, self._connect() as connection:
            connection.execute("SELECT 1")
        return True

    def _seed_from_json(self, connection: _ConnectionAdapter) -> None:
        """One-time import of legacy JSON files. Never runs against a seeded DB."""
        status = self._read_legacy_status()
        if not status:
            return
        stamp = self._stamp_now()
        connection.executemany(
            """
            INSERT INTO player_status
                (name, status, current_team, current_team_type, note, rr_fit, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    name,
                    entry["status"],
                    entry["current_team"],
                    entry["current_team_type"],
                    entry["note"],
                    entry["rr_fit"],
                    stamp,
                )
                for name, entry in status.items()
            ],
        )
        history = self._read_legacy_history()
        for name, entries in history.items():
            for entry in entries:
                for change in entry["changes"]:
                    connection.execute(
                        """
                        INSERT INTO status_history
                            (name, field, old_value, new_value, changed_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            name,
                            change["field"],
                            None if change.get("old") is None else str(change["old"]),
                            None if change.get("new") is None else str(change["new"]),
                            entry["timestamp"] or stamp,
                        ),
                    )

    def _read_legacy_status(self) -> dict[str, dict]:
        for path, is_seed in (
            (self.status_file, False),
            (self.seed_status_file, True),
        ):
            if not path.exists():
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                if is_seed:
                    raise RuntimeError(f"Unable to read public status seed: {path}") from exc
                continue

            if is_seed:
                if not isinstance(raw, dict) or not isinstance(raw.get("players"), dict):
                    raise RuntimeError(f"Public status seed has an invalid format: {path}")
                raw = raw["players"]

            loaded = {}
            if isinstance(raw, dict):
                for name, entry in raw.items():
                    if isinstance(entry, dict):
                        loaded[str(name).strip()] = _normalise_entry(entry)
            if loaded:
                return loaded
            if is_seed:
                raise RuntimeError(f"Public status seed contains no player records: {path}")
        return {}

    def _read_legacy_history(self) -> dict[str, list[dict]]:
        loaded: dict[str, list[dict]] = {}
        if not self.history_file.exists():
            return loaded
        try:
            raw = json.loads(self.history_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return loaded
        if not isinstance(raw, dict):
            return loaded
        for name, entries in raw.items():
            if not isinstance(entries, list):
                continue
            clean_entries = []
            for item in entries:
                if not isinstance(item, dict):
                    continue
                changes = []
                for change in item.get("changes") or []:
                    if not isinstance(change, dict):
                        continue
                    field = str(change.get("field") or "").strip()
                    if field not in STATUS_FIELDS:
                        continue
                    changes.append(
                        {
                            "field": field,
                            "old": change.get("old"),
                            "new": change.get("new"),
                        }
                    )
                if changes:
                    clean_entries.append(
                        {
                            "timestamp": str(item.get("timestamp") or ""),
                            "changes": changes,
                        }
                    )
            if clean_entries:
                loaded[str(name).strip()] = clean_entries[-100:]
        return loaded

    def status_map(self) -> dict[str, dict]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT name, status, current_team, current_team_type, note, rr_fit
                FROM player_status
                ORDER BY name
                """
            ).fetchall()
        return {
            row["name"]: _normalise_entry(
                {
                    "status": row["status"],
                    "current_team": row["current_team"],
                    "current_team_type": row["current_team_type"],
                    "note": row["note"],
                    "rr_fit": row["rr_fit"],
                }
            )
            for row in rows
        }

    # ------------------------------------------------------------------
    # Custom playing XI per team
    # ------------------------------------------------------------------

    def custom_xi(self, slug: str) -> dict | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT players, updated_at FROM team_xi WHERE slug = ?", (slug,)
            ).fetchone()
        if row is None:
            return None
        try:
            players = json.loads(row["players"])
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(players, list):
            return None
        return {
            "players": [str(name) for name in players],
            "updated_at": row["updated_at"],
        }

    def set_custom_xi(self, slug: str, players: list[str]) -> None:
        payload = json.dumps([str(name) for name in players])
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO team_xi (slug, players, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    players=excluded.players,
                    updated_at=excluded.updated_at
                """,
                (slug, payload, self._stamp_now()),
            )

    def clear_custom_xi(self, slug: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM team_xi WHERE slug = ?", (slug,))

    def _write_status(self, status: dict[str, dict]) -> None:
        stamp = self._stamp_now()
        distinct = "IS DISTINCT FROM" if self.database_url else "IS NOT"
        with self._lock, self._connect() as connection:
            connection.executemany(
                f"""
                INSERT INTO player_status
                    (name, status, current_team, current_team_type, note, rr_fit, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    status=excluded.status,
                    current_team=excluded.current_team,
                    current_team_type=excluded.current_team_type,
                    note=excluded.note,
                    rr_fit=excluded.rr_fit,
                    updated_at=excluded.updated_at
                WHERE player_status.status {distinct} excluded.status
                   OR player_status.current_team {distinct} excluded.current_team
                   OR player_status.current_team_type {distinct} excluded.current_team_type
                   OR player_status.note {distinct} excluded.note
                   OR player_status.rr_fit {distinct} excluded.rr_fit
                """,
                [
                    (
                        name,
                        entry["status"],
                        entry["current_team"],
                        entry["current_team_type"],
                        entry["note"],
                        entry["rr_fit"],
                        stamp,
                    )
                    for name, entry in status.items()
                ],
            )

    def status_for(self, name: str, ipl_played) -> tuple[str, dict]:
        status_map = self.status_map()
        entry = status_map.get(str(name).strip())
        if entry:
            return entry["status"], entry
        fallback = default_status(ipl_played)
        return fallback, _default_entry(fallback)

    # ------------------------------------------------------------------
    # Change history
    # ------------------------------------------------------------------

    def history_map(self) -> dict[str, list[dict]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT name, field, old_value, new_value, changed_at
                FROM status_history
                ORDER BY name, id
                """
            ).fetchall()
        loaded: dict[str, list[dict]] = {}
        for row in rows:
            name = row["name"]
            entries = loaded.setdefault(name, [])
            stamp = row["changed_at"]
            if not entries or entries[-1]["timestamp"] != stamp:
                entries.append({"timestamp": stamp, "changes": []})
            entries[-1]["changes"].append(
                {
                    "field": row["field"],
                    "old": row["old_value"],
                    "new": row["new_value"],
                }
            )
        return {name: entries[-100:] for name, entries in loaded.items()}

    def _write_history(self, history: dict[str, list[dict]]) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM status_history")
            rows = []
            for name, entries in history.items():
                for entry in entries[-100:]:
                    for change in entry.get("changes") or []:
                        rows.append(
                            (
                                name,
                                change["field"],
                                None if change.get("old") is None else str(change["old"]),
                                None if change.get("new") is None else str(change["new"]),
                                entry.get("timestamp") or self._stamp_now(),
                            )
                        )
            if rows:
                connection.executemany(
                    """
                    INSERT INTO status_history
                        (name, field, old_value, new_value, changed_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    def history_available(self) -> bool:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT 1 FROM status_history LIMIT 1").fetchone()
        return row is not None

    def history_for(self, name: str) -> list[dict]:
        return list(self.history_map().get(str(name).strip(), []))

    @staticmethod
    def _append_history(history: dict[str, list[dict]], name: str, changes, stamp: str):
        if not changes:
            return
        entries = list(history.get(name, []))
        entries.append({"timestamp": stamp, "changes": changes})
        history[name] = entries[-100:]

    def undo_last(self, name: str) -> dict:
        name = str(name).strip()
        if not name:
            raise ValueError("name is required")
        with self._lock:
            history = {
                key: list(entries) for key, entries in self.history_map().items()
            }
            entries = history.get(name)
            if not entries:
                raise ValueError(f"No change history for '{name}'")
            last = entries.pop()
            status = dict(self.status_map())
            entry = dict(status.get(name, _default_entry()))
            for change in last["changes"]:
                entry[change["field"]] = change["old"]
            status[name] = _normalise_entry(entry)
            if entries:
                history[name] = entries
            else:
                history.pop(name, None)
            self._write_status(status)
            self._write_history(history)
            return {"undone": last, "status": status}

    def undo_many(self, names: list[str]) -> dict:
        cleaned = []
        seen = set()
        for raw_name in names or []:
            name = str(raw_name or "").strip()
            if name and name not in seen:
                cleaned.append(name)
                seen.add(name)
        if not cleaned:
            raise ValueError("names must contain at least one player name")
        if len(cleaned) > 1000:
            raise ValueError("cannot undo more than 1,000 players at once")

        with self._lock:
            history = {
                key: list(entries) for key, entries in self.history_map().items()
            }
            status = dict(self.status_map())
            undone = {}
            skipped = []
            for name in cleaned:
                entries = history.get(name)
                if not entries:
                    skipped.append(name)
                    continue
                last = entries.pop()
                entry = dict(status.get(name, _default_entry()))
                for change in last["changes"]:
                    entry[change["field"]] = change["old"]
                status[name] = _normalise_entry(entry)
                if entries:
                    history[name] = entries
                else:
                    history.pop(name, None)
                undone[name] = last

            if not undone:
                raise ValueError("None of the selected players has change history to undo")
            self._write_status(status)
            self._write_history(history)
            return {
                "undone": undone,
                "skipped": skipped,
                "status": status,
                "summary": (
                    f"Undid the latest change for {len(undone)} player"
                    f"{'' if len(undone) == 1 else 's'}; skipped "
                    f"{len(skipped)} without history"
                ),
            }

    # ------------------------------------------------------------------
    # Updates, bulk edits, import/export
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_fields(
        entry: dict,
        *,
        status: str | None = None,
        note: str | None = None,
        rr_fit: str | None = None,
        current_team=_UNSET,
        current_team_type=_UNSET,
    ) -> tuple[dict, list[dict]]:
        updated = _normalise_entry(entry)
        changes: list[dict] = []

        if status is not None:
            status = str(status).strip().lower()
            if status not in ALLOWED_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. Allowed: {', '.join(ALLOWED_STATUSES)}"
                )
            if updated["status"] != status:
                changes.append(
                    {"field": "status", "old": updated["status"], "new": status}
                )
                updated["status"] = status
            if status == "no_ipl":
                current_team = NO_TEAM
                current_team_type = None

        if note is not None:
            note = str(note)
            if updated["note"] != note:
                changes.append(
                    {"field": "note", "old": updated["note"], "new": note}
                )
                updated["note"] = note

        if rr_fit is not None:
            rr_fit = str(rr_fit)
            if updated["rr_fit"] != rr_fit:
                changes.append(
                    {"field": "rr_fit", "old": updated["rr_fit"], "new": rr_fit}
                )
                updated["rr_fit"] = rr_fit

        if current_team is not _UNSET or current_team_type is not _UNSET:
            team_value = (
                current_team
                if current_team is not _UNSET
                else updated.get("current_team")
            )
            type_value = (
                current_team_type
                if current_team_type is not _UNSET
                else (None if current_team is not _UNSET else updated.get("current_team_type"))
            )
            team, team_type = _validate_team(team_value, type_value)
            if updated.get("current_team") != team:
                changes.append(
                    {
                        "field": "current_team",
                        "old": updated.get("current_team"),
                        "new": team,
                    }
                )
                updated["current_team"] = team
            if updated.get("current_team_type") != team_type:
                changes.append(
                    {
                        "field": "current_team_type",
                        "old": updated.get("current_team_type"),
                        "new": team_type,
                    }
                )
                updated["current_team_type"] = team_type

            if status is None and current_team is not _UNSET:
                suggested = suggest_status_for_team(updated.get("current_team"))
                if suggested and updated["status"] != suggested:
                    changes.append(
                        {
                            "field": "status",
                            "old": updated["status"],
                            "new": suggested,
                        }
                    )
                    updated["status"] = suggested

        return updated, changes

    @staticmethod
    def _stamp_now() -> str:
        return (
            datetime.now(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )

    def update_status(
        self,
        name: str,
        status: str | None = None,
        note: str | None = None,
        rr_fit: str | None = None,
        current_team=_UNSET,
        current_team_type=_UNSET,
    ) -> dict[str, dict]:
        name = str(name).strip()
        if not name:
            raise ValueError("name is required")

        with self._lock:
            current = dict(self.status_map())
            entry = dict(current.get(name, _default_entry()))
            entry, changes = self._apply_fields(
                entry,
                status=status,
                note=note,
                rr_fit=rr_fit,
                current_team=current_team,
                current_team_type=current_team_type,
            )
            current[name] = entry
            self._write_status(current)
            if changes:
                history = {
                    key: list(entries) for key, entries in self.history_map().items()
                }
                self._append_history(history, name, changes, self._stamp_now())
                self._write_history(history)
            return current

    def bulk_update(
        self,
        names: list[str],
        status: str | None = None,
        current_team=_UNSET,
        current_team_type=_UNSET,
    ) -> dict:
        cleaned: list[str] = []
        seen = set()
        for raw_name in names or []:
            name = str(raw_name or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            cleaned.append(name)
        if not cleaned:
            raise ValueError("names must contain at least one player name")
        if status is None and current_team is _UNSET and current_team_type is _UNSET:
            raise ValueError("Provide status, current_team or current_team_type")

        with self._lock:
            current = dict(self.status_map())
            history = {
                key: list(entries) for key, entries in self.history_map().items()
            }
            stamp = self._stamp_now()
            details = []
            for name in cleaned:
                entry = dict(current.get(name, _default_entry()))
                entry, changes = self._apply_fields(
                    entry,
                    status=status,
                    current_team=current_team,
                    current_team_type=current_team_type,
                )
                if not changes:
                    continue
                current[name] = entry
                self._append_history(history, name, changes, stamp)
                details.append({"player": name, "changed": changes})
            if details:
                self._write_status(current)
                self._write_history(history)
            team_for_suggestion = (
                current.get(cleaned[0], {}).get("current_team")
                if current_team is not _UNSET
                else None
            )
            return {
                "requested": len(cleaned),
                "changed": len(details),
                "unchanged": len(cleaned) - len(details),
                "details": details,
                "summary": f"Changed {len(details)} of {len(cleaned)} players",
                "suggestion": status_suggestion(team_for_suggestion),
            }

    def import_status(self, records: list[dict], dry_run: bool = True) -> dict:
        if not records:
            raise ValueError("Import contains no player records")

        merged: dict[str, dict] = {}
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("Each import record must be an object")
            name = str(record.get("player") or record.get("name") or "").strip()
            if not name:
                raise ValueError("Every import record needs a player/name field")
            target = merged.setdefault(name, {})
            if "status" in record:
                if record.get("status") is None:
                    raise ValueError(f"{name}: status cannot be null")
                target["status"] = record.get("status")
            if "current_team" in record:
                value = record.get("current_team")
                target["current_team"] = None if value == "" else value
            if "current_team_type" in record:
                value = record.get("current_team_type")
                target["current_team_type"] = None if value == "" else value
            if "note" in record:
                target["note"] = "" if record.get("note") is None else record.get("note")
            if "rr_fit" in record:
                target["rr_fit"] = "" if record.get("rr_fit") is None else record.get("rr_fit")

        with self._lock:
            current = dict(self.status_map())
            history = {
                key: list(entries) for key, entries in self.history_map().items()
            }
            stamp = self._stamp_now()
            changes = []
            for name, fields in merged.items():
                entry = dict(current.get(name, _default_entry()))
                try:
                    entry, field_changes = self._apply_fields(
                        entry,
                        status=fields.get("status"),
                        note=fields.get("note"),
                        rr_fit=fields.get("rr_fit"),
                        current_team=(
                            fields["current_team"]
                            if "current_team" in fields
                            else _UNSET
                        ),
                        current_team_type=(
                            fields["current_team_type"]
                            if "current_team_type" in fields
                            else _UNSET
                        ),
                    )
                except ValueError as exc:
                    raise ValueError(f"{name}: {exc}") from exc
                if not field_changes:
                    continue
                current[name] = entry
                changes.append({"player": name, "changed": field_changes})
                self._append_history(history, name, field_changes, stamp)

            result = {
                "dry_run": bool(dry_run),
                "players": len(merged),
                "changed": len(changes),
                "unchanged": len(merged) - len(changes),
                "changes": changes,
                "summary": (
                    f"{len(changes)} of {len(merged)} players would change"
                    if dry_run
                    else f"Updated {len(changes)} of {len(merged)} players"
                ),
            }
            if dry_run:
                return result

            if changes:
                self._write_status(current)
                self._write_history(history)
                result["players_map"] = current
            return result

    # ------------------------------------------------------------------
    # Status export helpers
    # ------------------------------------------------------------------

    def role_by_name(self) -> dict[str, str]:
        roles: dict[str, set[str]] = defaultdict(set)
        for row in self.rankings():
            name = str(row.get("name") or "").strip()
            if name:
                roles[name].add(row["player_type"])
        result = {}
        for name, values in roles.items():
            if values == {"batter"}:
                result[name] = "batter"
            elif values == {"bowler"}:
                result[name] = "bowler"
            else:
                result[name] = " + ".join(sorted(values))
        return result

    def data_team_values(self) -> list[str]:
        values = set()
        for row in self.rankings():
            for key in ("latest_IPL_team", "latest_team"):
                team = row.get(key)
                if team:
                    values.add(str(team))
        return sorted(values)

    def export_payload(self) -> dict:
        status = self.status_map()
        roles = self.role_by_name()
        return {
            "exported_at": self._stamp_now(),
            "players": {name: status[name] for name in sorted(status)},
            "roles": {name: roles.get(name, "") for name in sorted(status)},
        }

    def export_csv(self) -> str:
        status = self.status_map()
        roles = self.role_by_name()
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "player",
                "role",
                "status",
                "current_team",
                "current_team_type",
                "note",
                "rr_fit",
            ]
        )
        for name in sorted(status):
            entry = status[name]
            writer.writerow(
                [
                    name,
                    roles.get(name, ""),
                    entry.get("status", ""),
                    entry.get("current_team") or "",
                    entry.get("current_team_type") or "",
                    entry.get("note", ""),
                    entry.get("rr_fit", ""),
                ]
            )
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # Decoration and clean rankings
    # ------------------------------------------------------------------

    def _decorate(self, row: dict, status_map: dict[str, dict]) -> dict:
        decorated = dict(row)
        name = decorated.get("name") or ""
        entry = status_map.get(name)
        status = entry["status"] if entry else default_status(decorated.get("IPL_PLAYED"))
        decorated["status"] = status
        decorated["available"] = status in AVAILABLE_STATUSES
        decorated["note"] = entry["note"] if entry else ""
        decorated["rr_fit"] = entry["rr_fit"] if entry else ""
        current_team = entry.get("current_team") if entry else None
        current_team_type = entry.get("current_team_type") if entry else None
        data_team = decorated.get("latest_IPL_team") or decorated.get("latest_team")
        decorated["current_team"] = current_team
        decorated["current_team_type"] = current_team_type
        decorated["data_team"] = data_team
        decorated["team_source"] = "manual" if current_team is not None else "data"
        decorated["effective_team"] = (
            current_team if current_team is not None else data_team
        )
        decorated["clean_rank"] = None
        decorated["is_shortlist"] = False
        decorated["is_reserve"] = False
        return decorated

    def _assign_clean_ranks(self, rows: list[dict], available_only: bool) -> None:
        if not available_only:
            for row in rows:
                row["clean_rank"] = row.get("rank")
                row["is_shortlist"] = row["clean_rank"] is not None and row["clean_rank"] <= 10
                row["is_reserve"] = row["clean_rank"] is not None and 11 <= row["clean_rank"] <= 20
            return

        by_role: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            by_role[row["player_type"]].append(row)
        for group in by_role.values():
            pool = [r for r in group if r["available"]]
            pool.sort(
                key=lambda r: (
                    -(
                        r.get("rating100")
                        if r.get("rating100") is not None
                        else (r.get("score") if r.get("score") is not None else float("-inf"))
                    ),
                    -(r.get("score") if r.get("score") is not None else float("-inf")),
                    r.get("rank") or 10**9,
                    normalise_name(r.get("name")),
                )
            )
            for position, row in enumerate(pool, start=1):
                row["clean_rank"] = position
                row["is_shortlist"] = position <= 10
                row["is_reserve"] = 11 <= position <= 20

    def available_pool_count(self) -> int:
        rows = self.rankings()
        status_map = self.status_map()
        available_keys = set()
        for row in rows:
            status = status_map.get(row["name"], {}).get("status")
            if status is None:
                status = default_status(row.get("IPL_PLAYED"))
            if status in AVAILABLE_STATUSES:
                available_keys.add(_canon_id(row.get("player_id")))
        return len(available_keys)

    def players(
        self,
        role: str | None = None,
        available_only: bool = True,
        team: str | None = None,
        phase: str | None = None,
        min_ipl_balls: int | None = None,
        min_matches: int | None = None,
        current_team_unset: bool = False,
    ) -> dict:
        rows = self.rankings()
        status_map = self.status_map()
        decorated = [self._decorate(row, status_map) for row in rows]
        last_match_dates = {
            _canon_id(entry.get("player_id")): entry.get("last_match_date")
            for entry in self.player_index()
            if _canon_id(entry.get("player_id")) is not None
        }
        for row in decorated:
            row["last_match_date"] = last_match_dates.get(
                _canon_id(row.get("player_id"))
            )
        self._assign_clean_ranks(decorated, available_only)

        role_filter = None
        if role:
            role_filter = role.strip().lower().rstrip("s")
            if role_filter not in ("batter", "bowler"):
                raise ValueError("role must be 'batter' or 'bowler'")

        team_filter = team.strip().casefold() if team else None
        phase_filter = phase.strip().casefold() if phase else None
        if phase_filter == "pp":
            phase_filter = "powerplay"

        result = []
        for row in decorated:
            if role_filter and row["player_type"] != role_filter:
                continue
            if available_only and not row["available"]:
                continue
            if team_filter and str(row.get("effective_team") or "").casefold() != team_filter:
                continue
            if current_team_unset and row.get("current_team") is not None:
                continue
            if phase_filter and str(row.get("dominant_phase") or "").casefold() != phase_filter:
                continue
            if min_ipl_balls is not None:
                ipl_balls = _float_or_none(row.get("IPL_balls"))
                if ipl_balls is None or ipl_balls < min_ipl_balls:
                    continue
            if min_matches is not None:
                matches = _float_or_none(row.get("matches"))
                if matches is None or matches < min_matches:
                    continue
            result.append(row)

        result.sort(
            key=lambda r: (
                r["clean_rank"] is None,
                r["clean_rank"] if r["clean_rank"] is not None else 10**9,
                r["rank"],
            )
        )
        return {
            "ready": self._rankings_loaded,
            "message": self._rankings_message,
            "count": len(result),
            "available_pool": self.available_pool_count(),
            "rating_meta": self._rating_meta,
            "current_team_set": sum(
                1 for row in result if row.get("current_team") is not None
            ),
            "current_team_unset": sum(
                1 for row in result if row.get("current_team") is None
            ),
            "players": result,
        }

    def player(self, role: str, player_id: str) -> dict | None:
        role = role.strip().lower().rstrip("s")
        if role not in ("batter", "bowler"):
            return None
        pid = _canon_id(player_id)
        rows = self.rankings()
        status_map = self.status_map()
        decorated = [self._decorate(row, status_map) for row in rows]
        clean_rows = [dict(row) for row in decorated]
        self._assign_clean_ranks(clean_rows, available_only=True)
        clean_lookup = {
            (row["player_type"], _canon_id(row["player_id"])): row["clean_rank"]
            for row in clean_rows
        }
        for row in decorated:
            if row["player_type"] != role or _canon_id(row["player_id"]) != pid:
                continue
            row["clean_rank"] = clean_lookup.get((row["player_type"], pid))
            row["is_shortlist"] = row["clean_rank"] is not None and row["clean_rank"] <= 10
            row["is_reserve"] = row["clean_rank"] is not None and 11 <= row["clean_rank"] <= 20
            return {
                "ready": True,
                "player": row,
                "modules": self.modules_for(pid),
            }
        return None

    def modules_for(self, player_id: str) -> list[str]:
        if not self.derived_dir.exists():
            return []
        found = []
        for child in sorted(self.derived_dir.iterdir()):
            if not child.is_dir() or child.name == "recent":
                continue
            if (child / f"{player_id}.json").exists():
                found.append(child.name)
        return found

    def shortlist(self, role: str) -> dict:
        role = role.strip().lower().rstrip("s")
        if role not in ("batter", "bowler"):
            raise ValueError("role must be 'batter' or 'bowler'")
        payload = self.players(role=role, available_only=True)
        rows = payload["players"]
        return {
            "ready": payload["ready"],
            "message": payload["message"],
            "role": role,
            "shortlist": rows[:10],
            "reserves": rows[10:20],
        }

    def summary(self) -> dict:
        rows = self.rankings()
        status_map = self.status_map()
        decorated = [self._decorate(row, status_map) for row in rows]
        available_rows = [row for row in decorated if row["available"]]
        self._assign_clean_ranks(decorated, available_only=True)

        top = {"batter": [], "bowler": []}
        for row in sorted(
            [r for r in decorated if r["available"]],
            key=lambda r: (r["player_type"], r["clean_rank"] or 10**9),
        ):
            if len(top[row["player_type"]]) < 5:
                top[row["player_type"]].append(row)

        meta = self.meta()
        last_updated = meta.get("generated_at")
        if not last_updated:
            candidates = [
                _utc_from_mtime(path) for path in self._ranking_paths() if path.exists()
            ] + [_utc_from_mtime(self.status_file)]
            last_updated = max([c for c in candidates if c], default=None)

        ranked_names = {row["name"] for row in decorated}
        manual_team_names = {
            row["name"] for row in decorated if row.get("current_team") is not None
        }

        return {
            "ready": self._rankings_loaded,
            "message": self._rankings_message,
            "rating_meta": self._rating_meta,
            "qualifying_batters": sum(1 for r in rows if r["player_type"] == "batter"),
            "qualifying_bowlers": sum(1 for r in rows if r["player_type"] == "bowler"),
            "available_pool": self.available_pool_count(),
            "available_batters": sum(
                1 for r in available_rows if r["player_type"] == "batter"
            ),
            "available_bowlers": sum(
                1 for r in available_rows if r["player_type"] == "bowler"
            ),
            "current_team_set": len(manual_team_names),
            "current_team_missing": len(ranked_names) - len(manual_team_names),
            "last_updated": last_updated,
            "top5": top,
            "meta": meta,
        }

    # ------------------------------------------------------------------
    # Aggregate player statistics
    # ------------------------------------------------------------------

    @property
    def stats_dir(self) -> Path:
        return self.derived_dir / "stats"

    def _stats_index_payload(self) -> dict:
        path = self.stats_dir / "index.json"
        if not path.exists():
            return {"ready": False, "players": [], "options": {}, "meta": {}}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"ready": False, "players": [], "options": {}, "meta": {}}
        if not isinstance(payload, dict):
            return {"ready": False, "players": [], "options": {}, "meta": {}}
        return payload

    def stats_index(
        self,
        role: str | None = None,
        min_balls: int = 0,
        season: str | None = None,
        competition: str | None = None,
        team: str | None = None,
    ) -> dict:
        payload = self._stats_index_payload()
        rows = payload.get("players") or []
        threshold = 100 if role == "batter" else 120 if role == "bowler" else 0
        current_rankings = {}
        for ranking in self.rankings():
            player_id = _canon_id(ranking.get("player_id"))
            if player_id is None:
                continue
            existing = current_rankings.get(player_id)
            if existing is None or ranking["rank"] < existing["rank"]:
                current_rankings[player_id] = {
                    "role": ranking["player_type"],
                    "rank": ranking["rank"],
                }

        def balls_for(row):
            bat = (row.get("batting") or {}).get("balls") or 0
            bowl = (row.get("bowling") or {}).get("legal_balls") or 0
            if role == "batter":
                return bat
            if role == "bowler":
                return bowl
            return max(bat, bowl)

        filtered = []
        for row in rows:
            if role and row.get("role") not in (role, "both"):
                continue
            if team and row.get("latest_team") != team:
                continue
            if season and season not in (row.get("seasons") or []):
                continue
            if competition and competition not in (row.get("competitions") or []):
                continue
            if min_balls and balls_for(row) < int(min_balls):
                continue
            result = row
            if current_rankings:
                result = dict(row)
                ranking = current_rankings.get(_canon_id(row.get("player_id")))
                result["ranked"] = ranking is not None
                result["ranked_role"] = ranking["role"] if ranking else None
                result["ranked_rank"] = ranking["rank"] if ranking else None
            filtered.append(result)
        return {
            "ready": bool(payload.get("players")),
            "count": len(filtered),
            "threshold_balls": threshold,
            "rows": filtered,
            "options": payload.get("options") or {},
            "meta": payload.get("meta") or {},
        }

    def stats_player(self, player_id: str, split: str = "career") -> dict | None:
        pid = _canon_id(player_id)
        if pid is None or not pid.isdigit():
            return None
        path = self.stats_dir / f"{pid}.json"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        splits = payload.get("splits") or {}
        if split not in splits:
            split = "career" if "career" in splits else next(iter(splits), "career")
        record = splits.get(split) or {}
        percentiles = self._stats_percentiles(payload, record)
        return {
            **payload,
            "split": split,
            "split_label": record.get("label") or split,
            "available_splits": [
                {"key": key, "label": value.get("label", key)}
                for key, value in splits.items()
            ],
            "batting": record.get("batting"),
            "bowling": record.get("bowling"),
            "percentiles": percentiles,
            "thresholds": {"batting_balls": 100, "bowling_legal_balls": 120},
        }

    def _stats_percentiles(self, payload: dict, record: dict) -> dict:
        index = self._stats_index_payload().get("players") or []
        batting = record.get("batting") or {}
        bowling = record.get("bowling") or {}
        bat_keys = (
            "runs",
            "strike_rate",
            "average",
            "highest",
            "fours",
            "sixes",
            "boundary_pct",
            "dot_pct",
            "balls_per_boundary",
            "fifties",
            "hundreds",
        )
        bowl_keys = (
            "wickets",
            "economy",
            "average",
            "strike_rate",
            "dot_pct",
            "maidens",
            "four_w",
            "five_w",
        )
        bat_cohort = []
        bowl_cohort = []
        for row in index:
            bat = row.get("batting") or {}
            bowl = row.get("bowling") or {}
            if (bat.get("balls") or 0) >= 100:
                bat_cohort.append(bat)
            if (bowl.get("legal_balls") or 0) >= 120:
                bowl_cohort.append(bowl)
        return {
            "batting": {
                key: self._percentile([row.get(key) for row in bat_cohort], batting.get(key))
                for key in bat_keys
            },
            "bowling": {
                key: self._percentile([row.get(key) for row in bowl_cohort], bowling.get(key))
                for key in bowl_keys
            },
        }

    @staticmethod
    def _percentile(values, value):
        if value is None:
            return None
        clean = [v for v in values if isinstance(v, (int, float))]
        if not clean:
            return None
        below = sum(1 for v in clean if v < value)
        equal = sum(1 for v in clean if v == value)
        return round((below + 0.5 * equal) / len(clean) * 100, 1)

    @property
    def matchups_dir(self) -> Path:
        return self.derived_dir / "matchups"

    def matchups_player(self, player_id: str) -> dict | None:
        pid = _canon_id(player_id)
        if pid is None or not pid.isdigit():
            return None
        path = self.matchups_dir / f"{pid}.json"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    # ------------------------------------------------------------------
    # Search and recent form
    # ------------------------------------------------------------------

    def player_index(self) -> list[dict]:
        path = self.derived_dir / "player_index.json"
        with self._lock:
            stamp = self._stamp([path])
            if stamp != self._index_stamp:
                self._index_stamp = stamp
                if path.exists():
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        self._index = data if isinstance(data, list) else []
                    except (OSError, json.JSONDecodeError):
                        self._index = []
                else:
                    self._index = []
            return self._index

    def search(self, query: str, limit: int = 10) -> dict:
        index = self.player_index()
        q = str(query or "").strip()
        if not q:
            return {"ready": bool(index), "query": q, "results": []}
        q_norm = normalise_name(q)
        q_compact = compact_name(q)
        if not q_norm and not q_compact:
            return {"ready": bool(index), "query": q, "results": []}

        ranking_by_pid: dict[str, dict] = {}
        status_map = self.status_map()
        for row in self.rankings():
            pid = _canon_id(row["player_id"])
            if pid is None:
                continue
            existing = ranking_by_pid.get(pid)
            if existing is None or row["rank"] < existing["rank"]:
                ranking_by_pid[pid] = row

        scored = []
        for entry in index:
            pid = _canon_id(entry.get("player_id"))
            if pid is None:
                continue
            indexed_name = str(entry.get("name") or "")
            ranking = ranking_by_pid.get(pid)
            name = str(ranking.get("name") or indexed_name) if ranking else indexed_name
            name_norm = normalise_name(name)
            name_compact = compact_name(name)
            if not (
                q_norm in name_norm
                or (q_compact and q_compact in name_compact)
            ):
                continue

            if name_compact == q_compact:
                bucket = 0
            elif name_norm.startswith(q_norm):
                bucket = 1
            elif name_compact.startswith(q_compact):
                bucket = 2
            elif any(word.startswith(q_norm) for word in name_norm.split()):
                bucket = 3
            else:
                bucket = 4

            result = {
                "player_id": entry.get("player_id"),
                "name": name,
                "role": ranking.get("player_type") if ranking else entry.get("role"),
                "latest_team": entry.get("latest_team"),
                "current_team": status_map.get(name, {}).get("current_team"),
                "last_match_date": entry.get("last_match_date"),
                "ranked": ranking is not None,
                "ranked_role": ranking.get("player_type") if ranking else None,
                "ranked_rank": ranking.get("rank") if ranking else None,
            }
            scored.append(((bucket, ranking is None, name_norm), result))

        scored.sort(key=lambda item: item[0])
        return {
            "ready": bool(index),
            "query": q,
            "results": [item[1] for item in scored[: max(1, min(limit, 20))]],
        }

    def recent(self, player_id: str) -> dict | None:
        pid = _canon_id(player_id)
        if pid is None or not pid.isdigit():
            return None
        path = self.derived_dir / "recent" / f"{pid}.json"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        status_map = self.status_map()
        rankings = []
        for row in self.rankings():
            if _canon_id(row["player_id"]) != pid:
                continue
            decorated = self._decorate(row, status_map)
            decorated["flags"] = row.get("flags", {})
            rankings.append(decorated)
        rankings.sort(key=lambda r: r["rank"])
        primary = rankings[0] if rankings else None
        return {
            "player": payload,
            "ranking": primary,
            "rankings": rankings,
            "ranked": primary is not None,
            "status": primary["status"] if primary else None,
            "current_team": primary["current_team"] if primary else None,
            "current_team_type": primary["current_team_type"] if primary else None,
            "team_source": primary["team_source"] if primary else None,
            "effective_team": primary["effective_team"] if primary else None,
            "note": primary["note"] if primary else None,
            "rr_fit": primary["rr_fit"] if primary else None,
        }

    def derived(self, module: str, player_id: str) -> dict | None:
        if not MODULE_RE.fullmatch(module or ""):
            raise ValueError("invalid module name")
        pid = _canon_id(player_id)
        if pid is None or not pid.isdigit():
            return None
        base = self.derived_dir.resolve()
        path = (self.derived_dir / module / f"{pid}.json").resolve()
        if not path.is_relative_to(base) or not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def meta(self) -> dict:
        path = self.derived_dir / "meta.json"
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def health(self) -> dict:
        self.rankings()
        return {
            "ready": self._rankings_loaded,
            "rankings_message": self._rankings_message,
            "rankings_loaded": self._rankings_loaded,
            "player_index": (self.derived_dir / "player_index.json").exists(),
            "recent_files": len(list((self.derived_dir / "recent").glob("*.json")))
            if (self.derived_dir / "recent").exists()
            else 0,
            "meta": self.meta(),
        }
