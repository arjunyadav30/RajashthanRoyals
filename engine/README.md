# Pressure-reliability scoring engine

This engine computes an independent pressure-reliability score for **every player
who appears in the confidential data pack** (`data_raw/`). It does not read the
ranking CSVs in `data_rankings/` to produce scores; those files are opened only at
the end as an external sanity check.

Run it from the project root:

```bash
python engine/run_all.py
# faster rerun from parquet caches:
python engine/run_all.py
# ignore the parquet cache and re-read data_raw:
python engine/run_all.py --refresh
```

The first run on the supplied pack takes roughly 35–40 seconds. Deliveries,
matches, player metadata and enriched rows are cached under `engine/.cache/`
(gitignored). `--refresh` rebuilds them.

## Outputs

```
data_derived/scores/
  batters.json          # every batter in scope, sorted by all_rank
  bowlers.json          # every bowler in scope, sorted by all_rank
  meta.json             # model, leverage, baselines, shrinkage, bootstrap, sensitivity
  model_metrics.json    # holdout metrics only
  calibration.png       # holdout reliability curve
engine/validation_report.md   # engine vs reference-CSV comparison
```

Both JSON files are aggregate player tables. They contain **no delivery-level
rows**, no raw file contents and no identifiers from the raw pack beyond player,
team and competition names already used by the app. Every file is below 5 MB and
passes `scripts/build_check.py`.

## Pipeline

| Step | Module | What it does |
| --- | --- | --- |
| 1 | `data.py` | Loads the five required raw tables, filters matches, builds the pre-delivery state. |
| 2 | `wp.py` | Trains the win-probability model, calibrates it, evaluates the holdout. |
| 3 | `leverage.py` | Computes state-based leverage, freezes the 75th-percentile cutoff. |
| 4 | `baselines.py` | Builds opposition tiers and role/phase baselines. |
| 5 | `players.py` | Builds per-player pressure and normal aggregates, impacts and WPA. |
| 6 | `eb.py` | Empirical-Bayes shrinkage, composite score, ranks, bootstrap, sensitivity. |
| 7 | `output.py` | Writes compact, frontend-ready JSON. |
| 8 | `validation.py` | Compares with the reference rankings (optional sanity check). |

### Scope and data rules

- Window: **2022-01-22 through 2026-11-01**, inclusive, by `match_date`.
- Only IPL and T20I matches; the two Emerging/Asia-Cup Rising-Stars competitions
  are excluded, as are matches with a revised target.
- Innings 1 and 2 only. Matches with no winner and ties are excluded from the
  model and leverage but do not affect which players are in scope (players are
  counted from the eligible delivery rows).
- **Equal weight per ball.** There is no recency weighting, no last-N-match
  filter and no season weighting anywhere in the score. Recent form is attached
  to the output for display only and never feeds the score.
- Legal ball = extras type not `wide`/`Overstep`. Batter balls faced exclude
  wides; bowler-charged runs include wides and no-balls; byes and leg-byes are
  not charged to the bowler.
- Wickets credited to bowlers: caught, bowled, lbw, stumped, hit wicket.
  Run-outs, retired-outs and obstruction are not credited.

### Win probability and leverage

`HistGradientBoostingClassifier` (100 iterations, 15 leaves, learning rate 0.07,
min 100 samples/leaf, L2 20, seed 2022) on state features: runs, wickets, legal
balls, target/required rate, rate gap, score-minus-par, phase, innings, league
and interaction terms. Trained on 2022–2023, isotonic-calibrated on 2024, tested
on 2025–2026. The calibration curve is read with `np.interp` over the isotonic
knots so it is piecewise linear and monotone outside the knot range.

Leverage is the probability-weighted absolute win-probability change across **8
events** (`r0`–`r6`, `w0`) at each pre-delivery state, using per-cell
(league × innings × phase × wicket bucket) smoothed event distributions (100
pseudo-balls toward the league-wide distribution) and terminal overrides for
chase completion and innings end. The pressure cutoff is the **75th percentile
of leverage, frozen** at `0.018053`, applied to every season. This flags 24.38% of
deliveries. The old rule-based pressure flag agrees on 71.97% of balls (Jaccard
0.109), so the two definitions are related but far from identical. Sensitivity
runs at cutoffs 70 and 80 are written to `meta.json`.

### Baselines, impacts, shrinkage

Opposition tiers are tertiles of T20I batting/bowling strength, smoothed with 300
pseudo-balls; IPL is always `neutral` and unseen teams fall back to the middle
tier. Baseline cells (league × innings × phase × wicket bucket × opposition tier)
are smoothed with 100 pseudo-balls toward the league mean, with a further fallback
to the league prior for unseen cells.

- Batter `bat_impact = bat_runs − expected_bat_runs`.
- Bowler `bowl_impact_q = expected_bowl_runs − bowler_runs + 20 × (actual_wickets − expected_wickets)`.
  WPA for bowlers is negated so positive is always good for the player.
- `delta = pressure_impact100 − normal_impact100`.
- `consistency = (positive pressure matches + 2) / (pressure matches + 4)`.

Empirical Bayes shrinks each impact using `w = n / (n + k)`, where `k` is
estimated from the between-player variance among 150+ ball players minus
within-match variance, clipped to 50–500. In this pack the estimated k hits the
upper clip (**500**) for both roles: shot-level noise is large, so small samples
are pulled strongly toward the role average. The reference (unshrunk) values and
`k` are written to `meta.json`.

The composite is `50 + 10 × (0.45·z_perf + 0.25·z_wpa + 0.20·z_delta + 0.10·z_consistency)`,
where z-scores use the qualified cohort's means and standard deviations.
Alternative weightings (`attack`, `equal`) and threshold/leverage variants are
ranked and compared with the primary ranking; `stability` is the minimum
Spearman correlation across variants. In this run the minimum is 0.900 for
batters and 0.875 for bowlers (both at leverage 80); threshold variants are
≈0.998.

### Players with little or no pressure exposure

Every batter and bowler with at least one delivery in scope is scored. A player
with **zero pressure balls** is still ranked, with `eb_weight = 0` and all
components at the role reference, so the score reflects "no evidence" rather
than being dropped. The sample flag and interval expose this: all players carry
`WIDE` when the 90% bootstrap rank span exceeds 10. Players below 150 pressure
balls are marked `BELOW_MIN` and receive a separate qualified rank of null; they
still have an all-player rank. Qualified players' `rank_lo`/`rank_hi` come from
the bootstrap distribution of their **qualified** rank (not the all-player
rank) so the displayed interval answers the question the UI asks.

Intervals come from a 250-repetition match-cluster bootstrap with Poisson(1)
weights, seed 2022. The model, tournament cutoff, baselines and `k` are held
fixed; only match replication is perturbed, which captures sampling noise in the
match sample rather than model uncertainty.

### Reliability and validation

Split-half reliability correlates pressure impact per 100 balls across odd/even
matches (≥75 pressure balls per half). Season-to-season reliability correlates
within adjacent seasons (≥50 balls). The values are reported in `meta.json` and
on the Data & Methods page. They are **low**, especially for bowlers (split-half
−0.04), which is the honest conclusion: a single pressure-impact ranking is a
noisy signal at this sample size.

The reference CSVs are used only at the end. Engine output is merged on
`player_id`, engine ranks are compared with reference ranks over players present
in both, and the largest gaps plus explanations are written to
`engine/validation_report.md`. A moderate correlation is expected; forcing it to
1.0 would mean copying the reference rather than estimating independently.

## Tests

```bash
python -m pytest tests/test_engine.py -q
```

Covers legal-ball and extra accounting, state construction, leverage probability
distributions, baseline fallback, shrinkage weights and the composite formula,
rank/qualification assignment, bootstrap reproducibility with a fixed seed, and
team-total reconciliation on a real cached match (bat runs + extras = team total;
bowler-charged runs + byes + leg-byes = team total). The reconciliation test is
skipped if the cache has not been built.

Dependencies added for this engine: `scikit-learn`, `matplotlib`, `pyarrow`.
All are in the root `requirements.txt`.
