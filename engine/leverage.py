"""Pre-delivery leverage, realized WPA and rule-flag overlap."""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.config import (
    EVENTS,
    EVENT_RUNS,
    PRESSURE_PERCENTILE,
    PRESSURE_SENSITIVITY,
    PSEUDO_EVENT_BALLS,
)
from engine.data import STATE_FEATURES
from engine.wp import predict_wp

TRAIN_SEASONS = (2022, 2023, 2024)


def _cells(df: pd.DataFrame) -> pd.Series:
    return (
        df["league"].astype(str)
        + "|"
        + df["innings"].astype(int).astype(str)
        + "|"
        + df["phase"].astype(str)
        + "|"
        + df["wicket_bucket"].astype(str)
    )


def event_labels(df: pd.DataFrame) -> pd.Series:
    legal = df["legal_ball"].fillna(False).astype(bool)
    runs = df["team_runs"].fillna(0).clip(lower=0, upper=6).round().astype(int)
    label = pd.Series("r" + runs.astype(str), index=df.index)
    wicket_zero = df["is_wicket"].fillna(False).astype(bool) & df["team_runs"].fillna(0).eq(0)
    label = label.where(~wicket_zero, "w0")
    return label.where(legal)


def event_probabilities(df: pd.DataFrame) -> tuple[dict, np.ndarray, int]:
    """Smoothed P(event | league x innings x phase x wickets) on 2022-2024."""
    train = df[df["season_year"].isin(TRAIN_SEASONS)]
    labels = event_labels(train)
    labeled = labels.notna()
    counts_global = labels[labeled].value_counts()
    total = float(counts_global.sum())
    global_probs = np.array(
        [float(counts_global.get(e, 0)) / total if total else 1 / len(EVENTS) for e in EVENTS]
    )

    frame = train[labeled].copy()
    frame["event"] = labels[labeled]
    frame["cell"] = _cells(frame)
    cell_totals = frame.groupby("cell").size()
    cell_counts = frame.groupby(["cell", "event"]).size().unstack(fill_value=0)
    cell_counts = cell_counts.reindex(columns=list(EVENTS), fill_value=0)

    distributions: dict[str, np.ndarray] = {}
    for cell, row in cell_counts.iterrows():
        n = float(cell_totals.get(cell, 0))
        counts = row.to_numpy(dtype=float)
        distributions[cell] = (counts + PSEUDO_EVENT_BALLS * global_probs) / (
            n + PSEUDO_EVENT_BALLS
        )
    return distributions, global_probs, int(total)


def next_state_frame(base: pd.DataFrame, runs, wicket, legal) -> pd.DataFrame:
    """Feature frame after adding runs/wicket and optionally consuming a legal ball."""
    runs = np.asarray(runs, dtype=float)
    wicket = np.asarray(wicket, dtype=float)
    legal = np.asarray(legal, dtype=float)
    balls_remaining = np.clip(
        base["balls_remaining"].to_numpy(dtype=float) - legal, 0.0, 120.0
    )
    elapsed = np.clip(120.0 - balls_remaining, 0.0, 120.0)
    score = base["team_score"].to_numpy(dtype=float) + runs
    wickets = base["wickets_down"].to_numpy(dtype=float) + wicket
    target = base["target"].to_numpy(dtype=float)
    innings2 = base["innings"].to_numpy(dtype=int) == 2
    needed = np.where(innings2, np.clip(target - score, 0.0, None), np.nan)
    required = np.where(
        innings2, needed / np.where(balls_remaining > 0, balls_remaining, np.nan) * 6.0, np.nan
    )
    current = score / np.where(elapsed > 0, elapsed, np.nan) * 6.0
    rate_gap = required - current
    angle = score - 1.4 * elapsed
    return pd.DataFrame(
        {
            "innings": base["innings"].to_numpy(dtype=float),
            "balls_remaining": balls_remaining,
            "wickets_down": wickets,
            "team_score": score,
            "target": target,
            "runs_needed": needed,
            "required_rate": required,
            "current_rate": current,
            "rate_gap": rate_gap,
            "score_minus_par": angle,
            "is_ipl": base["is_ipl"].to_numpy(dtype=float),
        },
        columns=STATE_FEATURES,
    )


def terminal_wp(frame_after: pd.DataFrame) -> np.ndarray:
    """Win probability overrides for completed second innings."""
    out = np.full(len(frame_after), np.nan)
    innings2 = frame_after["innings"].to_numpy(dtype=float) == 2
    needed = frame_after["runs_needed"].to_numpy(dtype=float)
    wickets = frame_after["wickets_down"].to_numpy(dtype=float)
    remaining = frame_after["balls_remaining"].to_numpy(dtype=float)
    out[innings2 & (needed <= 0)] = 1.0
    out[innings2 & (needed > 0) & (wickets >= 10)] = 0.0
    out[innings2 & (needed > 0) & (wickets < 10) & (remaining <= 0)] = 0.0
    return out


def wp_states(bundle, frame: pd.DataFrame) -> np.ndarray:
    wp = predict_wp(bundle, frame)
    override = terminal_wp(frame)
    mask = np.isfinite(override)
    wp[mask] = override[mask]
    return wp


def compute_leverage(bundle, df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    base = df.reset_index(drop=True)
    wp_before = wp_states(bundle, base)
    distributions, global_probs, event_balls = event_probabilities(base)
    cells = _cells(base).to_numpy()
    prob_matrix = np.vstack([distributions.get(cell, global_probs) for cell in cells])

    leverage = np.zeros(len(base))
    for column, event in enumerate(EVENTS):
        after = next_state_frame(
            base,
            runs=EVENT_RUNS.get(event, 0),
            wicket=1 if event == "w0" else 0,
            legal=1,
        )
        wp_after = wp_states(bundle, after)
        leverage += prob_matrix[:, column] * np.abs(wp_after - wp_before)

    actual_after = next_state_frame(
        base,
        runs=base["team_runs"].to_numpy(dtype=float),
        wicket=base["is_wicket"].fillna(False).astype(int).to_numpy(dtype=float),
        legal=base["legal_ball"].fillna(False).astype(int).to_numpy(dtype=float),
    )
    wp_after_actual = wp_states(bundle, actual_after)
    wpa = wp_after_actual - wp_before

    out = base.copy()
    out["wp_before"] = wp_before
    out["wp_after"] = wp_after_actual
    out["wpa"] = wpa
    out["leverage"] = leverage

    training = out["season_year"].isin(TRAIN_SEASONS)
    reference = out.loc[training, "leverage"]
    cutoffs = {
        str(int(pct * 100)): float(np.quantile(reference, pct)) for pct in PRESSURE_SENSITIVITY
    }
    main_key = str(int(PRESSURE_PERCENTILE * 100))
    main_cutoff = cutoffs[main_key]
    out["pressure_leverage"] = out["leverage"] > main_cutoff
    for pct in PRESSURE_SENSITIVITY:
        out[f"pressure_leverage_{int(pct * 100)}"] = out["leverage"] > cutoffs[
            str(int(pct * 100))
        ]

    rule = out["pressure_rule"].fillna(False).astype(bool)
    flag = out["pressure_leverage"]
    both = int((rule & flag).sum())
    rule_only = int((rule & ~flag).sum())
    flag_only = int((~rule & flag).sum())
    neither = int((~rule & ~flag).sum())
    stats = {
        "event_probability_balls": event_balls,
        "cutoff_percentile": int(PRESSURE_PERCENTILE * 100),
        "cutoff_leverage": round(main_cutoff, 6),
        "cutoffs": {key: round(value, 6) for key, value in cutoffs.items()},
        "pressure_deliveries": int(flag.sum()),
        "pressure_share": round(float(flag.mean()), 4),
        "rule_vs_leverage": {
            "both": both,
            "rule_only": rule_only,
            "leverage_only": flag_only,
            "neither": neither,
            "agreement": round((both + neither) / len(out), 4),
            "jaccard": round(both / (both + rule_only + flag_only), 4)
            if (both + rule_only + flag_only)
            else None,
        },
    }
    return out, stats
