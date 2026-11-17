"""Shared configuration for the pressure-reliability engine."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data_raw"
DEFAULT_DERIVED_DIR = PROJECT_ROOT / "data_derived"
DEFAULT_RANKINGS_DIR = PROJECT_ROOT / "data_rankings"
CACHE_DIR = Path(__file__).resolve().parent / ".cache"
SCORES_DIRNAME = "scores"

DATA_START = "2022-01-22"
DATA_END = "2026-11-01"

TRAIN_SEASONS = (2022, 2023)
CALIBRATION_SEASON = 2024
TEST_SEASONS = (2025, 2026)

LEAGUES = ("IPL", "T20I")
EMERGING_COMPS = {
    "Mens T20 Emerging Teams Asia Cup 2024",
    "Asia Cup Rising Stars 2025",
}

PHASES = ("powerplay", "middle", "death")
PHASE_LABELS = {"powerplay": "Powerplay", "middle": "Middle", "death": "Death"}
WICKET_BUCKETS = ((0, 2, "0-2"), (3, 5, "3-5"), (6, 9, "6+"))

EVENTS = ("r0", "r1", "r2", "r3", "r4", "r5", "r6", "w0")
EVENT_RUNS = {"r0": 0, "r1": 1, "r2": 2, "r3": 3, "r4": 4, "r5": 5, "r6": 6}
PSEUDO_EVENT_BALLS = 100.0
PSEUDO_BASELINE_BALLS = 100.0
PSEUDO_TIER_BALLS = 300.0

PRESSURE_PERCENTILE = 0.75
PRESSURE_SENSITIVITY = (0.70, 0.75, 0.80)

MIN_PRESSURE_BALLS = 150
THRESHOLD_SENSITIVITY = (100, 150, 200)

COMPOSITE_WEIGHTS = {
    "primary": (0.45, 0.25, 0.20, 0.10),
    "attack": (0.60, 0.20, 0.10, 0.10),
    "equal": (0.25, 0.25, 0.25, 0.25),
}
COMPONENT_ORDER = ("shrunk_performance", "shrunk_wpa", "shrunk_delta", "consistency")

WICKET_CREDIT = 20.0
BOOTSTRAP_REPS = 250
SEED = 2022
WIDE_RANK_SPAN = 10

SCORE_TABLE_FILES = (("batters.json", "batter"), ("bowlers.json", "bowler"))
