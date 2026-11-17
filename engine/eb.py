"""Empirical-Bayes shrinkage, composite scores, ranks, bootstrap and reliability."""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.config import (
    BOOTSTRAP_REPS,
    COMPONENT_ORDER,
    COMPOSITE_WEIGHTS,
    MIN_PRESSURE_BALLS,
    SEED,
    WIDE_RANK_SPAN,
)

ROLE_SIGN = {"batter": 1.0, "bowler": 1.0}


def _spearman(a: pd.Series, b: pd.Series) -> float | None:
    joined = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if len(joined) < 3:
        return None
    return float(joined["a"].rank().corr(joined["b"].rank()))


def _within_match_var(pm: pd.DataFrame, eligible: set) -> float:
    values = []
    for pid, group in pm.groupby(level=0):
        if pid not in eligible or len(group) < 2:
            continue
        per100 = group["impact_sum"] / group["balls"] * 100.0
        values.append(float(per100.var(ddof=1)) / len(group))
    return float(np.median(values)) if values else 0.0


def shrink_params(frame: pd.DataFrame, pm: pd.DataFrame, ball_impacts: np.ndarray, min_balls: int):
    eligible = frame[frame["pressure_balls"] >= min_balls]
    if len(eligible) < 2:
        raise ValueError("not enough eligible players for shrinkage moments")
    signal_var = float(eligible["impact100"].var(ddof=1))
    within = _within_match_var(pm, set(eligible["player_id"]))
    signal_var = max(signal_var - within, 1.0)
    per_ball_var = float(np.var(ball_impacts, ddof=1)) if len(ball_impacts) > 1 else 0.0
    k = per_ball_var * 10000.0 / signal_var if signal_var > 0 else 500.0
    k = float(np.clip(k, 50.0, 500.0))
    ref = {
        "impact100": float(eligible["impact100"].mean()),
        "wpa100": float(eligible["wpa100"].mean()),
        "delta": float(eligible["delta"].mean()),
        "consistency": float(eligible["consistency"].mean()),
    }
    sd = {
        "impact100": max(float(eligible["impact100"].std(ddof=1)), 1e-9),
        "wpa100": max(float(eligible["wpa100"].std(ddof=1)), 1e-9),
        "delta": max(float(eligible["delta"].std(ddof=1)), 1e-9),
        "consistency": max(float(eligible["consistency"].std(ddof=1)), 1e-9),
    }
    return {
        "k": k,
        "per_ball_variance": per_ball_var,
        "signal_variance": signal_var,
        "within_match_variance": within,
        "ref": ref,
        "sd": sd,
        "eligible_n": int(len(eligible)),
    }


def _z(series: pd.Series, mean: float, sd: float) -> pd.Series:
    return (series - mean) / sd


def add_components(frame: pd.DataFrame, params: dict, weights=COMPOSITE_WEIGHTS["primary"]):
    frame = frame.copy()
    n = frame["pressure_balls"].astype(float)
    w = n / (n + params["k"])
    ref = params["ref"]
    frame["eb_weight"] = w
    for component, source, target in (
        ("impact100", "impact100", "shrunk_performance"),
        ("wpa100", "wpa100", "shrunk_wpa"),
        ("delta", "delta", "shrunk_delta"),
    ):
        raw = frame[source]
        filled = raw.fillna(ref[component])
        frame[target] = w * filled + (1.0 - w) * ref[component]
    frame["shrunk_performance"] = frame["shrunk_performance"].round(2)
    frame["shrunk_wpa"] = frame["shrunk_wpa"].round(3)
    frame["shrunk_delta"] = frame["shrunk_delta"].round(2)
    frame["shrunk_consistency"] = frame["consistency"].round(3)
    frame["eb_weight"] = frame["eb_weight"].round(3)
    sd = params["sd"]
    frame["z_performance"] = _z(frame["shrunk_performance"], ref["impact100"], sd["impact100"])
    frame["z_wpa"] = _z(frame["shrunk_wpa"], ref["wpa100"], sd["wpa100"])
    frame["z_delta"] = _z(frame["shrunk_delta"], ref["delta"], sd["delta"])
    frame["z_consistency"] = _z(frame["shrunk_consistency"], ref["consistency"], sd["consistency"])
    z = {
        "shrunk_performance": frame["z_performance"],
        "shrunk_wpa": frame["z_wpa"],
        "shrunk_delta": frame["z_delta"],
        "consistency": frame["z_consistency"],
    }
    frame["score"] = 50.0 + 10.0 * sum(weights[i] * z[key] for i, key in enumerate(COMPONENT_ORDER))
    frame["score"] = frame["score"].round(2)
    return frame


def rescore(frame: pd.DataFrame, weights) -> pd.DataFrame:
    frame = frame.copy()
    z = {
        "shrunk_performance": frame["z_performance"],
        "shrunk_wpa": frame["z_wpa"],
        "shrunk_delta": frame["z_delta"],
        "consistency": frame["z_consistency"],
    }
    frame["score"] = (50.0 + 10.0 * sum(weights[i] * z[k] for i, k in enumerate(COMPONENT_ORDER))).round(2)
    return frame


def add_ranks(frame: pd.DataFrame, min_balls: int):
    frame = frame.sort_values(
        ["score", "pressure_balls", "player_id"], ascending=[False, False, True], kind="mergesort"
    ).reset_index(drop=True)
    frame["qualification_status"] = np.where(
        frame["pressure_balls"] >= min_balls, "QUALIFIED", "BELOW_MIN"
    )
    frame["all_rank"] = np.arange(1, len(frame) + 1)
    frame["rank"] = frame["all_rank"]
    qualified = frame["qualification_status"].eq("QUALIFIED").to_numpy()
    qualified_rank = np.full(len(frame), np.nan)
    qualified_rank[qualified] = np.arange(1, int(qualified.sum()) + 1)
    frame["qualified_rank"] = pd.array(qualified_rank, dtype="Int64")
    return frame


def apply_shrinkage_ranks(
    frame: pd.DataFrame,
    pm: pd.DataFrame,
    ball_impacts: np.ndarray,
    min_balls: int = MIN_PRESSURE_BALLS,
    weights=COMPOSITE_WEIGHTS["primary"],
):
    params = shrink_params(frame, pm, ball_impacts, min_balls)
    scored = add_components(frame, params, weights)
    scored = add_ranks(scored, min_balls)
    return scored, params


def _match_index(matches: np.ndarray) -> dict:
    return {m: i for i, m in enumerate(matches)}


def bootstrap_ranks(
    frame: pd.DataFrame,
    pm: pd.DataFrame,
    pm_normal: pd.DataFrame,
    params: dict,
    matches: np.ndarray,
    min_balls: int,
    reps: int = BOOTSTRAP_REPS,
    seed: int = SEED,
):
    """Joint Poisson(1) match-cluster bootstrap with model, k and moments fixed."""
    rng = np.random.default_rng(seed)
    pids = frame["player_id"].tolist()
    pos = {p: i for i, p in enumerate(pids)}
    mpos = _match_index(matches)
    p_ball = frame["pressure_balls"].to_numpy(float)
    k = params["k"]
    ref = params["ref"]
    sd = params["sd"]

    def arrays(rows: pd.DataFrame, cols):
        pid_idx = np.array([pos[p] for p in rows.index.get_level_values(0)], dtype=int)
        match_idx = np.array([mpos[m] for m in rows.index.get_level_values(1)], dtype=int)
        return pid_idx, match_idx, [rows[c].to_numpy(float) for c in cols]

    p_pid, p_mid, p_cols = arrays(pm, ["impact_sum", "balls", "wpa_sum", "positive"])
    n_pid, n_mid, n_cols = (
        arrays(pm_normal, ["normal_impact_sum", "normal_balls"]) if len(pm_normal) else ([], [], [])
    )

    n_players = len(pids)
    score_reps = np.empty((reps, n_players))
    all_rank_reps = np.empty((reps, n_players))
    qual_rank_reps = np.full((reps, n_players), np.nan)

    for rep in range(reps):
        w = rng.poisson(1.0, size=len(matches)).astype(float)
        pw = w[p_mid] if len(p_mid) else np.zeros(0)
        pb = np.bincount(p_pid, weights=p_cols[1] * pw, minlength=n_players)
        pi = np.bincount(p_pid, weights=p_cols[0] * pw, minlength=n_players)
        wp = np.bincount(p_pid, weights=p_cols[2] * pw, minlength=n_players)
        positive = np.bincount(p_pid, weights=p_cols[3] * pw, minlength=n_players)
        exposed = np.bincount(p_pid, weights=pw, minlength=n_players)
        if len(n_pid):
            nw = w[n_mid]
            nb = np.bincount(n_pid, weights=n_cols[1] * nw, minlength=n_players)
            ni = np.bincount(n_pid, weights=n_cols[0] * nw, minlength=n_players)
        else:
            nb = np.zeros(n_players)
            ni = np.zeros(n_players)

        has_p = pb > 0
        impact = np.where(has_p, pi / np.maximum(pb, 1e-9) * 100.0, np.nan)
        wpa = np.where(has_p, wp / np.maximum(pb, 1e-9) * 100.0, np.nan)
        normal = np.where(nb > 0, ni / np.maximum(nb, 1e-9) * 100.0, np.nan)
        delta = np.where(has_p & (nb > 0), impact - normal, np.nan)
        consistency = (positive + 2.0) / (exposed + 4.0)

        weight = pb / (pb + k)
        imp_s = np.where(has_p, weight * impact, 0.0) + (1.0 - weight) * ref["impact100"]
        wpa_s = np.where(has_p, weight * wpa, 0.0) + (1.0 - weight) * ref["wpa100"]
        delta_s = np.where(has_p, weight * np.where(np.isnan(delta), ref["delta"], delta), 0.0) + (
            1.0 - weight
        ) * ref["delta"]
        z = (
            0.45 * (imp_s - ref["impact100"]) / sd["impact100"]
            + 0.25 * (wpa_s - ref["wpa100"]) / sd["wpa100"]
            + 0.20 * (delta_s - ref["delta"]) / sd["delta"]
            + 0.10 * (consistency - ref["consistency"]) / sd["consistency"]
        )
        score = 50.0 + 10.0 * z
        score_reps[rep] = score

        order = np.argsort(-score, kind="stable")
        ranks = np.empty(n_players)
        ranks[order] = np.arange(1, n_players + 1)
        all_rank_reps[rep] = ranks

        qualified = np.where(pb >= min_balls)[0]
        if len(qualified):
            qscores = score[qualified]
            qorder = np.argsort(-qscores, kind="stable")
            qranks = np.empty(len(qualified))
            qranks[qorder] = np.arange(1, len(qualified) + 1)
            qual_rank_reps[rep, qualified] = qranks

    frame = frame.copy()
    frame["score_lo"] = np.percentile(score_reps, 5, axis=0).round(2)
    frame["score_hi"] = np.percentile(score_reps, 95, axis=0).round(2)
    frame["rank_lo"] = np.percentile(all_rank_reps, 5, axis=0).round(0).astype(int)
    frame["rank_hi"] = np.percentile(all_rank_reps, 95, axis=0).round(0).astype(int)
    frame["qualified_rank_lo"] = pd.array([None] * len(frame), dtype="Int64")
    frame["qualified_rank_hi"] = pd.array([None] * len(frame), dtype="Int64")
    qualified = frame["qualification_status"].eq("QUALIFIED").to_numpy()
    if qualified.any():
        q_lo = np.nanpercentile(qual_rank_reps[:, qualified], 5, axis=0)
        q_hi = np.nanpercentile(qual_rank_reps[:, qualified], 95, axis=0)
        frame.loc[qualified, "qualified_rank_lo"] = pd.array(np.round(q_lo, 0), dtype="Int64")
        frame.loc[qualified, "qualified_rank_hi"] = pd.array(np.round(q_hi, 0), dtype="Int64")
        frame.loc[qualified, "rank_lo"] = pd.array(np.round(q_lo, 0), dtype="Int64")
        frame.loc[qualified, "rank_hi"] = pd.array(np.round(q_hi, 0), dtype="Int64")
    span = frame["rank_hi"] - frame["rank_lo"]
    frame["SAMPLE_FLAG"] = np.where(span > WIDE_RANK_SPAN, "WIDE", "OK")
    return frame


def rank_variants(primary: pd.DataFrame, variants: dict[str, pd.DataFrame]):
    """Attach all-player ranks under each sensitivity variant and stability scores."""
    out = primary.copy()
    out["rank_variants"] = [dict() for _ in range(len(out))]
    stability = {}
    key_to_pos = {p: i for i, p in enumerate(out["player_id"])}
    for name, variant in variants.items():
        v = variant.sort_values(
            ["score", "pressure_balls", "player_id"], ascending=[False, False, True], kind="mergesort"
        ).reset_index(drop=True)
        ranks = {pid: i + 1 for i, pid in enumerate(v["player_id"])}
        stability[name] = _spearman(out["score"], out["player_id"].map(v.set_index("player_id")["score"]))
        values = [ranks.get(p) for p in out["player_id"]]
        out["rank_variants"] = [
            {**current, name: values[i]} for i, current in enumerate(out["rank_variants"])
        ]
    out["stability"] = round(min(v for v in stability.values() if v is not None), 3) if any(
        v is not None for v in stability.values()
    ) else None
    return out, stability


def reliability_report(role: str, frame: pd.DataFrame, pm: pd.DataFrame, match_seasons: dict):
    """Odd/even split-half and adjacent-season Spearman of pressure impact per 100."""
    if pm.empty:
        return {}
    rows = pm.reset_index()
    rows["season"] = rows["match_id"].map(match_seasons)
    ordered = sorted(rows["match_id"].unique())
    parity = {m: ("odd" if i % 2 else "even") for i, m in enumerate(ordered)}
    rows["half"] = rows["match_id"].map(parity)
    halves = []
    for half in ("odd", "even"):
        part = rows[rows["half"] == half]
        agg = part.groupby("pid").agg(balls=("balls", "sum"), impact=("impact_sum", "sum"))
        agg["impact100"] = agg["impact"] / agg["balls"] * 100.0
        halves.append(agg)
    joined = pd.concat([halves[0][["impact100", "balls"]], halves[1][["impact100", "balls"]]], axis=1)
    joined.columns = ["odd", "odd_balls", "even", "even_balls"]
    joined = joined[(joined["odd_balls"] >= 75) & (joined["even_balls"] >= 75)]
    split_half = _spearman(joined["odd"], joined["even"]) if len(joined) >= 3 else None

    by_season = []
    seasons = sorted({s for s in rows["season"].dropna().unique()})
    for a, b in zip(seasons, seasons[1:]):
        agg = rows[rows["season"].isin([a, b])].groupby(["pid", "season"]).agg(
            balls=("balls", "sum"), impact=("impact_sum", "sum")
        )
        agg["impact100"] = agg["impact"] / agg["balls"] * 100.0
        pivot = agg["impact100"].unstack()
        balls = agg["balls"].unstack()
        if a not in pivot.columns or b not in pivot.columns:
            continue
        mask = (balls[a] >= 50) & (balls[b] >= 50)
        if mask.sum() >= 3:
            by_season.append(
                {"pair": f"{int(a)}-{int(b)}", "n": int(mask.sum()), "rho": _spearman(pivot.loc[mask, a], pivot.loc[mask, b])}
            )
    return {
        "role": role,
        "split_half_spearman": round(split_half, 3) if split_half is not None else None,
        "split_half_n": int(len(joined)),
        "season_pairs": by_season,
    }
