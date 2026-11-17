"""Serialise small aggregate score tables for deployment."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from engine.config import COMPOSITE_WEIGHTS

REQUIRED_COLUMNS = [
    "player_type",
    "rank",
    "all_rank",
    "qualified_rank",
    "qualification_status",
    "player_id",
    "name",
    "score",
    "score_lo",
    "score_hi",
    "rank_lo",
    "rank_hi",
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
    "dominant_phase",
    "role",
    "IPL_PLAYED",
    "PLAYED_2026_IPL",
    "IPL_PRESSURE_FLAG",
    "latest_team",
    "latest_IPL_team",
    "form2026_balls",
    "form2026_impact100",
    "RECENT_FORM_FLAG",
    "SAMPLE_FLAG",
    "rank_variants",
    "stability",
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
]

EXTRA_NUMERIC = ("partial", "form2026_impact100", "form2026_balls")


def _value(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: _value(v) for k, v in value.items() if v is not None}
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return None if not math.isfinite(number) else round(number, 4)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _records(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for record in frame.to_dict(orient="records"):
        rows.append({column: _value(record.get(column)) for column in REQUIRED_COLUMNS})
    return rows


def _top(frame: pd.DataFrame, limit: int = 10) -> list[dict]:
    qualified = frame[frame["qualification_status"].eq("QUALIFIED")].head(limit)
    return [
        {
            "rank": int(row["qualified_rank"]),
            "player_id": str(row["player_id"]),
            "name": row["name"],
            "score": float(row["score"]),
            "score_lo": float(row["score_lo"]),
            "score_hi": float(row["score_hi"]),
            "pressure_balls": int(row["pressure_balls"]),
            "impact100": _value(row["impact100"]),
            "shrunk_performance": _value(row["shrunk_performance"]),
            "wpa100": _value(row["wpa100"]),
            "delta": _value(row["delta"]),
            "consistency": _value(row["consistency"]),
            "eb_weight": _value(row["eb_weight"]),
            "role": row["role"],
            "SAMPLE_FLAG": row["SAMPLE_FLAG"],
        }
        for _, row in qualified.iterrows()
    ]


def write_role(
    frame: pd.DataFrame,
    role: str,
    scores_dir: Path,
) -> dict:
    frame = frame.copy()
    frame["player_type"] = role
    if role == "batter":
        frame["impact"] = frame["pressure_impact"]
        frame["wpa"] = frame["pressure_wpa"]
        frame["expected"] = frame["pressure_expected"]
        frame["run_rate"] = frame["strike_rate"]
        frame["wickets"] = frame["dismissals"]
        frame["IPL_PRESSURE_FLAG"] = np.where(frame["IPL_balls"] >= 30, "OK", "LOW")
    else:
        frame["impact"] = frame["pressure_impact"]
        frame["wpa"] = frame["pressure_wpa"]
        frame["expected"] = frame["pressure_expected"]
        frame["IPL_PRESSURE_FLAG"] = np.where(frame["IPL_balls"] >= 30, "OK", "LOW")
    frame = frame.sort_values(["all_rank", "player_id"], kind="mergesort").reset_index(drop=True)
    frame["rank"] = frame["all_rank"]
    records = _records(frame)
    path = scores_dir / ("batters.json" if role == "batter" else "bowlers.json")
    path.write_text(json.dumps(records, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {
        "path": str(path),
        "rows": len(records),
        "qualified": int(frame["qualification_status"].eq("QUALIFIED").sum()),
        "below_min": int(frame["qualification_status"].eq("BELOW_MIN").sum()),
        "wide": int(frame["SAMPLE_FLAG"].eq("WIDE").sum()),
        "top10": _top(frame),
        "score": {
            "mean": round(float(frame["score"].mean()), 2),
            "top": round(float(frame["score"].max()), 2),
            "qualified_mean": round(
                float(frame.loc[frame["qualification_status"].eq("QUALIFIED"), "score"].mean()), 2
            ),
        },
    }


def write_meta(scores_dir: Path, meta: dict):
    meta = {**meta, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (scores_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1, default=_value), encoding="utf-8"
    )
    return meta
