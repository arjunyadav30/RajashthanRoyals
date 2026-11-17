"""Reproducible end-to-end scoring pipeline: python engine/run_all.py."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from engine.baselines import attach_baselines, build_baselines, build_tiers
from engine.config import (
    CACHE_DIR,
    CALIBRATION_SEASON,
    COMPOSITE_WEIGHTS,
    DATA_END,
    DATA_START,
    DEFAULT_DERIVED_DIR,
    DEFAULT_RANKINGS_DIR,
    DEFAULT_RAW_DIR,
    MIN_PRESSURE_BALLS,
    TEST_SEASONS,
    TRAIN_SEASONS,
)
from engine.data import build_dataset
from engine.eb import (
    apply_shrinkage_ranks,
    bootstrap_ranks,
    rank_variants,
    reliability_report,
    rescore,
)
from engine.leverage import compute_leverage
from engine.output import write_meta, write_role
from engine.players import PRESS_FLAGS, attach_form, player_tables
from engine.validation import validate
from engine.wp import MODEL_PARAMS, run_wp


def player_meta(players: pd.DataFrame) -> dict:
    meta = {}
    for row in players.itertuples():
        meta[str(row.player_id)] = {
            "name": row.name,
            "latest_team": getattr(row, "latest_team", None),
            "latest_IPL_team": getattr(row, "latest_IPL_team", None),
            "IPL_PLAYED": getattr(row, "IPL_PLAYED", None),
            "PLAYED_2026_IPL": getattr(row, "PLAYED_2026_IPL", None),
        }
    return meta


def print_table(title: str, rows: list[dict]):
    print(f"\n{title}")
    header = f"{'#':>3}  {'Player':<28}{'Score':>7}{'Balls':>7}{'Impact/100':>12}{'Shrunk':>9}{'WPA/100':>9}{'Flag':>7}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['rank']:>3}  {str(row['name'])[:28]:<28}{row['score']:>7.2f}{row['pressure_balls']:>7}"
            f"{(row['impact100'] if row['impact100'] is not None else 0):>12.2f}"
            f"{row['shrunk_performance']:>9.2f}{(row['wpa100'] if row['wpa100'] is not None else 0):>9.2f}"
            f"{row['SAMPLE_FLAG']:>7}"
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the RR pressure-reliability engine.")
    parser.add_argument("--refresh", action="store_true", help="ignore the raw-data parquet cache")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--derived-dir", type=Path, default=DEFAULT_DERIVED_DIR)
    parser.add_argument("--rankings-dir", type=Path, default=DEFAULT_RANKINGS_DIR)
    args = parser.parse_args(argv)

    started = time.time()
    scores_dir = args.derived_dir / "scores"
    scores_dir.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("1/7 Loading and preparing deliveries ...")
    df, matches, players, info = build_dataset(
        args.raw_dir, DATA_START, DATA_END, refresh=args.refresh
    )
    meta = player_meta(players)

    print("2/7 Fitting win probability and leverage ...")
    bundle, model_metrics = run_wp(df, scores_dir)
    lever, leverage_stats = compute_leverage(bundle, df)
    df = lever

    print("3/7 Building baselines and per-delivery impacts ...")
    tiers = build_tiers(df)
    baselines = build_baselines(df, tiers)
    df = attach_baselines(df, tiers, baselines)
    df.to_parquet(CACHE_DIR / "enriched.parquet", index=False)

    match_seasons = df.groupby("match_id")["season_year"].first().to_dict()
    all_matches = sorted(df["match_id"].unique())

    print("4/7 Aggregating player pressure stats ...")
    tables = {pct: player_tables(df, pct, meta) for pct in PRESS_FLAGS}

    print("5/7 Shrinking, ranking and bootstrapping ...")
    primary = {}
    params = {}
    pm = {}
    for role, index in (("batter", 0), ("bowler", 1)):
        frame = tables[75][index]
        frame = attach_form(frame, df, PRESS_FLAGS[75], role)
        pm_pressure, pm_normal, ball_impacts = tables[75][2][role]
        scored, role_params = apply_shrinkage_ranks(frame, pm_pressure, ball_impacts)
        scored = bootstrap_ranks(scored, pm_pressure, pm_normal, role_params, all_matches, MIN_PRESSURE_BALLS)
        primary[role] = scored
        params[role] = role_params
        pm[role] = (pm_pressure, pm_normal)
        print(f"   {role}: {len(scored)} scored, {int(scored['qualification_status'].eq('QUALIFIED').sum())} qualified")

    variants = {}
    for pct in (70, 80):
        for role, index in (("batter", 0), ("bowler", 1)):
            frame = attach_form(tables[pct][index], df, PRESS_FLAGS[pct], role)
            pm_pressure, _, ball_impacts = tables[pct][2][role]
            scored, _ = apply_shrinkage_ranks(frame, pm_pressure, ball_impacts)
            variants[f"leverage_{pct}_{role}"] = scored
    for threshold in (100, 200):
        for role, index in (("batter", 0), ("bowler", 1)):
            frame = attach_form(tables[75][index], df, PRESS_FLAGS[75], role)
            pm_pressure, _, ball_impacts = tables[75][2][role]
            scored, _ = apply_shrinkage_ranks(frame, pm_pressure, ball_impacts, min_balls=threshold)
            variants[f"threshold_{threshold}_{role}"] = scored
    for name, weights in (("weights_attack", COMPOSITE_WEIGHTS["attack"]), ("weights_equal", COMPOSITE_WEIGHTS["equal"])):
        for role in ("batter", "bowler"):
            variants[f"{name}_{role}"] = rescore(primary[role], weights)

    stability = {}
    for role in ("batter", "bowler"):
        role_variants = {k.rsplit("_", 1)[0]: v for k, v in variants.items() if k.endswith(role)}
        primary[role], stability[role] = rank_variants(primary[role], role_variants)

    print("6/7 Writing score tables and validation ...")
    outputs = {}
    for role in ("batter", "bowler"):
        outputs[role] = write_role(primary[role], role, scores_dir)

    validation = validate(
        primary["batter"],
        primary["bowler"],
        args.rankings_dir,
        Path(__file__).resolve().parent / "validation_report.md",
    )
    reliability = {
        role: reliability_report(role, primary[role], pm[role][0], match_seasons)
        for role in ("batter", "bowler")
    }

    model_meta = {
        "engine_version": "1.0.0",
        "data_window": {"start": DATA_START, "end": DATA_END},
        "scope": info,
        "model": {
            "type": "HistGradientBoostingClassifier + isotonic calibration",
            "params": MODEL_PARAMS,
            "train_seasons": list(TRAIN_SEASONS),
            "calibration_season": CALIBRATION_SEASON,
            "test_seasons": list(TEST_SEASONS),
            "metrics": {
                key: {k: v for k, v in value.items() if k != "reliability"}
                for key, value in model_metrics.items()
                if key not in ("prior", "partitions") and isinstance(value, dict)
            },
            "prior": model_metrics.get("prior"),
            "partitions": model_metrics.get("partitions"),
        },
        "leverage": leverage_stats,
        "baselines": {
            "league_priors": {k: {kk: round(float(vv), 4) for kk, vv in v.items()} for k, v in baselines["league_priors"].items()},
            "batting_cells": len(baselines["batting_cells"]),
            "bowling_cells": len(baselines["bowling_cells"]),
            "league_bowling_mean": round(float(tiers["league_bowling_mean"]), 4),
            "league_batting_mean": round(float(tiers["league_batting_mean"]), 4),
        },
        "shrinkage": {
            role: {
                "k": round(params[role]["k"], 2),
                "per_ball_variance": round(params[role]["per_ball_variance"], 3),
                "signal_variance": round(params[role]["signal_variance"], 3),
                "within_match_variance": round(params[role]["within_match_variance"], 3),
                "eligible_n": params[role]["eligible_n"],
                "reference": {k: round(v, 3) for k, v in params[role]["ref"].items()},
            }
            for role in ("batter", "bowler")
        },
        "weights": {
            "primary": dict(zip(("shrunk_performance", "shrunk_wpa", "shrunk_delta", "consistency"), COMPOSITE_WEIGHTS["primary"])),
            "attack": dict(zip(("shrunk_performance", "shrunk_wpa", "shrunk_delta", "consistency"), COMPOSITE_WEIGHTS["attack"])),
            "equal": dict(zip(("shrunk_performance", "shrunk_wpa", "shrunk_delta", "consistency"), COMPOSITE_WEIGHTS["equal"])),
        },
        "bootstrap": {"reps": 250, "cluster": "match", "perturbation": "Poisson(1)", "interval": "5-95"},
        "sensitivity": {"stability": stability},
        "reliability": reliability,
        "validation": validation,
        "counts": {
            role: {
                "scored": outputs[role]["rows"],
                "qualified": outputs[role]["qualified"],
                "below_min": outputs[role]["below_min"],
                "wide_flags": outputs[role]["wide"],
            }
            for role in ("batter", "bowler")
        },
        "top10": {role: outputs[role]["top10"] for role in ("batter", "bowler")},
        "recent_form": "Reported only (form2026_*). It is not an input to the score.",
        "raw_data": "All outputs are aggregates. No delivery-level or /data_raw rows are written.",
    }
    write_meta(scores_dir, model_meta)

    elapsed = time.time() - started
    print("7/7 Done")
    print("\n=== Deliveries and scope ===")
    print(json.dumps({k: info[k] for k in info if k != "innings_flags"}, indent=2, default=str))
    print("\n=== Win-probability holdout (2025-2026) ===")
    for key in ("overall", "IPL", "T20I", "innings_1", "innings_2", "prior"):
        value = model_metrics.get(key)
        if isinstance(value, dict):
            print(
                f"{key:>10}: log_loss={value.get('log_loss')} brier={value.get('brier')} "
                f"auc={value.get('auc')} ece={value.get('ece')} baseline={value.get('baseline_log_loss')}"
            )
        else:
            print(f"{key:>10}: {value}")
    print("\n=== Players scored ===")
    for role in ("batter", "bowler"):
        print(f"{role:>7}: {outputs[role]['rows']} scored, {outputs[role]['qualified']} qualified, "
              f"{outputs[role]['below_min']} below minimum, {outputs[role]['wide']} wide intervals")
    print("\n=== Shrinkage ===")
    for role in ("batter", "bowler"):
        p = params[role]
        print(f"{role:>7}: k={p['k']:.1f} signal_var={p['signal_variance']:.2f} per_ball_var={p['per_ball_variance']:.2f} "
              f"reference impact100={p['ref']['impact100']:.2f}")
    print("\n=== Reliability ===")
    for role, report in reliability.items():
        print(f"{role:>7}: split-half rho={report.get('split_half_spearman')} (n={report.get('split_half_n')})")
        for pair in report.get("season_pairs", []):
            print(f"         {pair['pair']}: rho={pair['rho']:.3f} (n={pair['n']})")
    print_table("Top 10 qualified batters", outputs["batter"]["top10"])
    print_table("Top 10 qualified bowlers", outputs["bowler"]["top10"])
    print("\n=== Validation vs reference CSVs (not forced) ===")
    for role, summary in validation.items():
        if not summary.get("available"):
            print(f"{role}: reference unavailable")
            continue
        print(f"{role}: spearman={summary['spearman_rank']} top20_overlap={summary['top20_overlap']}/20 "
              f"matched={summary['matched']}")
    print(f"\nElapsed {elapsed:.1f}s; outputs in {scores_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
