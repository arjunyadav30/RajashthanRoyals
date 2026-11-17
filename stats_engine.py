"""Aggregate player statistics built from the prepared delivery table.

Only aggregate, per-player, per-split records are written. No delivery-level
rows leave this module.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SMALL_SAMPLE_BALLS = 30
BAT_PERCENTILE_BALLS = 100
BOWL_PERCENTILE_BALLS = 120
SEASONS = ("2022", "2023", "2024", "2025", "2026")
SPLIT_KEYS = (
    "career",
    "IPL",
    "T20I",
    "2022",
    "2023",
    "2024",
    "2025",
    "2026",
    "powerplay",
    "middle",
    "death",
    "innings1",
    "innings2",
    "vs_pace",
    "vs_spin",
    "vs_lhb",
    "vs_rhb",
    "pressure",
    "normal",
    "last5",
    "last10",
    "last20",
)
SPLIT_LABELS = {
    "career": "Career",
    "IPL": "IPL",
    "T20I": "T20I",
    "2022": "Season 2022",
    "2023": "Season 2023",
    "2024": "Season 2024",
    "2025": "Season 2025",
    "2026": "Season 2026",
    "powerplay": "Powerplay (overs 1-6)",
    "middle": "Middle overs (7-15)",
    "death": "Death overs (16-20)",
    "innings1": "Batting first (innings 1)",
    "innings2": "Chasing (innings 2)",
    "vs_pace": "Vs pace",
    "vs_spin": "Vs spin",
    "vs_lhb": "Vs left-hand batter",
    "vs_rhb": "Vs right-hand batter",
    "pressure": "Rule-based pressure",
    "normal": "Normal conditions",
    "last5": "Last 5 matches",
    "last10": "Last 10 matches",
    "last20": "Last 20 matches",
}

BAT_DEFINITIONS = {
    "matches": "Matches in which the player appeared in the XI within the split.",
    "innings": "Batting innings with at least one delivery as striker.",
    "not_outs": "Batting innings in which the striker was not dismissed.",
    "runs": "Bat runs only; wides, no-balls, byes and leg-byes are excluded.",
    "balls": "Balls faced: wides excluded, no-balls included (standard batter ball count).",
    "strike_rate": "Runs per 100 balls faced.",
    "average": "Runs divided by dismissals.",
    "highest": "Highest score in an innings in the split.",
    "thirties": "Scores from 30 to 49.",
    "fifties": "Scores from 50 to 99.",
    "hundreds": "Scores of 100 or more.",
    "ducks": "Dismissed for 0.",
    "golden_ducks": "Dismissed for 0 having faced at most one ball.",
    "fours": "Batter-hit fours.",
    "sixes": "Batter-hit sixes.",
    "boundary_pct": "Boundary runs (4s and 6s) as a share of bat runs.",
    "balls_per_boundary": "Balls faced per boundary hit.",
    "dot_pct": "Share of balls faced with zero bat runs.",
    "singles": "Balls scoring exactly one run.",
    "twos": "Balls scoring exactly two runs.",
    "threes": "Balls scoring exactly three runs.",
    "balls_per_dismissal": "Balls faced per dismissal.",
    "position": "Most used batting position in the XI within the split.",
    "entry": "Average entry point, in overs, at the first ball faced in an innings.",
}


def _id(value) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        number = float(value)
        if number.is_integer():
            return str(int(number))
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text or None


def _num(value):
    try:
        if value is None or pd.isna(value):
            return 0.0
    except (TypeError, ValueError):
        return 0.0
    return float(value)


def _int(value) -> int:
    return int(round(_num(value)))


def _round(value, digits=1):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math_isnan(number) or math_isinf(number):
        return None
    return round(number, digits)


def math_isnan(value: float) -> bool:
    return value != value


def math_isinf(value: float) -> bool:
    return value in (float("inf"), float("-inf"))


def _rate(numerator, denominator, factor=1.0):
    if not denominator:
        return None
    return _round(numerator / denominator * factor, 2 if factor == 1.0 else 1)


def _season_year(value):
    text = str(value or "").strip()
    return text[:4] if len(text) >= 4 and text[:4].isdigit() else None


def _sum(series) -> float:
    return float(pd.to_numeric(series, errors="coerce").fillna(0).sum())


def _prepare_frames(df: pd.DataFrame, appearances: pd.DataFrame):
    deliveries = df.copy()
    for col in (
        "batting_type",
        "pace_or_spin",
        "stroke",
        "on_or_off",
        "delivery_style",
        "over_or_around",
        "bowl_speed",
    ):
        if col not in deliveries.columns:
            deliveries[col] = np.nan
    deliveries["pid"] = deliveries["striker_id"].map(_id)
    deliveries["bowler_pid"] = deliveries["bowler_id"].map(_id)
    deliveries["match_id"] = deliveries["match_id"].map(_id)
    deliveries["season_year"] = deliveries["season"].map(_season_year)
    deliveries["pressure"] = deliveries["pressure"].fillna(False).astype(bool)
    deliveries["format"] = deliveries["format"].fillna("T20")
    deliveries["phase"] = deliveries["phase"].fillna("middle")

    balls = deliveries["ball_faced"].fillna(False).astype(bool)
    bat_runs = pd.to_numeric(deliveries["bat_runs"], errors="coerce").fillna(0)
    legal = deliveries["legal_ball"].fillna(False).astype(bool)
    extras_key = deliveries["extras_key"].fillna("").astype(str).str.lower()
    chargeable = extras_key.isin({"wide", "overstep", "other"})

    bat = pd.DataFrame(
        {
            "pid": deliveries["pid"],
            "match_id": deliveries["match_id"],
            "innings": deliveries["innings"],
            "overid": deliveries["overid"],
            "over_ball_num": deliveries["over_ball_num"],
            "match_date": deliveries["match_date"],
            "season": deliveries["season_year"],
            "format": deliveries["format"],
            "phase": deliveries["phase"],
            "pressure": deliveries["pressure"],
            "hand": deliveries["batting_type"].fillna("Unknown"),
            "pace": deliveries["pace_or_spin"].fillna("Unknown"),
            "stroke": deliveries["stroke"].fillna("Unknown"),
            "side": deliveries["on_or_off"].fillna("Unknown"),
            "balls": balls.astype(int),
            "runs": bat_runs,
            "fours": pd.to_numeric(deliveries["is_four"], errors="coerce").fillna(0).astype(int),
            "sixes": pd.to_numeric(deliveries["is_six"], errors="coerce").fillna(0).astype(int),
            "dismissed": deliveries["striker_dismissed"].fillna(False).astype(bool),
            "dismissal": deliveries["batter_dismissal"].fillna("Unknown"),
        }
    )
    bat = bat[bat["pid"].notna()].copy()
    bat["dot"] = (bat["balls"] > 0) & (bat["runs"] == 0)
    bat["single"] = bat["runs"] == 1
    bat["two"] = bat["runs"] == 2
    bat["three"] = bat["runs"] == 3
    bat["boundaries"] = bat["fours"] + bat["sixes"]
    bat["boundary_runs"] = bat["fours"] * 4 + bat["sixes"] * 6
    bat = bat.sort_values(
        ["pid", "match_id", "innings", "overid", "over_ball_num"], kind="stable"
    ).reset_index(drop=True)
    bat["ball_no"] = bat.groupby(["pid", "match_id", "innings"], sort=False)["balls"].cumsum()
    bat["entry_point"] = bat["overid"] + (bat["over_ball_num"] - 1).clip(lower=0) / 6.0
    bat["start_bucket"] = np.select(
        [bat["ball_no"] <= 10, bat["ball_no"] <= 20],
        ["first_10", "balls_11_20"],
        default="balls_21_plus",
    )

    bowl = pd.DataFrame(
        {
            "pid": deliveries["bowler_pid"],
            "match_id": deliveries["match_id"],
            "innings": deliveries["innings"],
            "overid": deliveries["overid"],
            "over_ball_num": deliveries["over_ball_num"],
            "match_date": deliveries["match_date"],
            "season": deliveries["season_year"],
            "format": deliveries["format"],
            "phase": deliveries["phase"],
            "pressure": deliveries["pressure"],
            "hand": deliveries["batting_type"].fillna("Unknown"),
            "pace": deliveries["pace_or_spin"].fillna("Unknown"),
            "style": deliveries["delivery_style"].fillna("Unknown"),
            "side": deliveries["on_or_off"].fillna("Unknown"),
            "angle": deliveries["over_or_around"].fillna("Unknown"),
            "legal": legal,
            "runs": pd.to_numeric(deliveries["bowler_runs"], errors="coerce").fillna(0),
            "wickets": deliveries["bowler_wicket"].fillna(False).astype(bool),
            "fours": pd.to_numeric(deliveries["is_four"], errors="coerce").fillna(0).astype(int),
            "sixes": pd.to_numeric(deliveries["is_six"], errors="coerce").fillna(0).astype(int),
            "wide": extras_key.eq("wide"),
            "no_ball": extras_key.eq("overstep"),
            "other": extras_key.eq("other"),
            "byes": extras_key.eq("byes"),
            "legbyes": extras_key.eq("legbyes"),
            "charged_extras": chargeable.astype(int)
            * (
                pd.to_numeric(deliveries["extras1_runs"], errors="coerce").fillna(0)
                + pd.to_numeric(deliveries["extras_2_runs"], errors="coerce").fillna(0)
            ),
            "byes_runs": extras_key.isin({"byes", "legbyes"}).astype(int)
            * (
                pd.to_numeric(deliveries["extras1_runs"], errors="coerce").fillna(0)
                + pd.to_numeric(deliveries["extras_2_runs"], errors="coerce").fillna(0)
            ),
            "speed": pd.to_numeric(deliveries["bowl_speed"], errors="coerce").fillna(0),
            "dismissal": deliveries["dismissal_type"].fillna("Unknown"),
        }
    )
    bowl = bowl[bowl["pid"].notna()].copy()
    bowl["dot"] = bowl["legal"] & (bowl["runs"] == 0)
    bowl = bowl.sort_values(
        ["pid", "match_id", "innings", "overid", "over_ball_num"], kind="stable"
    ).reset_index(drop=True)

    app = appearances.copy()
    if app.empty:
        app = pd.DataFrame(columns=["player_id", "match_id", "match_date"])
    app["player_id"] = app["player_id"].map(_id)
    app["match_id"] = app["match_id"].map(_id)
    app["season_year"] = app.get("season", pd.Series(index=app.index)).map(_season_year)
    app["format"] = app.get("format", pd.Series(index=app.index)).fillna("T20")
    app = app[app["player_id"].notna() & app["match_id"].notna()].copy()
    app["match_date"] = pd.to_datetime(app["match_date"], errors="coerce")
    for column in ("is_impact", "is_captain", "is_wk"):
        app[column] = app.get(column, 0)
        app[column] = pd.to_numeric(app[column], errors="coerce").fillna(0).astype(bool)
    for column in ("team_id", "win_team_id", "man_of_the_match", "batting_order"):
        app[column] = pd.to_numeric(app.get(column), errors="coerce")
    app["won"] = app["win_team_id"].notna() & app["win_team_id"].eq(app["team_id"])
    app["motm"] = app["man_of_the_match"].notna() & app["man_of_the_match"].eq(app["player_id"].astype(float))
    app = app.drop_duplicates(["player_id", "match_id"]).copy()
    app = app.sort_values(
        ["player_id", "match_date", "match_id"], ascending=[True, False, False], kind="stable"
    )
    app["recent_rank"] = app.groupby("player_id").cumcount() + 1
    bat = bat.merge(
        app[["player_id", "match_id", "recent_rank"]],
        left_on=["pid", "match_id"],
        right_on=["player_id", "match_id"],
        how="left",
    ).drop(columns=["player_id"])
    bowl = bowl.merge(
        app[["player_id", "match_id", "recent_rank"]],
        left_on=["pid", "match_id"],
        right_on=["player_id", "match_id"],
        how="left",
    ).drop(columns=["player_id"])
    return bat, bowl, app


def _scope_app(app: pd.DataFrame, bat: pd.DataFrame, bowl: pd.DataFrame) -> pd.DataFrame:
    pairs = pd.concat(
        [bat[["pid", "match_id"]], bowl[["pid", "match_id"]]], ignore_index=True
    ).drop_duplicates()
    pairs = pairs.rename(columns={"pid": "player_id"})
    return app.merge(pairs, on=["player_id", "match_id"], how="inner")


def _module_record(record: dict, keys) -> dict:
    return {key: record.get(key) for key in keys if key in record}


def _batting_agg(bat: pd.DataFrame, app: pd.DataFrame) -> dict[str, dict]:
    if bat.empty:
        return {}
    grouped = bat.groupby("pid", sort=False)
    totals = grouped.agg(
        balls=("balls", "sum"),
        runs=("runs", "sum"),
        fours=("fours", "sum"),
        sixes=("sixes", "sum"),
        dots=("dot", "sum"),
        dismissals=("dismissed", "sum"),
        singles=("single", "sum"),
        twos=("two", "sum"),
        threes=("three", "sum"),
        innings=("innings", "nunique"),
    )
    innings = (
        bat.groupby(["pid", "match_id", "innings"], sort=False)
        .agg(runs=("runs", "sum"), balls=("balls", "sum"), dismissed=("dismissed", "max"))
        .reset_index()
    )
    innings["dismissed"] = innings["dismissed"].astype(bool)
    innings["duck"] = (innings["runs"] == 0) & innings["dismissed"]
    innings["golden"] = innings["duck"] & (innings["balls"] <= 1)
    innings_group = innings.groupby("pid", sort=False)
    derived = pd.DataFrame(
        {
            "innings": innings_group.size(),
            "not_outs": innings_group["dismissed"].apply(lambda s: int((~s).sum())),
            "highest": innings_group["runs"].max(),
            "thirties": innings_group["runs"].apply(lambda s: int(((s >= 30) & (s < 50)).sum())),
            "fifties": innings_group["runs"].apply(lambda s: int(((s >= 50) & (s < 100)).sum())),
            "hundreds": innings_group["runs"].apply(lambda s: int((s >= 100).sum())),
            "ducks": innings_group["duck"].sum(),
            "golden_ducks": innings_group["golden"].sum(),
        }
    )
    entry = (
        bat.sort_values(["pid", "match_id", "innings", "overid", "over_ball_num"])
        .groupby(["pid", "match_id", "innings"], sort=False)
        .head(1)
        .groupby("pid")["entry_point"]
        .mean()
        .rename("entry")
    )
    positions = (
        app.dropna(subset=["batting_order"])
        .groupby(["player_id", "batting_order"], sort=False)
        .size()
        .reset_index(name="count")
        .sort_values(["player_id", "count", "batting_order"], ascending=[True, False, True])
        .drop_duplicates("player_id")
        .set_index("player_id")["batting_order"]
        .rename("position")
    )
    players = sorted(set(totals.index) | set(derived.index) | set(app["player_id"].dropna()))
    result = {}
    for pid in players:
        if pid not in totals.index and pid not in derived.index:
            continue
        row = totals.loc[pid] if pid in totals.index else pd.Series(dtype=float)
        extra = derived.loc[pid] if pid in derived.index else pd.Series(dtype=float)
        balls = _int(row.get("balls", 0))
        runs = _int(row.get("runs", 0))
        dismissals = _int(row.get("dismissals", 0))
        fours = _int(row.get("fours", 0))
        sixes = _int(row.get("sixes", 0))
        dots = _int(row.get("dots", 0))
        boundary_runs = fours * 4 + sixes * 6
        result[pid] = {
            "matches": 0,
            "innings": _int(extra.get("innings", row.get("innings", 0))),
            "not_outs": _int(extra.get("not_outs", 0)),
            "runs": runs,
            "balls": balls,
            "strike_rate": _rate(runs, balls, 100),
            "average": _rate(runs, dismissals),
            "highest": _int(extra.get("highest", 0)),
            "thirties": _int(extra.get("thirties", 0)),
            "fifties": _int(extra.get("fifties", 0)),
            "hundreds": _int(extra.get("hundreds", 0)),
            "ducks": _int(extra.get("ducks", 0)),
            "golden_ducks": _int(extra.get("golden_ducks", 0)),
            "fours": fours,
            "sixes": sixes,
            "boundary_pct": _rate(boundary_runs, runs, 100) if runs else None,
            "balls_per_boundary": _rate(balls, fours + sixes),
            "dot_pct": _rate(dots, balls, 100),
            "singles": _int(row.get("singles", 0)),
            "twos": _int(row.get("twos", 0)),
            "threes": _int(row.get("threes", 0)),
            "balls_per_dismissal": _rate(balls, dismissals),
            "position": None if pid not in positions.index or pd.isna(positions.loc[pid]) else _int(positions.loc[pid]),
            "entry": _round(entry.get(pid), 2),
            "small_sample": balls < SMALL_SAMPLE_BALLS,
        }
    return result


def _batting_details(bat: pd.DataFrame) -> dict[str, dict]:
    if bat.empty:
        return {}
    details: dict[str, dict] = {}

    def bucket_rows(frame, key, value_columns):
        out = {}
        for label, group in frame.groupby(key, sort=False):
            runs = _int(group["runs"].sum())
            balls = _int(group["balls"].sum())
            dismissal_count = _int(group["dismissed"].sum())
            row = {
                "runs": runs,
                "balls": balls,
                "dismissals": dismissal_count,
                "strike_rate": _rate(runs, balls, 100),
                "dot_pct": _rate(group["dot"].sum(), balls, 100),
            }
            for column in value_columns:
                row[column] = _int(group[column].sum())
            out[str(label)] = row
        return out

    dismissal_counts = (
        bat[bat["dismissed"]]
        .groupby(["pid", "dismissal"])
        .size()
        .reset_index(name="count")
    )
    stroke = (
        bat.groupby(["pid", "stroke"], sort=False)
        .agg(
            balls=("balls", "sum"),
            runs=("runs", "sum"),
            fours=("fours", "sum"),
            sixes=("sixes", "sum"),
            dismissals=("dismissed", "sum"),
        )
        .reset_index()
    )
    for pid, group in bat.groupby("pid", sort=False):
        entry = {
            "dismissal_types": {},
            "stroke": {},
            "side": {},
            "pace_spin": {},
            "start": {},
        }
        for _, row in dismissal_counts[dismissal_counts["pid"] == pid].iterrows():
            entry["dismissal_types"][str(row["dismissal"])] = _int(row["count"])
        for _, row in (
            stroke[stroke["pid"] == pid]
            .sort_values(["balls", "runs"], ascending=[False, False])
            .head(15)
            .iterrows()
        ):
            entry["stroke"][str(row["stroke"])] = {
                "balls": _int(row["balls"]),
                "runs": _int(row["runs"]),
                "boundaries": _int(row["fours"] + row["sixes"]),
                "dismissals": _int(row["dismissals"]),
            }
        entry["side"] = bucket_rows(group, "side", [])
        entry["pace_spin"] = bucket_rows(group, "pace", [])
        entry["start"] = {}
        for label, start_group in group.groupby("start_bucket", sort=False):
            runs = _int(start_group["runs"].sum())
            balls = _int(start_group["balls"].sum())
            entry["start"][str(label)] = {
                "runs": runs,
                "balls": balls,
                "dismissals": _int(start_group["dismissed"].sum()),
                "strike_rate": _rate(runs, balls, 100),
                "dot_pct": _rate(start_group["dot"].sum(), balls, 100),
            }
        details[pid] = entry
    return details


def _bowling_agg(bowl: pd.DataFrame) -> dict[str, dict]:
    if bowl.empty:
        return {}
    grouped = bowl.groupby("pid", sort=False)
    totals = grouped.agg(
        legal_balls=("legal", "sum"),
        runs=("runs", "sum"),
        wickets=("wickets", "sum"),
        dots=("dot", "sum"),
        fours=("fours", "sum"),
        sixes=("sixes", "sum"),
        wides=("wide", "sum"),
        no_balls=("no_ball", "sum"),
        other_extras=("other", "sum"),
        charged_extras=("charged_extras", "sum"),
        byes_legbyes=("byes_runs", "sum"),
        innings=("innings", "nunique"),
    )
    innings = (
        bowl.groupby(["pid", "match_id", "innings"], sort=False)
        .agg(
            legal_balls=("legal", "sum"),
            runs=("runs", "sum"),
            wickets=("wickets", "sum"),
        )
        .reset_index()
    )
    innings_group = innings.groupby("pid", sort=False)
    derived = pd.DataFrame(
        {
            "innings": innings_group.size(),
            "two_w": innings_group["wickets"].apply(lambda s: int((s >= 2).sum())),
            "three_w": innings_group["wickets"].apply(lambda s: int((s >= 3).sum())),
            "four_w": innings_group["wickets"].apply(lambda s: int((s >= 4).sum())),
            "five_w": innings_group["wickets"].apply(lambda s: int((s >= 5).sum())),
        }
    )
    best = (
        innings.sort_values(["pid", "wickets", "runs"], ascending=[True, False, True])
        .drop_duplicates("pid")
        .set_index("pid")
    )
    overs = (
        bowl.groupby(["pid", "match_id", "innings", "overid"], sort=False)
        .agg(legal=("legal", "sum"), runs=("runs", "sum"))
        .reset_index()
    )
    maidens = overs[(overs["legal"] >= 6) & (overs["runs"] == 0)].groupby("pid").size()
    rpo = (
        overs[overs["legal"] >= 6]
        .groupby(["pid", "runs"])
        .size()
        .reset_index(name="count")
    )
    first_over = (
        bowl[bowl["overid"] == 1]
        .groupby("pid", sort=False)
        .agg(
            innings=("innings", "nunique"),
            balls=("legal", "sum"),
            runs=("runs", "sum"),
            wickets=("wickets", "sum"),
            dots=("dot", "sum"),
        )
    )
    speed = (
        bowl[bowl["speed"] > 0]
        .groupby("pid", sort=False)["speed"]
        .agg(["count", "mean", "max"])
    )
    plausible = (
        bowl[(bowl["speed"] >= 50) & (bowl["speed"] <= 160)]
        .groupby("pid", sort=False)["speed"]
        .agg(["count", "mean", "max"])
    )
    players = set(totals.index)
    result = {}
    for pid in players:
        row = totals.loc[pid]
        extra = derived.loc[pid] if pid in derived.index else pd.Series(dtype=float)
        balls = _int(row["legal_balls"])
        runs = _int(row["runs"])
        wickets = _int(row["wickets"])
        record = {
            "matches": 0,
            "innings": _int(extra.get("innings", row["innings"])),
            "legal_balls": balls,
            "overs": f"{balls // 6}.{balls % 6}",
            "runs": runs,
            "wickets": wickets,
            "economy": _rate(runs, balls / 6),
            "average": _rate(runs, wickets),
            "strike_rate": _rate(balls, wickets),
            "dot_pct": _rate(row["dots"], balls, 100),
            "fours": _int(row["fours"]),
            "sixes": _int(row["sixes"]),
            "balls_per_boundary": _rate(balls, int(row["fours"] + row["sixes"])),
            "wides": _int(row["wides"]),
            "no_balls": _int(row["no_balls"]),
            "other_extras": _int(row["other_extras"]),
            "total_extras": _int(row["charged_extras"]),
            "byes_legbyes": _int(row["byes_legbyes"]),
            "extras_per_match": None,
            "maidens": _int(maidens.get(pid, 0)),
            "best": None,
            "two_w": _int(extra.get("two_w", 0)),
            "three_w": _int(extra.get("three_w", 0)),
            "four_w": _int(extra.get("four_w", 0)),
            "five_w": _int(extra.get("five_w", 0)),
            "small_sample": balls < SMALL_SAMPLE_BALLS,
        }
        if pid in best.index:
            best_row = best.loc[pid]
            record["best"] = {
                "wickets": _int(best_row["wickets"]),
                "runs": _int(best_row["runs"]),
                "balls": _int(best_row["legal_balls"]),
            }
        if pid in speed.index:
            speed_row = speed.loc[pid]
            plausible_row = plausible.loc[pid] if pid in plausible.index else None
            record["speed"] = {
                "n": _int(speed_row["count"]),
                "average": _round(speed_row["mean"], 1),
                "max": _round(speed_row["max"], 1),
                "plausible_n": _int(plausible_row["count"]) if plausible_row is not None else 0,
                "plausible_average": _round(plausible_row["mean"], 1) if plausible_row is not None else None,
                "plausible_max": _round(plausible_row["max"], 1) if plausible_row is not None else None,
            }
        if pid in first_over.index:
            first = first_over.loc[pid]
            record["first_over"] = {
                "innings": _int(first["innings"]),
                "balls": _int(first["balls"]),
                "runs": _int(first["runs"]),
                "wickets": _int(first["wickets"]),
                "economy": _rate(first["runs"], first["balls"] / 6),
                "dot_pct": _rate(first["dots"], first["balls"], 100),
            }
        if pid in rpo["pid"].values:
            distribution = rpo[rpo["pid"] == pid]
            record["runs_per_over"] = [
                {"runs": _int(r), "count": _int(c)}
                for r, c in distribution.sort_values("runs")[["runs", "count"]].itertuples(index=False)
            ]
        result[pid] = record
    return result


def _bowling_details(bowl: pd.DataFrame) -> dict[str, dict]:
    if bowl.empty:
        return {}
    details: dict[str, dict] = {}
    wicket_types = (
        bowl[bowl["wickets"]]
        .groupby(["pid", "dismissal"])
        .size()
        .reset_index(name="count")
    )

    def grouped_table(frame, key):
        out = {}
        for label, group in frame.groupby(key, sort=False):
            balls = _int(group["legal"].sum())
            runs = _int(group["runs"].sum())
            out[str(label)] = {
                "balls": balls,
                "runs": runs,
                "wickets": _int(group["wickets"].sum()),
                "economy": _rate(runs, balls / 6),
                "dot_pct": _rate(group["dot"].sum(), balls, 100),
            }
        return out

    for pid, group in bowl.groupby("pid", sort=False):
        entry = {
            "wicket_types": {
                str(row["dismissal"]): _int(row["count"])
                for _, row in wicket_types[wicket_types["pid"] == pid].iterrows()
            },
            "style": {},
            "side": {},
            "angle": {},
        }
        style = grouped_table(group, "style")
        entry["style"] = dict(
            sorted(style.items(), key=lambda item: item[1]["balls"], reverse=True)[:10]
        )
        entry["side"] = grouped_table(group, "side")
        entry["angle"] = grouped_table(group, "angle")
        details[pid] = entry
    return details


def _context(app: pd.DataFrame) -> dict[str, dict]:
    if app.empty:
        return {}
    grouped = app.groupby("player_id", sort=False)
    rows = grouped.agg(
        matches=("match_id", "nunique"),
        man_of_the_match=("motm", "sum"),
        matches_won=("won", "sum"),
        impact_matches=("is_impact", "sum"),
        captain_matches=("is_captain", "sum"),
        wk_matches=("is_wk", "sum"),
    )
    result = {}
    for pid, row in rows.iterrows():
        matches = _int(row["matches"])
        wins = _int(row["matches_won"])
        result[pid] = {
            "matches": matches,
            "man_of_the_match": _int(row["man_of_the_match"]),
            "matches_won": wins,
            "win_pct": _rate(wins, matches, 100),
            "impact_matches": _int(row["impact_matches"]),
            "captain_matches": _int(row["captain_matches"]),
            "wk_matches": _int(row["wk_matches"]),
        }
    return result


def _apply_matches(batting: dict, bowling: dict, context: dict) -> None:
    for record in (batting, bowling):
        if not record:
            continue
        record["matches"] = context.get("matches", 0)
        record["man_of_the_match"] = context.get("man_of_the_match", 0)
        record["matches_won"] = context.get("matches_won", 0)
        record["win_pct"] = context.get("win_pct")
        record["impact_matches"] = context.get("impact_matches", 0)
        record["captain_matches"] = context.get("captain_matches", 0)
        record["wk_matches"] = context.get("wk_matches", 0)
    if bowling:
        matches = bowling.get("matches") or 0
        bowling["extras_per_match"] = _rate(
            (bowling.get("total_extras") or 0)
            + (bowling.get("byes_legbyes") or 0),
            matches,
            1,
        )


def _aggregate(bat: pd.DataFrame, bowl: pd.DataFrame, app: pd.DataFrame) -> dict[str, dict]:
    batting = _batting_agg(bat, app)
    bowling = _bowling_agg(bowl)
    bat_details = _batting_details(bat)
    bowl_details = _bowling_details(bowl)
    context = _context(app)
    players = set(batting) | set(bowling) | set(context)
    result = {}
    for pid in players:
        bat_record = batting.get(pid)
        bowl_record = bowling.get(pid)
        ctx = context.get(pid, {})
        _apply_matches(bat_record, bowl_record, ctx)
        if bat_record is not None:
            bat_record.update(bat_details.get(pid, {}))
        if bowl_record is not None:
            bowl_record.update(bowl_details.get(pid, {}))
        result[pid] = {"batting": bat_record, "bowling": bowl_record}
    return result


def _split_frames(key: str, bat: pd.DataFrame, bowl: pd.DataFrame, app: pd.DataFrame):
    if key == "career":
        return bat, bowl, app
    if key in ("IPL", "T20I"):
        return (
            bat[bat["format"] == key],
            bowl[bowl["format"] == key],
            app[app["format"] == key],
        )
    if key in SEASONS:
        return (
            bat[bat["season"] == key],
            bowl[bowl["season"] == key],
            app[app["season_year"] == key],
        )
    if key in ("powerplay", "middle", "death"):
        bat_sub = bat[bat["phase"] == key]
        bowl_sub = bowl[bowl["phase"] == key]
        return bat_sub, bowl_sub, _scope_app(app, bat_sub, bowl_sub)
    if key in ("innings1", "innings2"):
        innings = 1 if key == "innings1" else 2
        bat_sub = bat[bat["innings"] == innings]
        bowl_sub = bowl[bowl["innings"] == innings]
        return bat_sub, bowl_sub, _scope_app(app, bat_sub, bowl_sub)
    if key == "vs_pace":
        bat_sub = bat[bat["pace"] == "Pace"]
        bowl_sub = bowl[bowl["pace"] == "Pace"]
        return bat_sub, bowl_sub, _scope_app(app, bat_sub, bowl_sub)
    if key == "vs_spin":
        bat_sub = bat[bat["pace"] == "Spin"]
        bowl_sub = bowl[bowl["pace"] == "Spin"]
        return bat_sub, bowl_sub, _scope_app(app, bat_sub, bowl_sub)
    if key == "vs_lhb":
        bat_sub = bat.iloc[0:0]
        bowl_sub = bowl[bowl["hand"] == "LHB"]
        return bat_sub, bowl_sub, _scope_app(app, bat_sub, bowl_sub)
    if key == "vs_rhb":
        bat_sub = bat.iloc[0:0]
        bowl_sub = bowl[bowl["hand"] == "RHB"]
        return bat_sub, bowl_sub, _scope_app(app, bat_sub, bowl_sub)
    if key == "pressure":
        bat_sub = bat[bat["pressure"]]
        bowl_sub = bowl[bowl["pressure"]]
        return bat_sub, bowl_sub, _scope_app(app, bat_sub, bowl_sub)
    if key == "normal":
        bat_sub = bat[~bat["pressure"]]
        bowl_sub = bowl[~bowl["pressure"]]
        return bat_sub, bowl_sub, _scope_app(app, bat_sub, bowl_sub)
    if key in ("last5", "last10", "last20"):
        limit = int(key.replace("last", ""))
        bat_sub = bat[bat["recent_rank"] <= limit]
        bowl_sub = bowl[bowl["recent_rank"] <= limit]
        app_sub = app[app["recent_rank"] <= limit]
        return bat_sub, bowl_sub, app_sub
    return bat.iloc[0:0], bowl.iloc[0:0], app.iloc[0:0]


def _payload(pid, career, splits, name, team, role):
    return {
        "player_id": int(pid) if str(pid).isdigit() else pid,
        "name": name,
        "latest_team": team,
        "role": role,
        "small_sample_threshold_balls": SMALL_SAMPLE_BALLS,
        "splits": splits,
        "notes": {
            "fielding": "No fielding statistics: the supplied data has no fielder IDs.",
            "pressure": (
                "The pressure split is descriptive and rule-based. It is separate from the "
                "supplied headline composite rank and score, which are never recomputed."
            ),
            "legal_balls": "Wides and Overstep (no-balls) are not legal balls.",
            "batter_runs": "Batters receive bat runs only.",
            "bowler_runs": (
                "Bowlers are charged bat runs plus extras1 on wides, Overstep and other extras; "
                "byes, leg-byes and penalties are not charged."
            ),
            "wickets": "Run-outs, retired-out and obstructing the field are not bowler wickets.",
            "exclusions": (
                "Super overs (innings 3 and 4), the two Emerging tournaments, and "
                "DLS/shortened matches are excluded."
            ),
            "percentiles": (
                "Percentiles compare the selected split with career values of qualified players "
                f"(batters: >= {BAT_PERCENTILE_BALLS} balls; bowlers: >= {BOWL_PERCENTILE_BALLS} legal balls)."
            ),
        },
        "definitions": {
            "batting": BAT_DEFINITIONS,
            "bowling": {
                "matches": "Matches in which the player appeared in the XI within the split.",
                "innings": "Bowling innings with at least one delivery.",
                "legal_balls": "Deliveries that are not wides or Overstep no-balls.",
                "overs": "Overs in cricket 12.3 notation.",
                "runs": "Bat runs plus chargeable extras (wides, Overstep, other).",
                "wickets": "Bowler-credited dismissals only.",
                "economy": "Runs conceded per over.",
                "average": "Runs conceded per wicket.",
                "strike_rate": "Legal balls per wicket.",
                "dot_pct": "Legal balls with no runs charged.",
                "maidens": "Complete six-ball overs with zero runs charged.",
                "best": "Best innings figures, wickets first then runs.",
                "speed": "Recorded bowl_speed values greater than zero; plausible range 50-160 km/h shown separately.",
            },
        },
    }


def compute_stats(
    df: pd.DataFrame,
    appearances: pd.DataFrame,
    latest_names: dict | None = None,
    name_fallback: dict | None = None,
    overlay: dict | None = None,
) -> tuple[dict[str, dict], list[dict], dict]:
    """Return per-player payloads, an index and metadata.

    ``df`` must be the prepared delivery table from ``precompute.prepare_deliveries``.
    """
    latest_names = latest_names or {}
    name_fallback = name_fallback or {}
    overlay = overlay or {}
    bat, bowl, app = _prepare_frames(df, appearances)
    split_results = {}
    for key in SPLIT_KEYS:
        bat_sub, bowl_sub, app_sub = _split_frames(key, bat, bowl, app)
        split_results[key] = _aggregate(bat_sub, bowl_sub, app_sub)

    all_players = set(split_results["career"])
    app_all = app.drop_duplicates(["player_id", "match_id"])
    seasons = (
        app_all.dropna(subset=["season_year"])
        .groupby("player_id")["season_year"]
        .apply(lambda s: sorted(set(str(v) for v in s)))
        .to_dict()
    )
    competitions = (
        app_all.groupby("player_id")["format"]
        .apply(lambda s: sorted(set(str(v) for v in s if str(v) in {"IPL", "T20I"})))
        .to_dict()
    )
    latest = (
        app_all.sort_values(["player_id", "match_date", "match_id"])
        .drop_duplicates("player_id", keep="last")
        .set_index("player_id")
    )
    players: dict[str, dict] = {}
    index_rows = []
    for pid in sorted(all_players, key=lambda value: latest_names.get(value) or name_fallback.get(value) or value):
        career = split_results["career"].get(pid) or {}
        if not career.get("batting") and not career.get("bowling"):
            continue
        name = latest_names.get(pid) or name_fallback.get(pid) or f"Player {pid}"
        team = None
        if pid in latest.index and pd.notna(latest.loc[pid].get("player_team")):
            team = str(latest.loc[pid]["player_team"])
        role_info = overlay.get(pid, {})
        role = role_info.get("ranked_role")
        if not role:
            batting_balls = (career.get("batting") or {}).get("balls") or 0
            bowling_balls = (career.get("bowling") or {}).get("legal_balls") or 0
            role = "both" if batting_balls >= 60 and bowling_balls >= 60 else (
                "bowler" if bowling_balls > batting_balls else "batter"
            )
        splits = {}
        for key in SPLIT_KEYS:
            record = split_results[key].get(pid)
            if not record:
                continue
            batting = record.get("batting")
            bowling = record.get("bowling")
            if not batting and not bowling:
                continue
            splits[key] = {
                "label": SPLIT_LABELS[key],
                "batting": batting,
                "bowling": bowling,
            }
        players[pid] = _payload(pid, career, splits, name, team, role)
        index_rows.append(
            {
                "player_id": int(pid) if str(pid).isdigit() else pid,
                "name": name,
                "role": role,
                "latest_team": team,
                "seasons": seasons.get(pid, []),
                "competitions": competitions.get(pid, []),
                "batting": career.get("batting"),
                "bowling": career.get("bowling"),
                "ranked_role": role_info.get("ranked_role"),
                "ranked_rank": role_info.get("ranked_rank"),
            }
        )
    meta = {
        "players": len(players),
        "splits": len(SPLIT_KEYS),
        "small_sample_threshold_balls": SMALL_SAMPLE_BALLS,
        "bat_percentile_balls": BAT_PERCENTILE_BALLS,
        "bowl_percentile_balls": BOWL_PERCENTILE_BALLS,
        "definitions": {"batting": BAT_DEFINITIONS},
    }
    return players, index_rows, meta


def build_stats(
    df: pd.DataFrame,
    appearances: pd.DataFrame,
    out_dir: str | Path,
    latest_names: dict | None = None,
    name_fallback: dict | None = None,
    overlay: dict | None = None,
) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.json"):
        stale.unlink()
    players, index_rows, meta = compute_stats(
        df, appearances, latest_names=latest_names, name_fallback=name_fallback, overlay=overlay
    )
    for pid, payload in players.items():
        (out_dir / f"{pid}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
            encoding="utf-8",
        )
    (out_dir / "index.json").write_text(
        json.dumps(
            {
                "generated_at": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "players": index_rows,
                "options": {
                    "teams": sorted({row["latest_team"] for row in index_rows if row["latest_team"]}),
                    "seasons": sorted({season for row in index_rows for season in row["seasons"]}),
                    "competitions": sorted(
                        {
                            competition
                            for row in index_rows
                            for competition in row["competitions"]
                        }
                    ),
                    "roles": sorted({row["role"] for row in index_rows}),
                },
                "meta": meta,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta
