import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

const BAT_DEFINITIONS = [
  ["Matches", "Matches in which the player appeared in the XI within the selected split."],
  ["Innings", "Batting innings with at least one delivery as striker."],
  ["Not outs", "Batting innings in which the striker was not dismissed."],
  ["Runs", "Bat runs only; wides, no-balls, byes and leg-byes are excluded."],
  ["Balls faced", "Wides excluded, no-balls included (standard batter ball count)."],
  ["Strike rate", "Runs per 100 balls faced."],
  ["Average", "Runs divided by dismissals."],
  ["Highest score", "Best innings score in the split."],
  ["30s / 50s / 100s", "Scores of 30–49, 50–99 and 100+."],
  ["Ducks / golden ducks", "Dismissed for 0; golden means dismissed for 0 having faced at most one ball."],
  ["Fours / sixes", "Batter-hit boundaries only."],
  ["Boundary % of runs", "Boundary runs as a share of bat runs."],
  ["Balls per boundary", "Balls faced per boundary hit."],
  ["Dot %", "Share of balls faced with zero bat runs."],
  ["Singles / twos / threes", "Balls scoring exactly 1, 2 or 3 runs."],
  ["Balls per dismissal", "Balls faced per dismissal."],
  ["SR and dot % by phase", "Powerplay (overs 1–6), middle (7–15), death (16–20)."],
  ["Start performance", "SR and dot % for the first 10 balls, balls 11–20 and balls 21+ of an innings."],
  ["Dismissal types", "Counts by dismissal kind (bowled, caught, LBW, stumped, run out, etc.)."],
  ["Runs by stroke", "Top strokes by balls, with runs, boundaries and dismissals."],
  ["Off-side vs on-side", "Runs, balls, dismissals, SR and dot % by stroke side."],
  ["SR vs pace vs spin", "Split by the recorded delivery type."],
  ["Most used position", "Most frequent batting slot in the XI; average entry point in overs."],
];

const BOWL_DEFINITIONS = [
  ["Matches / innings", "Matches in the XI; bowling innings with at least one ball."],
  ["Legal balls", "Excludes wides and Overstep no-balls."],
  ["Overs", "Legal balls in cricket notation (12.3 = 12 overs and 3 balls)."],
  ["Runs conceded", "Bat runs plus chargeable extras (wides, Overstep and other extras). Byes, leg-byes and penalties are not charged."],
  ["Wickets", "Excludes run-outs, retired-out and obstructing the field."],
  ["Economy", "Runs conceded per over."],
  ["Average / strike rate", "Runs per wicket / legal balls per wicket."],
  ["Dot %", "Legal balls with zero runs charged."],
  ["4s / 6s conceded", "Batter-hit boundaries off the bowler."],
  ["Balls per boundary conceded", "Legal balls per boundary conceded."],
  ["Wides / no-balls / other extras", "Chargeable extras, shown separately."],
  ["Byes and leg-byes", "Shown separately and not charged to the bowler."],
  ["Extras per match", "All extras (charged plus byes/leg-byes) divided by matches."],
  ["Maidens", "Complete six-legal-ball overs with zero runs charged."],
  ["Best figures", "Best wickets/runs in an innings."],
  ["2W / 3W / 4W / 5W hauls", "Innings with at least 2, 3, 4 or 5 wickets."],
  ["Wickets by type and phase", "Dismissal mix and powerplay/middle/death split."],
  ["Economy by phase and innings", "Economy in each phase, and in innings 1 vs 2."],
  ["vs LHB / RHB", "Split by the striker's batting hand."],
  ["Delivery style / angle / over-or-around", "Top styles by balls, plus side and angle splits."],
  ["Speed", "Average and maximum where bowl_speed > 0; a plausible 50–160 km/h range is shown separately."],
  ["First-over performance", "Balls, runs, wickets, economy and dot % in the first over."],
  ["Runs per completed over", "Distribution of runs in completed six-ball overs."],
];

const BOTH_DEFINITIONS = [
  ["Man of the match", "Count of matches where the player was named MOTM."],
  ["Matches won / win %", "Team wins in matches where the player appeared."],
  ["Impact-sub appearances", "Matches appearing as an impact substitute."],
  ["Captain / wicketkeeper matches", "Matches as captain and as designated wicketkeeper."],
];

function DefinitionTable({ title, rows }) {
  return (
    <section className="card p-5">
      <h2 className="text-sm font-bold text-slate-900 dark:text-white">{title}</h2>
      <dl className="mt-3 divide-y divide-slate-100 text-xs dark:divide-slate-800/70">
        {rows.map(([term, definition]) => (
          <div key={term} className="grid gap-1 py-2 sm:grid-cols-[13rem_1fr] sm:gap-3">
            <dt className="font-semibold text-slate-700 dark:text-slate-200">{term}</dt>
            <dd className="leading-relaxed text-slate-500 dark:text-slate-400">{definition}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function MiniTable({ head, rows }) {
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="min-w-full text-left text-[11px]">
        <thead>
          <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400">
            {head.map((cell) => (
              <th key={cell} className="py-1.5 pr-4 font-semibold">
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800/70">
          {rows.map((row) => (
            <tr key={row[0]}>
              {row.map((cell, index) => (
                <td
                  key={`${row[0]}-${index}`}
                  className={
                    index === 0
                      ? "py-1.5 pr-4 font-semibold text-slate-700 dark:text-slate-200"
                      : "num py-1.5 pr-4 text-slate-600 dark:text-slate-300"
                  }
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DataMethodsPage() {
  const [meta, setMeta] = useState(null);
  const [metaError, setMetaError] = useState(false);
  const [rankingMeta, setRankingMeta] = useState(null);
  const [rankingMetaError, setRankingMetaError] = useState(false);

  useEffect(() => {
    api
      .scoresMeta()
      .then((payload) => setMeta(payload))
      .catch(() => setMetaError(true));
  }, []);

  useEffect(() => {
    api
      .summary()
      .then((payload) => setRankingMeta(payload.rating_meta))
      .catch(() => setRankingMetaError(true));
  }, []);

  const metrics = meta?.model?.metrics;
  const overall = metrics?.overall;
  const counts = meta?.counts;
  const leverage = meta?.leverage;
  const shrink = meta?.shrinkage;
  const reliability = meta?.reliability;
  const validation = meta?.validation;
  const stability = meta?.sensitivity?.stability;

  return (
    <div className="space-y-5">
      <header>
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rr-600 dark:text-rr-300">
          Data &amp; Methods
        </p>
        <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-900 dark:text-white">
          {rankingMeta?.source
            ? "Ranking source and supplementary methods"
            : "What the engine computes and what is excluded"}
        </h1>
        <p className="mt-2 max-w-4xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">
          {rankingMeta?.source ? (
            <>
              The dashboard uses the supplied master CSV for all-player ranks, qualified ranks,
              and scores. The project engine diagnostics below are supplementary and do not
              recalculate or replace those rankings. Aggregate Stats pages are a separate
              descriptive layer built by{" "}
              <code className="font-mono text-[11px]">precompute.py</code>.
            </>
          ) : (
            <>
              Scores are produced inside this project by the reproducible engine in{" "}
              <code className="font-mono text-[11px]">/engine</code> (
              <code className="font-mono text-[11px]">python engine/run_all.py</code>) from the
              full 2022-01-22 to 2026-11-01 data pack. The aggregate Stats pages are a separate
              descriptive layer built by{" "}
              <code className="font-mono text-[11px]">precompute.py</code>.
            </>
          )}
        </p>
      </header>

      {rankingMeta?.source ? (
        <section className="card p-5">
          <h2 className="text-sm font-bold text-slate-900 dark:text-white">
            Active ranking package
          </h2>
          <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
            {rankingMeta.source}. {rankingMeta.analysis_version}. Ranks and scores are consumed
            directly from the CSV; data confidence is separate and is not added again to the score.
          </p>
          <div className="mt-3 grid gap-4 text-xs leading-relaxed text-slate-600 dark:text-slate-300 md:grid-cols-2">
            <div>
              <h3 className="font-bold text-slate-800 dark:text-slate-100">Batter score weights</h3>
              <p className="mt-1">
                Overall 15, pressure 18, consistency 13, boundary hitting 10, dot-ball control 8,
                phase-wise performance 10, pace vs spin 8, recent form 5, experience 7 and sample
                size 6 marks.
              </p>
              <p className="mt-1">
                Qualified batters meet the source criteria: at least 60 pressure balls, 5 pressure
                matches and 5 overall matches. Other ranked players remain in the all-player list.
              </p>
            </div>
            <div>
              <h3 className="font-bold text-slate-800 dark:text-slate-100">Bowler score weights</h3>
              <p className="mt-1">
                Overall 14, pressure 18, wicket-taking 13, economy control 9, dot-ball control 7,
                consistency 9, phase-wise performance 8, batting-style matchups 4, recent form 5,
                experience 7 and sample size 6 marks.
              </p>
              <p className="mt-1">
                Qualified bowlers meet the source criteria: at least 36 pressure legal balls, 5
                pressure matches and 5 overall matches.
              </p>
            </div>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
            Pressure is assessed only during second-innings chases using required-run-rate,
            wickets-in-hand and balls-remaining thresholds. The data covers 853 selected matches
            (837 with ball-by-ball records); Pakistan-mapped IDs were excluded. IPL 2027
            registration, contracts, injuries and auction availability are not verified.
          </p>
        </section>
      ) : rankingMetaError ? (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          Could not load the active ranking source details.
        </p>
      ) : null}

      <section className="card p-5">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">
          {rankingMeta?.source
            ? "Supplementary scoring-engine diagnostics (not the ranking source)"
            : "Scoring engine"}
        </h2>
        {metaError ? (
          <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">
            Engine metadata is not available. Run{" "}
            <code className="font-mono text-[11px]">python engine/run_all.py</code> to build it.
          </p>
        ) : null}
        <div className="mt-3 grid gap-4 text-xs leading-relaxed text-slate-600 dark:text-slate-300 md:grid-cols-2">
          <div className="space-y-2">
            <h3 className="text-xs font-bold text-slate-800 dark:text-slate-100">
              Win probability and leverage
            </h3>
            <p>
              A calibrated win-probability model is fitted on the pre-delivery state: innings,
              legal balls remaining, wickets down, score, target, runs needed, required rate,
              current rate, required-minus-current rate, score versus par (1.4 runs per legal
              ball) and league. Training is 2022–2023, isotonic calibration is 2024, and 2025–2026
              is held out. No tuning uses the holdout.
            </p>
            <p>
              Leverage for a state is the sum over eight legal event types (0–6 runs and a wicket
              for 0) of the event probability in its cell times the absolute win-probability
              change. Cells are league × innings × phase × wicket bucket and are smoothed with
              100 global pseudo-observations. Pressure is leverage above the frozen 75th
              percentile of 2022–2024 leverage; 70th and 80th percentile variants are reported as
              sensitivity checks.
            </p>
            {leverage ? (
              <p className="num text-[11px] text-slate-500 dark:text-slate-400">
                Cutoff {leverage.cutoff_leverage} · pressure deliveries{" "}
                {leverage.pressure_deliveries} ({Math.round(leverage.pressure_share * 100)}% of
                legal deliveries) · rule-vs-leverage agreement{" "}
                {Math.round(leverage.rule_vs_leverage.agreement * 100)}%.
              </p>
            ) : null}
          </div>
          <div className="space-y-2">
            <h3 className="text-xs font-bold text-slate-800 dark:text-slate-100">
              Baselines, impact and shrinkage
            </h3>
            <p>
              Expected runs and wicket probabilities come from 2022–2024 league × innings × phase ×
              wicket-bucket cells, smoothed toward league means with 100 pseudo-balls. T20I
              opposition strength is a tertile of runs conceded/allowed per legal ball, smoothed
              with 300 pseudo-balls; unseen teams fall back to the middle tier. IPL is neutral.
            </p>
            <p>
              Batter impact per ball is bat runs minus expected runs. Bowler impact over legal
              balls is 100 × (expected runs conceded − charged runs + 20 × (actual − expected
              wickets)). Pressure impact, WPA and pressure-minus-normal delta are shrunk with
              empirical Bayes: {" "}
              <span className="font-mono text-[11px]">
                w = n / (n + k)
              </span>
              , where k scales the per-delivery variance against signal variance (clipped
              50–500). Consistency is (positive pressure matches + 2) / (pressure matches + 4).
            </p>
            <p>
              The composite is 50 + 10 × (0.45 z(shrunk pressure impact) + 0.25 z(shrunk WPA/100) +
              0.20 z(shrunk pressure delta) + 0.10 z(consistency)). z-scores use the qualified
              cohort (150+ pressure balls) in each role and are applied to every player. All
              deliveries carry equal weight per ball; there is no recency weighting.
            </p>
            {shrink ? (
              <p className="num text-[11px] text-slate-500 dark:text-slate-400">
                k: batter {shrink.batter.k}, bowler {shrink.bowler.k} · reference impact/100:
                batter {shrink.batter.reference.impact100}, bowler {shrink.bowler.reference.impact100}.
              </p>
            ) : null}
          </div>
        </div>

        {counts ? (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {["batter", "bowler"].map((role) => (
              <div key={role} className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
                <p className="label">{role}s scored</p>
                <p className="num mt-1 text-2xl font-black text-slate-900 dark:text-white">
                  {counts[role].scored}
                </p>
                <p className="mt-0.5 text-[10px] text-slate-500 dark:text-slate-400">
                  {counts[role].qualified} qualified · {counts[role].below_min} below minimum
                </p>
              </div>
            ))}
            <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
              <p className="label">Holdout log loss</p>
              <p className="num mt-1 text-2xl font-black text-slate-900 dark:text-white">
                {overall?.log_loss ?? "—"}
              </p>
              <p className="mt-0.5 text-[10px] text-slate-500 dark:text-slate-400">
                constant prior {meta?.model?.prior ?? "—"} · ECE {overall?.ece ?? "—"}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
              <p className="label">Holdout AUC</p>
              <p className="num mt-1 text-2xl font-black text-slate-900 dark:text-white">
                {overall?.auc ?? "—"}
              </p>
              <p className="mt-0.5 text-[10px] text-slate-500 dark:text-slate-400">
                Brier {overall?.brier ?? "—"} · 2025–2026
              </p>
            </div>
          </div>
        ) : null}

        {metrics ? (
          <MiniTable
            head={["Split", "Log loss", "Brier", "AUC", "ECE", "Baseline log loss"]}
            rows={["overall", "IPL", "T20I", "innings_1", "innings_2"]
              .filter((key) => metrics[key])
              .map((key) => [
                key,
                metrics[key].log_loss,
                metrics[key].brier,
                metrics[key].auc,
                metrics[key].ece,
                metrics[key].baseline_log_loss,
              ])}
          />
        ) : null}

        <div className="mt-4 grid gap-4 border-t border-slate-100 pt-4 text-xs leading-relaxed text-slate-600 dark:border-slate-800 dark:text-slate-300 md:grid-cols-2">
          <div>
            <h3 className="text-xs font-bold text-slate-800 dark:text-slate-100">
              Uncertainty, sensitivity and reliability
            </h3>
            <p className="mt-1">
              90% score and rank intervals come from 250 joint Poisson(1) match-cluster bootstrap
              replicates. The model, cutoffs, baselines and shrinkage k and reference moments are
              held fixed, so the intervals reflect match-sampling noise. A rank interval wider than
              10 places is tagged WIDE and should not be read as a precise position.
            </p>
            <p className="mt-1">
              Sensitivity checks vary the qualification threshold (100 / 150 / 200 pressure balls),
              the leverage cutoff (70th / 75th / 80th percentile) and the composite weights
              (primary, attack-heavy, equal). Stability is the lowest rank correlation against the
              primary ordering.
            </p>
            {stability ? (
              <p className="num mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                Min rank stability: batter {Math.min(...Object.values(stability.batter)).toFixed(2)},
                bowler {Math.min(...Object.values(stability.bowler)).toFixed(2)}.
              </p>
            ) : null}
            {reliability ? (
              <p className="mt-1">
                Split-half Spearman for pressure impact/100: batter{" "}
                {reliability.batter?.split_half_spearman ?? "—"} (n=
                {reliability.batter?.split_half_n ?? "—"}), bowler{" "}
                {reliability.bowler?.split_half_spearman ?? "—"} (n=
                {reliability.bowler?.split_half_n ?? "—"}). Season-to-season correlations are
                similar and sometimes negative. The bowling ranking in particular is not stable;
                treat it as an exploratory ordering, not a precise draft board.
              </p>
            ) : null}
          </div>
          <div>
            <h3 className="text-xs font-bold text-slate-800 dark:text-slate-100">
              Form, validation and data safety
            </h3>
            <p className="mt-1">
              Recent form is <strong>not</strong> in the score. Every delivery in the window has
              equal weight. 2026 pressure impact and balls are reported separately for information
              (RECENT_FORM_FLAG), computed after the score.
            </p>
            <p className="mt-1">
              The external ranking CSVs are compared after the fact. Spearman correlation and
              top-20 overlap are reported in{" "}
              <code className="font-mono text-[11px]">engine/validation_report.md</code>. Differences
              are expected: the reference tables use a different pressure definition and cover only
              a selected subset. The engine never copies their scores.
            </p>
            {validation ? (
              <p className="num mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                Spearman vs reference: batter {validation.batter?.spearman_rank ?? "—"}, bowler{" "}
                {validation.bowler?.spearman_rank ?? "—"}; top-20 overlap{" "}
                {validation.batter?.top20_overlap ?? "—"}/20 and{" "}
                {validation.bowler?.top20_overlap ?? "—"}/20.
              </p>
            ) : null}
            <p className="mt-1">
              Only small aggregate tables are written to{" "}
              <code className="font-mono text-[11px]">data_derived/scores</code>. No
              delivery-level rows and no file from{" "}
              <code className="font-mono text-[11px]">/data_raw</code> are served by the API or
              included in the deploy bundle. The build check fails if a raw file or a file over
              5 MB enters the bundle.
            </p>
          </div>
        </div>
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">
          0–100 auction rating
        </h2>
        <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
          The ranking table and the team fit use a separate 100-mark auction rubric built by{" "}
          <code className="font-mono text-[11px]">python scripts/build_rubric.py</code> from the
          engine career tables and the derived player profiles. The engine composite score and
          rank are kept for reference ("engine X"); clean ranks are sorted by the 100-mark rating.
        </p>
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          <div>
            <h3 className="text-xs font-bold text-slate-800 dark:text-slate-100">Batter — 100 marks</h3>
            <ul className="mt-1.5 list-disc space-y-1 pl-5 text-xs text-slate-600 dark:text-slate-300">
              <li>Overall impact 15 · Pressure 18 · Consistency 13</li>
              <li>Boundary hitting 10 · Dot-ball control 8 · Phase-wise 10</li>
              <li>Pace &amp; spin 8 · Recent form 5 · Matches 7 · Sample 6</li>
            </ul>
          </div>
          <div>
            <h3 className="text-xs font-bold text-slate-800 dark:text-slate-100">Bowler — 100 marks</h3>
            <ul className="mt-1.5 list-disc space-y-1 pl-5 text-xs text-slate-600 dark:text-slate-300">
              <li>Overall impact 15 · Pressure 18 · Wicket-taking 13</li>
              <li>Economy 10 · Dot-ball % 8 · Consistency 10 · Phase-wise 8</li>
              <li>Batting styles 5 · Recent form 5 · Matches 7 · Sample 6</li>
            </ul>
          </div>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
          Each criterion is percentile-based within the role, so the bar to clear is the scored
          universe, not absolute league averages. Rate criteria are shrunk toward the role median
          with a reliability weight of n / (n + prior) before percentiles are taken (career: 150
          balls or 150 economy balls; form: 100 balls; phase/style splits need 15–30 balls). Thin
          samples therefore sit near the middle instead of topping the board. Skill criteria are
          mapped to marks with a small floor (12% of the maximum) so players keep readable shape,
          while the sample and experience marks stay honest.
        </p>
        <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
          Matches and experience come from career match counts: 1–5 matches 1/7, 6–10 2/7, 11–20
          3/7, 21–30 4/7, 31–50 5/7, 51–75 6/7, 76+ 7/7. Sample marks out of 6 scale with innings,
          legal balls and matches (batters: 20 innings, 300 balls, 15 matches; bowlers: 15 innings,
          300 legal balls, 15 matches), so a one- or two-match player cannot reach the top even with
          a hot cameo. Each player card shows the total, the per-criterion marks, strengths
          (criteria at 65%+ of their maximum), watch-outs (45% or below), a Low / Medium / High risk
          badge and the itemised marks. The rubric is written to{" "}
          <code className="font-mono text-[11px]">data_derived/scores/rubric.json</code> — career
          aggregates only, no delivery rows.
        </p>
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">Stats scope and exclusions</h2>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
          <li>Super overs (innings 3 and 4) are excluded from every aggregate.</li>
          <li>The two Emerging tournaments are excluded.</li>
          <li>DLS/shortened matches are excluded, consistent with the recent-form module.</li>
          <li>Wides and Overstep (no-ball) deliveries are not legal balls.</li>
          <li>Batters receive bat runs only; byes, leg-byes, penalties and non-bat extras are not credited.</li>
          <li>
            Bowlers are charged bat runs plus extras1 on wides, Overstep and other extras; byes,
            leg-byes and penalties are not charged.
          </li>
          <li>Bowler wickets exclude run-outs, retired-out and obstructing the field.</li>
          <li>
            No fielding statistics are shown: the supplied data contains no fielder IDs. Dropped
            catches, ground fielding and fielding runs are therefore out of scope.
          </li>
          <li>
            Only small aggregate tables are written to <code className="font-mono text-[11px]">data_derived/stats</code>.
            The raw delivery pack in /data_raw is never served by the API or bundled into the frontend.
          </li>
        </ul>
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">Splits, samples and percentiles</h2>
        <p className="mt-2 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          The split dropdown covers career, IPL, T20I, seasons 2022–2026, powerplay/middle/death,
          innings 1/2, versus pace/spin, versus LHB/RHB (bowling), descriptive pressure vs normal,
          and the last 5/10/20 matches. Every cell shows its ball count. Cells under 30 balls are
          tagged “small sample”. Percentiles compare each value with all players who have at least
          100 batting balls (batting) or 120 legal balls (bowling); a percentile is the share of the
          cohort below the value plus half of those equal to it. The “Pressure only” toggle is a
          descriptive, rule-based split (innings position, required rate and wickets in hand). It is
          separate from, and does not change, the engine composite rank and score.
        </p>
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">Head-to-head matchups</h2>
        <p className="mt-2 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          The Matchups sub-tab aggregates every player against every opponent across IPL and T20I
          matches in the same 2022-01-22 to 2026-11-01 window. Balls faced exclude wides; bowler
          balls are legal deliveries. Runs are bat runs for the batter view and charged runs for the
          bowler view. Outs include all dismissals; bowler wickets exclude run-outs and retirements.
          Pressure is the descriptive rule-based split, not the engine leverage flag. Pairs need 6+
          balls to be stored, pairs under 12 balls are tagged “small”, and the minimum-balls filter
          can be raised to 12 or 24. Only aggregates in
          <code className="font-mono text-[11px]"> data_derived/matchups</code> are served; no
          delivery-level rows are exposed.
        </p>
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">
          Public dashboard and signed-in access
        </h2>
        <p className="mt-2 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          All dashboard data is readable without an account. Signing in with the team password
          unlocks edits (availability, current team, notes, bulk, undo, import) and downloads (CSV
          exports, status backup, print/PDF). The API enforces the same rule: write and download
          endpoints return 401 without a valid session cookie, so the lock is not just a UI detail.
          Sessions last 12 hours; recent form still never feeds the engine score.
        </p>
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">
          Team squads and automatic status
        </h2>
        <p className="mt-2 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          A squad is every player whose current team equals one of the ten IPL franchises. Setting
          a current team without an explicit status applies the matching availability rule in the
          same write: Rajasthan Royals → <strong>RR own</strong>, any other franchise →{" "}
          <strong>retained</strong>, Released / in auction pool → <strong>pool</strong>, No team →
          <strong> no IPL</strong>. A free-text team leaves the status unchanged. A player with any
          team is therefore not in the available auction pool, and RR players are marked RR own.
          The supplied 2027 rosters were seeded with{" "}
          <code className="font-mono text-[11px]">scripts/apply_2027_rosters.py</code>; players not
          present in the data are left untouched.
        </p>
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">Best XI selection</h2>
        <p className="mt-2 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          The XI uses the active role-specific source scores. Players with a qualified role
          according to the source package are picked greedily by score, then a fill pass keeps the
          shape legal: one career
          wicketkeeper with 5+ matches, at least five batting options, at least four bowling
          options and at most four overseas players. Nationality comes from T20I appearances with
          the latest national team as a fallback (1057-player map in{" "}
          <code className="font-mono text-[11px]">data_derived/teams/player_meta.json</code>). The
          batting metric is the top-5 XI batting-score average, bowling is the top-4 XI
          bowling-score average, depth counts squad players scoring 50+ with 100+ pressure balls,
          pressure is the mean pressure-vs-normal delta and experience is pressure balls across
          the XI; death options, powerplay batters and all-rounders are counted from the XI. Each
          dimension is ranked 1–10 across the squads. This is a data-driven best selection, not a
          coach's tactical pick. Recent-form metrics are included in the supplied player score;
          this live recent-form view does not change it. Signed-in scouts
          can replace slots, reorder and save a custom XI; each slot shows a best-fit replacement
          drawn only from this squad or the available auction pool (never another team's retained
          players), and the XI can be reset to the data-driven selection.
        </p>
      </section>

      <DefinitionTable title="Batting definitions" rows={BAT_DEFINITIONS} />
      <DefinitionTable title="Bowling definitions" rows={BOWL_DEFINITIONS} />
      <DefinitionTable title="Both: match context" rows={BOTH_DEFINITIONS} />

      <section className="card p-5">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">Availability and backups</h2>
        <p className="mt-2 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          Availability status, current team, notes and RR fit are scouting judgements stored in the
          backend SQLite database (<code className="font-mono text-[11px]">backend/data/app.db</code>),
          which is the single source of truth. Every edit is saved through the API and reflected in
          the UI with a Saving / Saved / Error indicator. Use “Export backup” and “Import backup” in
          the Availability workspace to move the status layer as JSON. The database is never reset
          on restart.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link to="/availability" className="btn-ghost">Availability workspace</Link>
          <Link to="/stats-explorer" className="btn-primary">Stats Explorer</Link>
        </div>
      </section>
    </div>
  );
}
