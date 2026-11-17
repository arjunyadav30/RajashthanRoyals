"""Win-probability model, calibration and holdout evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from engine.config import SEED
from engine.data import STATE_FEATURES, match_partition

MODEL_PARAMS = dict(
    max_iter=100,
    max_leaf_nodes=15,
    learning_rate=0.07,
    min_samples_leaf=100,
    l2_regularization=20.0,
    random_state=SEED,
)

SUBSETS = {
    "overall": lambda d: np.ones(len(d), dtype=bool),
    "IPL": lambda d: d["league"].eq("IPL").to_numpy(),
    "T20I": lambda d: d["league"].eq("T20I").to_numpy(),
    "innings_1": lambda d: d["innings"].eq(1).to_numpy(),
    "innings_2": lambda d: d["innings"].eq(2).to_numpy(),
}


def _features(df: pd.DataFrame) -> pd.DataFrame:
    return df[STATE_FEATURES].astype(float).reset_index(drop=True)


def fit_model(df: pd.DataFrame):
    partition = match_partition(df)
    train = df[partition.eq("train") & df["batting_won"].notna()]
    calibration = df[partition.eq("calibration")]
    test = df[partition.eq("test")]
    if train.empty or calibration.empty or test.empty:
        raise ValueError("Win-probability partitions are empty; check the season window.")

    model = HistGradientBoostingClassifier(**MODEL_PARAMS)
    model.fit(_features(train), train["batting_won"].astype(int))

    calib_raw = model.predict_proba(_features(calibration))[:, 1]
    isotonic = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    isotonic.fit(calib_raw, calibration["batting_won"].astype(int))
    knots = np.asarray(isotonic.X_thresholds_, dtype=float)
    values = np.asarray(isotonic.y_thresholds_, dtype=float)

    train_prior = float(train["batting_won"].mean())
    return {
        "model": model,
        "isotonic": isotonic,
        "knots": knots,
        "values": values,
        "prior": train_prior,
        "partitions": {
            "train": train,
            "calibration": calibration,
            "test": test,
        },
    }


def calibrate(bundle, raw: np.ndarray) -> np.ndarray:
    """Piecewise-linear interpolation of the isotonic fit (avoids step plateaus)."""
    knots = bundle["knots"]
    values = bundle["values"]
    if len(knots) == 0:
        return np.clip(raw, 0.0, 1.0)
    return np.clip(np.interp(raw, knots, values, left=values[0], right=values[-1]), 0.0, 1.0)


def predict_wp(bundle, frame: pd.DataFrame) -> np.ndarray:
    if frame.empty:
        return np.array([], dtype=float)
    raw = bundle["model"].predict_proba(_features(frame))[:, 1]
    return calibrate(bundle, raw)


def _ece(y_true: np.ndarray, p: np.ndarray, bins: int = 10) -> float | None:
    if len(p) == 0:
        return None
    order = np.argsort(p)
    splits = np.array_split(order, bins)
    total = len(p)
    ece = 0.0
    used = 0
    for idx in splits:
        if len(idx) == 0:
            continue
        gap = abs(float(p[idx].mean()) - float(y_true[idx].mean()))
        ece += gap * len(idx)
        used += len(idx)
    return ece / used if used else None


def _reliability_points(y_true: np.ndarray, p: np.ndarray, bins: int = 10):
    order = np.argsort(p)
    points = []
    for idx in np.array_split(order, bins):
        if len(idx) == 0:
            continue
        points.append(
            {
                "predicted": round(float(p[idx].mean()), 4),
                "observed": round(float(y_true[idx].mean()), 4),
                "n": int(len(idx)),
            }
        )
    return points


def _metrics(y_true: np.ndarray, p: np.ndarray, prior: float) -> dict:
    out = {
        "n": int(len(y_true)),
        "positives": int(y_true.sum()) if len(y_true) else 0,
        "win_rate": round(float(y_true.mean()), 4) if len(y_true) else None,
        "log_loss": round(float(log_loss(y_true, p, labels=[0, 1])), 4) if len(y_true) else None,
        "brier": round(float(brier_score_loss(y_true, p)), 4) if len(y_true) else None,
        "auc": (
            round(float(roc_auc_score(y_true, p)), 4)
            if len(y_true) and len(np.unique(y_true)) > 1
            else None
        ),
        "ece": round(_ece(y_true, p), 4) if len(y_true) else None,
        "baseline_log_loss": (
            round(float(log_loss(y_true, np.full(len(y_true), prior), labels=[0, 1])), 4)
            if len(y_true)
            else None
        ),
        "baseline_brier": (
            round(float(brier_score_loss(y_true, np.full(len(y_true), prior))), 4)
            if len(y_true)
            else None
        ),
    }
    return out


def evaluate(bundle) -> dict:
    test = bundle["partitions"]["test"]
    y = test["batting_won"].astype(int).to_numpy()
    p = predict_wp(bundle, test)
    prior = bundle["prior"]
    results = {}
    for name, selector in SUBSETS.items():
        mask = selector(test)
        results[name] = _metrics(y[mask], p[mask], prior)
    results["overall"]["reliability"] = _reliability_points(y, p)
    results["prior"] = round(prior, 4)
    results["partitions"] = {
        name: {
            "deliveries": int(len(frame)),
            "matches": int(frame["match_id"].nunique()),
            "seasons": sorted(int(s) for s in frame["season_year"].unique()),
        }
        for name, frame in bundle["partitions"].items()
    }
    return results


def calibration_plot(metrics: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    points = metrics["overall"]["reliability"]
    fig, ax = plt.subplots(figsize=(5.2, 4.4), dpi=140)
    ax.plot([0, 1], [0, 1], linestyle="--", linewidth=1, color="#94a3b8", label="Perfect")
    ax.plot(
        [p["predicted"] for p in points],
        [p["observed"] for p in points],
        marker="o",
        linewidth=1.8,
        color="#0f766e",
        label="Holdout 2025-26",
    )
    ax.set_xlabel("Predicted batting-side win probability")
    ax.set_ylabel("Observed win rate")
    ax.set_title("Win-probability calibration")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def run_wp(df: pd.DataFrame, scores_dir: Path) -> dict:
    bundle = fit_model(df)
    metrics = evaluate(bundle)
    calibration_plot(metrics, scores_dir / "calibration.png")
    (scores_dir / "model_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    return bundle, metrics
