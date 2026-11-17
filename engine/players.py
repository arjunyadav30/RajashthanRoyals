"""Per-player pressure aggregates from delivery-level impacts."""

from __future__ import annotations

import numpy as np
import pandas as pd

from precompute import _canon_id

from engine.config import PHASE_LABELS

PRESS_FLAGS = {
    70: "pressure_leverage_70",
    75: "pressure_leverage_75",
    80: "pressure_leverage_80",
}


def _rate_per_100(total, balls):
    if balls is None or balls <= 0:
        return 0.0
    return 100.0 * float(total) / float(balls)


def _pct(total, balls):
    if balls is None or balls <= 0:
        return None
    return round(100.0 * float(total) / float(balls), 1)


def _phase_role(phase: str | None, role: str) -> str:
    if phase is None:
        return "Unclassified batter" if role == "batter" else "Unclassified bowler"
    label = PHASE_LABELS.get(phase, phase)
    if role == "batter":
        return {"Powerplay": "Powerplay batter", "Middle": "Middle-overs batter", "Death": "Finisher"}.get(
            label, f"{label} batter"
        )
    return f"{label} bowler"


def _dominant(counts: pd.DataFrame, fallback: pd.DataFrame | None, pid) -> str | None:
    if counts is not None and pid in counts.index:
        row = counts.loc[pid]
        if row.sum() > 0:
            return str(row.idxmax())
    if fallback is not None and pid in fallback.index:
        row = fallback.loc[pid]
        if row.sum() > 0:
            return str(row.idxmax())
    return None


def _bat_facts(df: pd.DataFrame, pressure_col: str):
    faced = df[df["striker_id"].notna() & df["ball_faced"].fillna(False).astype(bool)].copy()
    faced["pid"] = faced["striker_id"].map(_canon_id)
    faced = faced[faced["pid"].notna()].copy()
    faced["pressure"] = faced[pressure_col].fillna(False).astype(bool)
    faced["impact"] = faced["bat_impact"].fillna(0.0)
    faced["dot"] = faced["bat_runs"].fillna(0).eq(0)
    faced["fours"] = faced["is_four"].fillna(False).astype(int)
    faced["sixes"] = faced["is_six"].fillna(False).astype(int)
    faced["boundaries"] = faced["fours"] + faced["sixes"]
    faced["dismissed"] = faced["striker_dismissed"].fillna(False).astype(int)
    faced["exp_runs"] = faced["exp_bat_runs"].fillna(0.0)
    faced["is_pressure"] = faced["pressure"].astype(int)

    wpa = df[df["striker_id"].notna()].copy()
    wpa["pid"] = wpa["striker_id"].map(_canon_id)
    wpa = wpa[wpa["pid"].notna()].copy()
    wpa["pressure"] = wpa[pressure_col].fillna(False).astype(bool)
    wpa["wpa"] = wpa["wpa"].fillna(0.0)
    wpa_player = wpa[wpa["pressure"]].groupby("pid")["wpa"].sum()
    wpa_league = (
        wpa[wpa["pressure"]]
        .groupby(["pid", "league"])["wpa"]
        .sum()
        .unstack(fill_value=0.0)
    )

    total = faced.groupby("pid").agg(
        balls=("impact", "size"),
        runs=("bat_runs", "sum"),
        fours=("fours", "sum"),
        sixes=("sixes", "sum"),
        dots=("dot", "sum"),
        dismissals=("dismissed", "sum"),
        impact=("impact", "sum"),
        exp_runs=("exp_runs", "sum"),
        matches=("match_id", "nunique"),
    )
    pressure = faced[faced["pressure"]].groupby("pid").agg(
        pressure_balls=("impact", "size"),
        pressure_runs=("bat_runs", "sum"),
        pressure_fours=("fours", "sum"),
        pressure_sixes=("sixes", "sum"),
        pressure_dots=("dot", "sum"),
        pressure_dismissals=("dismissed", "sum"),
        pressure_impact=("impact", "sum"),
        pressure_expected=("exp_runs", "sum"),
        pressure_matches=("match_id", "nunique"),
    )
    normal = faced[~faced["pressure"]].groupby("pid").agg(
        normal_balls=("impact", "size"),
        normal_impact=("impact", "sum"),
    )
    pressure_league = (
        faced[faced["pressure"]]
        .groupby(["pid", "league"])
        .agg(balls=("impact", "size"), impact=("impact", "sum"))
    )

    phase_pressure = (
        faced[faced["pressure"]].groupby(["pid", "phase"]).size().unstack(fill_value=0)
    )
    phase_all = faced.groupby(["pid", "phase"]).size().unstack(fill_value=0)

    pm_pressure = faced[faced["pressure"]].groupby(["pid", "match_id"]).agg(
        impact_sum=("impact", "sum"), balls=("impact", "size")
    )
    wpa_pm = (
        wpa[wpa["pressure"]]
        .groupby(["pid", "match_id"])["wpa"]
        .sum()
        .rename("wpa_sum")
    )
    pm_pressure = pm_pressure.join(wpa_pm, how="left")
    pm_pressure["wpa_sum"] = pm_pressure["wpa_sum"].fillna(0.0)
    pm_pressure["positive"] = (pm_pressure["impact_sum"] > 0).astype(int)
    pm_pressure["role"] = "batter"

    pm_normal = faced[~faced["pressure"]].groupby(["pid", "match_id"]).agg(
        normal_impact_sum=("impact", "sum"), normal_balls=("impact", "size")
    )

    return {
        "total": total,
        "pressure": pressure,
        "normal": normal,
        "pressure_league": pressure_league,
        "wpa_player": wpa_player,
        "wpa_league": wpa_league,
        "phase_pressure": phase_pressure,
        "phase_all": phase_all,
        "pm_pressure": pm_pressure,
        "pm_normal": pm_normal,
        "ball_values": faced,
    }


def _bowl_facts(df: pd.DataFrame, pressure_col: str):
    legal = df[df["bowler_id"].notna() & df["legal_ball"].fillna(False).astype(bool)].copy()
    legal["pid"] = legal["bowler_id"].map(_canon_id)
    legal = legal[legal["pid"].notna()].copy()
    legal["pressure"] = legal[pressure_col].fillna(False).astype(bool)
    legal["impact"] = legal["bowl_impact_q"].fillna(0.0)
    legal["dot"] = legal["bowler_runs"].fillna(0).eq(0)
    legal["fours"] = legal["is_four"].fillna(False).astype(int)
    legal["sixes"] = legal["is_six"].fillna(False).astype(int)
    legal["wickets"] = legal["bowler_wicket"].fillna(False).astype(int)
    legal["exp_runs"] = legal["exp_bowl_runs"].fillna(0.0)

    all_bowl = df[df["bowler_id"].notna()].copy()
    all_bowl["pid"] = all_bowl["bowler_id"].map(_canon_id)
    all_bowl = all_bowl[all_bowl["pid"].notna()].copy()
    all_bowl["extras_key"] = all_bowl["extras_key"].fillna("").astype(str)
    extras = all_bowl.groupby("pid").agg(
        wides=("extras_key", lambda s: int((s == "wide").sum())),
        no_balls=("extras_key", lambda s: int((s == "overstep").sum())),
        other_extras=("extras_key", lambda s: int((s == "other").sum())),
        matches=("match_id", "nunique"),
    )

    total = legal.groupby("pid").agg(
        legal_balls=("impact", "size"),
        runs=("bowler_runs", "sum"),
        wickets=("wickets", "sum"),
        dots=("dot", "sum"),
        fours=("fours", "sum"),
        sixes=("sixes", "sum"),
        exp_runs=("exp_runs", "sum"),
    )
    pressure = legal[legal["pressure"]].groupby("pid").agg(
        pressure_balls=("impact", "size"),
        pressure_runs=("bowler_runs", "sum"),
        pressure_wickets=("wickets", "sum"),
        pressure_dots=("dot", "sum"),
        pressure_fours=("fours", "sum"),
        pressure_sixes=("sixes", "sum"),
        pressure_impact=("impact", "sum"),
        pressure_expected=("exp_runs", "sum"),
        pressure_matches=("match_id", "nunique"),
    )
    normal = legal[~legal["pressure"]].groupby("pid").agg(
        normal_balls=("impact", "size"),
        normal_impact=("impact", "sum"),
    )
    pressure_league = (
        legal[legal["pressure"]]
        .groupby(["pid", "league"])
        .agg(balls=("impact", "size"), impact=("impact", "sum"), runs=("bowler_runs", "sum"))
    )
    wpa = legal[legal["pressure"]].groupby("pid")["wpa"].sum()
    wpa_league = (
        legal[legal["pressure"]]
        .groupby(["pid", "league"])["wpa"]
        .sum()
        .unstack(fill_value=0.0)
    )

    phase_pressure = legal[legal["pressure"]].groupby(["pid", "phase"]).size().unstack(fill_value=0)
    phase_all = legal.groupby(["pid", "phase"]).size().unstack(fill_value=0)

    pm_pressure = legal[legal["pressure"]].groupby(["pid", "match_id"]).agg(
        impact_sum=("impact", "sum"), balls=("impact", "size")
    )
    wpa_pm = (
        legal[legal["pressure"]]
        .groupby(["pid", "match_id"])["wpa"]
        .sum()
        .rename("wpa_sum")
        .mul(-1.0)
    )
    pm_pressure = pm_pressure.join(wpa_pm, how="left")
    pm_pressure["wpa_sum"] = pm_pressure["wpa_sum"].fillna(0.0)
    pm_pressure["positive"] = (pm_pressure["impact_sum"] > 0).astype(int)
    pm_pressure["role"] = "bowler"

    pm_normal = legal[~legal["pressure"]].groupby(["pid", "match_id"]).agg(
        normal_impact_sum=("impact", "sum"), normal_balls=("impact", "size")
    )

    return {
        "total": total,
        "pressure": pressure,
        "normal": normal,
        "pressure_league": pressure_league,
        "wpa": wpa,
        "wpa_league": wpa_league,
        "phase_pressure": phase_pressure,
        "phase_all": phase_all,
        "pm_pressure": pm_pressure,
        "pm_normal": pm_normal,
        "extras": extras,
    }


def _finish_batting(df, facts, players_meta) -> pd.DataFrame:
    total = facts["total"]
    pressure = facts["pressure"].reindex(total.index).fillna(0)
    normal = facts["normal"].reindex(total.index).fillna(0)
    rows = []
    phase_counts = facts["phase_pressure"]
    phase_all = facts["phase_all"]
    league_press = facts["pressure_league"]
    wpa_player = facts["wpa_player"]
    wpa_league = facts["wpa_league"]
    for pid in total.index:
        balls = int(pressure.loc[pid, "pressure_balls"])
        press = pressure.loc[pid]
        has_pressure = balls > 0
        pressure_impact = float(press["pressure_impact"])
        normal_balls = int(normal.loc[pid, "normal_balls"])
        normal_impact = float(normal.loc[pid, "normal_impact"])
        impact100 = _rate_per_100(pressure_impact, balls) if has_pressure else None
        normal100 = _rate_per_100(normal_impact, normal_balls)
        wpa_value = float(wpa_player.get(pid, 0.0))
        wpa100 = _rate_per_100(wpa_value, balls) if has_pressure else None
        phase = _dominant(phase_counts, phase_all, pid)
        ipl_balls = int(league_press.loc[(pid, "IPL"), "balls"]) if (pid, "IPL") in league_press.index else 0
        t20_balls = int(league_press.loc[(pid, "T20I"), "balls"]) if (pid, "T20I") in league_press.index else 0
        ipl_imp = float(league_press.loc[(pid, "IPL"), "impact"]) if (pid, "IPL") in league_press.index else 0.0
        t20_imp = float(league_press.loc[(pid, "T20I"), "impact"]) if (pid, "T20I") in league_press.index else 0.0
        ipl_wpa = float(wpa_league.loc[pid, "IPL"]) if pid in wpa_league.index and "IPL" in wpa_league.columns else 0.0
        t20_wpa = float(wpa_league.loc[pid, "T20I"]) if pid in wpa_league.index and "T20I" in wpa_league.columns else 0.0
        meta = players_meta.get(pid, {})
        rows.append(
            {
                "player_id": pid,
                "name": meta.get("name"),
                "player_type": "batter",
                "role": _phase_role(phase, "batter"),
                "dominant_phase": phase,
                "matches": int(total.loc[pid, "matches"]),
                "pressure_balls": balls,
                "IPL_balls": ipl_balls,
                "T20I_balls": t20_balls,
                "pressure_matches": int(press["pressure_matches"]),
                "impact100": round(impact100, 2) if impact100 is not None else None,
                "normal_impact": round(normal100, 2),
                "delta": round(impact100 - normal100, 2) if impact100 is not None else None,
                "wpa100": round(wpa100, 3) if wpa100 is not None else None,
                "pressure_impact": round(pressure_impact, 3),
                "pressure_wpa": round(wpa_value, 3),
                "pressure_expected": round(float(press["pressure_expected"]), 3),
                "pressure_runs": int(press["pressure_runs"]),
                "pressure": int(press["pressure_runs"]),
                "runs": int(press["pressure_runs"]),
                "fours": int(press["pressure_fours"]),
                "sixes": int(press["pressure_sixes"]),
                "boundaries": int(press["pressure_fours"] + press["pressure_sixes"]),
                "dots": int(press["pressure_dots"]),
                "dismissals": int(press["pressure_dismissals"]),
                "strike_rate": _pct(press["pressure_runs"], balls),
                "run_rate": _pct(press["pressure_runs"], balls),
                "dots_pct": _pct(press["pressure_dots"], balls),
                "boundaries_pct": _pct(press["pressure_fours"] + press["pressure_sixes"], balls),
                "wickets_pct": _pct(press["pressure_dismissals"], balls),
                "wickets": int(press["pressure_dismissals"]),
                "expected100": _pct(press["pressure_expected"], balls),
                "economy": None,
                "economy_above_expected": None,
                "IPL_impact100": round(_rate_per_100(ipl_imp, ipl_balls), 2),
                "T20I_impact100": round(_rate_per_100(t20_imp, t20_balls), 2),
                "IPL_wpa100": round(_rate_per_100(ipl_wpa, ipl_balls), 3),
                "T20I_wpa100": round(_rate_per_100(t20_wpa, t20_balls), 3),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    # Consistency inputs from pressure match rows.
    pm = facts["pm_pressure"]
    positive = pm.groupby("pid")["positive"].sum()
    exposed = pm.groupby("pid").size()
    frame["positive_matches"] = frame["player_id"].map(positive).fillna(0).astype(int)
    frame["exposed_matches"] = frame["player_id"].map(exposed).fillna(0).astype(int)
    frame["consistency"] = (frame["positive_matches"] + 2) / (frame["exposed_matches"] + 4)
    return frame.reset_index(drop=True)


def _finish_bowling(df, facts, players_meta) -> pd.DataFrame:
    total = facts["total"]
    pressure = facts["pressure"].reindex(total.index).fillna(0)
    normal = facts["normal"].reindex(total.index).fillna(0)
    rows = []
    phase_counts = facts["phase_pressure"]
    phase_all = facts["phase_all"]
    league_press = facts["pressure_league"]
    wpa_player = facts["wpa"]
    wpa_league = facts["wpa_league"]
    extras = facts["extras"]
    for pid in total.index:
        balls = int(pressure.loc[pid, "pressure_balls"])
        press = pressure.loc[pid]
        has_pressure = balls > 0
        pressure_impact = float(press["pressure_impact"])
        normal_balls = int(normal.loc[pid, "normal_balls"])
        normal_impact = float(normal.loc[pid, "normal_impact"])
        impact100 = _rate_per_100(pressure_impact, balls) if has_pressure else None
        normal100 = _rate_per_100(normal_impact, normal_balls)
        economy = press["pressure_runs"] / balls * 6.0 if has_pressure else None
        expected_econ = press["pressure_expected"] / balls * 6.0 if has_pressure else None
        wpa_value = float(wpa_player.get(pid, 0.0))
        # WPA for bowlers is the negative of the batting-side change.
        wpa100 = -_rate_per_100(wpa_value, balls) if has_pressure else None
        phase = _dominant(phase_counts, phase_all, pid)
        ipl_balls = int(league_press.loc[(pid, "IPL"), "balls"]) if (pid, "IPL") in league_press.index else 0
        t20_balls = int(league_press.loc[(pid, "T20I"), "balls"]) if (pid, "T20I") in league_press.index else 0
        ipl_imp = float(league_press.loc[(pid, "IPL"), "impact"]) if (pid, "IPL") in league_press.index else 0.0
        t20_imp = float(league_press.loc[(pid, "T20I"), "impact"]) if (pid, "T20I") in league_press.index else 0.0
        ipl_wpa = float(wpa_league.loc[pid, "IPL"]) if pid in wpa_league.index and "IPL" in wpa_league.columns else 0.0
        t20_wpa = float(wpa_league.loc[pid, "T20I"]) if pid in wpa_league.index and "T20I" in wpa_league.columns else 0.0
        meta = players_meta.get(pid, {})
        rows.append(
            {
                "player_id": pid,
                "name": meta.get("name"),
                "player_type": "bowler",
                "role": _phase_role(phase, "bowler"),
                "dominant_phase": phase,
                "matches": int(extras.loc[pid, "matches"]) if pid in extras.index else 0,
                "pressure_balls": balls,
                "IPL_balls": ipl_balls,
                "T20I_balls": t20_balls,
                "pressure_matches": int(press["pressure_matches"]),
                "impact100": round(impact100, 2) if impact100 is not None else None,
                "normal_impact": round(normal100, 2),
                "delta": round(impact100 - normal100, 2) if impact100 is not None else None,
                "wpa100": round(wpa100, 3) if wpa100 is not None else None,
                "pressure_impact": round(pressure_impact, 3),
                "pressure_wpa": round(-wpa_value, 3),
                "pressure_expected": round(float(press["pressure_expected"]), 3),
                "pressure_runs": int(press["pressure_runs"]),
                "runs": int(press["pressure_runs"]),
                "pressure_wickets": int(press["pressure_wickets"]),
                "wickets": int(press["pressure_wickets"]),
                "dots": int(press["pressure_dots"]),
                "boundaries": int(press["pressure_fours"] + press["pressure_sixes"]),
                "fours": int(press["pressure_fours"]),
                "sixes": int(press["pressure_sixes"]),
                "strike_rate": round(balls / press["pressure_wickets"], 1) if press["pressure_wickets"] else None,
                "run_rate": round(economy, 2) if economy is not None else None,
                "economy": round(economy, 2) if economy is not None else None,
                "economy_above_expected": round(economy - expected_econ, 2) if economy is not None else None,
                "expected100": round(expected_econ / 6.0 * 100.0, 2) if expected_econ is not None else None,
                "dots_pct": _pct(press["pressure_dots"], balls),
                "boundaries_pct": _pct(press["pressure_fours"] + press["pressure_sixes"], balls),
                "wickets_pct": _pct(press["pressure_wickets"], balls),
                "wides": int(extras.loc[pid, "wides"]) if pid in extras.index else 0,
                "no_balls": int(extras.loc[pid, "no_balls"]) if pid in extras.index else 0,
                "other_extras": int(extras.loc[pid, "other_extras"]) if pid in extras.index else 0,
                "IPL_impact100": round(_rate_per_100(ipl_imp, ipl_balls), 2),
                "T20I_impact100": round(_rate_per_100(t20_imp, t20_balls), 2),
                "IPL_wpa100": round(_rate_per_100(ipl_wpa, ipl_balls), 3),
                "T20I_wpa100": round(_rate_per_100(t20_wpa, t20_balls), 3),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    pm = facts["pm_pressure"]
    positive = pm.groupby("pid")["positive"].sum()
    exposed = pm.groupby("pid").size()
    frame["positive_matches"] = frame["player_id"].map(positive).fillna(0).astype(int)
    frame["exposed_matches"] = frame["player_id"].map(exposed).fillna(0).astype(int)
    frame["consistency"] = (frame["positive_matches"] + 2) / (frame["exposed_matches"] + 4)
    return frame.reset_index(drop=True)


def player_tables(df: pd.DataFrame, pressure_percentile: int, players_meta: dict):
    """Return batter and bowler aggregate frames plus bootstrap match frames."""
    pressure_col = PRESS_FLAGS[pressure_percentile]
    bf = _bat_facts(df, pressure_col)
    wf = _bowl_facts(df, pressure_col)
    batters = _finish_batting(df, bf, players_meta)
    bowlers = _finish_bowling(df, wf, players_meta)
    pm_frames = {
        "batter": (bf["pm_pressure"], bf["pm_normal"], bf["ball_values"]["impact"].to_numpy()),
        "bowler": (wf["pm_pressure"], wf["pm_normal"], legal_impact_array(df, pressure_col)),
    }
    return batters, bowlers, pm_frames


def legal_impact_array(df: pd.DataFrame, pressure_col: str):
    legal = df[df["bowler_id"].notna() & df["legal_ball"].fillna(False).astype(bool)]
    return legal.loc[legal[pressure_col].fillna(False).astype(bool), "bowl_impact_q"].fillna(0.0).to_numpy()


def attach_form(frame: pd.DataFrame, df: pd.DataFrame, pressure_col: str, role: str, season_year: int = 2026):
    """Recent form is reported only; it never enters the score."""
    if role == "batter":
        rows = df[
            df["striker_id"].notna()
            & df["ball_faced"].fillna(False).astype(bool)
            & df[pressure_col].fillna(False).astype(bool)
            & df["season_year"].eq(season_year)
        ].copy()
        rows["pid"] = rows["striker_id"].map(_canon_id)
        agg = rows.groupby("pid").agg(balls=("bat_impact", "size"), impact=("bat_impact", "sum"))
    else:
        rows = df[
            df["bowler_id"].notna()
            & df["legal_ball"].fillna(False).astype(bool)
            & df[pressure_col].fillna(False).astype(bool)
            & df["season_year"].eq(season_year)
        ].copy()
        rows["pid"] = rows["bowler_id"].map(_canon_id)
        agg = rows.groupby("pid").agg(balls=("bowl_impact_q", "size"), impact=("bowl_impact_q", "sum"))
    frame = frame.copy()
    frame["form2026_balls"] = frame["player_id"].map(agg["balls"] if len(agg) else {}).fillna(0).astype(int)
    frame["form2026_impact100"] = frame.apply(
        lambda r: round(100.0 * float(agg.loc[r["player_id"], "impact"]) / float(agg.loc[r["player_id"], "balls"]), 2)
        if r["player_id"] in agg.index and agg.loc[r["player_id"], "balls"] > 0
        else None,
        axis=1,
    )
    frame["RECENT_FORM_FLAG"] = np.where(frame["form2026_balls"] >= 30, "OK", "LOW")
    return frame
