import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import MatchupsPanel from "./MatchupsPanel";
import { ErrorNote, LoadingBlock } from "./States";
import { useChartTheme } from "../theme";
import { cx, fmtInt, fmtNum, fmtPct } from "../utils";

const BATTER_SPLITS = new Set(["career", "IPL", "T20I", "2022", "2023", "2024", "2025", "2026", "powerplay", "middle", "death", "innings1", "innings2", "vs_pace", "vs_spin", "pressure", "normal", "last5", "last10", "last20"]);

const LOW_IS_BETTER = new Set(["economy", "average", "strike_rate", "balls_per_boundary", "dots"]);

const BAT_HEADLINES = [
  ["runs", "Runs", "runs", "balls"],
  ["strike_rate", "Strike rate", "strike_rate", "balls"],
  ["average", "Average", "average", "balls"],
  ["highest", "Highest", "highest", "balls"],
  ["fifties", "50s", "fifties", "balls"],
  ["hundreds", "100s", "hundreds", "balls"],
  ["boundary_pct", "Boundary %", "boundary_pct", "balls"],
  ["dot_pct", "Dot %", "dot_pct", "balls"],
];

const BOWL_HEADLINES = [
  ["wickets", "Wickets", "wickets", "legal_balls"],
  ["economy", "Economy", "economy", "legal_balls"],
  ["average", "Average", "average", "legal_balls"],
  ["strike_rate", "Strike rate", "strike_rate", "legal_balls"],
  ["dot_pct", "Dot %", "dot_pct", "legal_balls"],
  ["legal_balls", "Legal balls", "legal_balls", "legal_balls"],
  ["maidens", "Maidens", "maidens", "legal_balls"],
  ["four_w", "4W+ hauls", "four_w", "legal_balls"],
];

function valueText(value, key) {
  if (value === null || value === undefined) return "—";
  if (["economy", "average", "strike_rate", "boundary_pct", "dot_pct", "win_pct", "balls_per_boundary", "balls_per_dismissal"].includes(key)) {
    return fmtNum(value, key === "economy" || key === "average" || key === "strike_rate" ? 2 : 1);
  }
  return fmtInt(value);
}

function Percentile({ value, lowerIsBetter }) {
  if (value === null || value === undefined) return <span className="text-slate-400">—</span>;
  const good = lowerIsBetter ? value <= 25 : value >= 75;
  const bad = lowerIsBetter ? value >= 75 : value <= 25;
  return (
    <span
      title="Percentile against qualified players"
      className={cx(
        "num rounded px-1 py-0.5 text-[10px] font-bold",
        good && "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300",
        bad && "bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-300",
        !good && !bad && "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400",
      )}
    >
      {fmtNum(value, 0)}
    </span>
  );
}

function SampleTag({ balls }) {
  if (balls === null || balls === undefined || balls >= 30) return null;
  return (
    <span className="ml-1 rounded bg-amber-50 px-1 py-0.5 text-[8px] font-bold uppercase tracking-wide text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
      small sample
    </span>
  );
}

function MiniBars({ rows, accent }) {
  const chart = useChartTheme();
  const data = rows.filter((row) => row.value !== null && row.value !== undefined).slice(0, 6);
  if (data.length < 2) return null;
  return (
    <div className="mt-2 h-24">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 0 }}>
          <CartesianGrid horizontal={false} stroke={chart.grid} />
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="label" width={104} tick={{ fontSize: 9, fill: chart.axis }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={chart.tooltip} />
          <Bar dataKey="value" barSize={9} radius={2} isAnimationActive={false}>
            {data.map((row, index) => (
              <Cell key={row.label} fill={index === 0 ? accent : chart.sky} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function MetricTable({ rows, percentiles, lowerBetter = false, ballsLabel = "balls" }) {
  if (!rows.length) return null;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse text-xs">
        <thead>
          <tr className="border-b border-slate-200 text-left text-[10px] uppercase tracking-wider text-slate-400 dark:border-slate-800">
            <th className="py-1.5 pr-3 font-semibold">Metric</th>
            <th className="py-1.5 pr-3 text-right font-semibold">Value</th>
            <th className="py-1.5 pr-3 text-right font-semibold">Balls</th>
            <th className="py-1.5 text-right font-semibold">Pct</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800/70">
          {rows.map((row) => (
            <tr key={row.key}>
              <td className="py-1.5 pr-3 text-slate-600 dark:text-slate-300" title={row.definition || undefined}>
                <span className="underline decoration-dotted decoration-slate-300 underline-offset-2 dark:decoration-slate-600">
                  {row.label}
                </span>
                <SampleTag balls={row.balls} />
              </td>
              <td className="num py-1.5 pr-3 text-right font-semibold text-slate-900 dark:text-white">
                {row.display ?? valueText(row.value, row.key)}
              </td>
              <td className="num py-1.5 pr-3 text-right text-[10px] text-slate-400 dark:text-slate-500">{row.balls ?? "—"}</td>
              <td className="py-1.5 text-right">
                <Percentile value={percentiles?.[row.pctKey ?? row.key]} lowerIsBetter={row.lowerBetter ?? lowerBetter} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Group({ title, subtitle, children, rows, accent, chart = true }) {
  return (
    <section className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-200">{title}</h3>
          {subtitle ? <p className="mt-0.5 text-[10px] leading-relaxed text-slate-400 dark:text-slate-500">{subtitle}</p> : null}
        </div>
      </div>
      {chart ? <MiniBars rows={rows || []} accent={accent} /> : null}
      <div className="mt-2">{children}</div>
    </section>
  );
}

function detailRows(table, labelKey, ballsLabel = "balls") {
  return Object.entries(table || {}).map(([label, value]) => ({
    key: label,
    label,
    value: value.runs ?? value.wickets ?? value.balls ?? 0,
    display: `${fmtInt(value.runs ?? value.wickets ?? 0)}${value.balls !== undefined ? ` / ${fmtInt(value.balls)}` : ""}`,
    balls: value.balls,
  }));
}

function battingGroups(record, percentiles, splits = {}) {
  if (!record) return [];
  const phaseSplits = [
    ["powerplay", "Powerplay"],
    ["middle", "Middle"],
    ["death", "Death"],
  ];
  const phaseRows = phaseSplits.map(([key, label]) => {
    const row = splits?.[key]?.batting || {};
    return { key, label, value: row.strike_rate, display: fmtNum(row.strike_rate), balls: row.balls, pctKey: "strike_rate" };
  });
  const groups = [
    {
      title: "Run scoring",
      rows: [
        { key: "matches", label: "Matches", value: record.matches, balls: record.balls },
        { key: "innings", label: "Innings", value: record.innings, balls: record.balls },
        { key: "not_outs", label: "Not outs", value: record.not_outs, balls: record.balls },
        { key: "runs", label: "Runs", value: record.runs, balls: record.balls },
        { key: "balls", label: "Balls faced", value: record.balls, balls: record.balls },
        { key: "strike_rate", label: "Strike rate", value: record.strike_rate, balls: record.balls },
        { key: "average", label: "Average", value: record.average, balls: record.balls },
        { key: "highest", label: "Highest score", value: record.highest, balls: record.balls },
        { key: "thirties", label: "30s", value: record.thirties, balls: record.balls },
        { key: "fifties", label: "50s", value: record.fifties, balls: record.balls },
        { key: "hundreds", label: "100s", value: record.hundreds, balls: record.balls },
        { key: "ducks", label: "Ducks", value: record.ducks, balls: record.balls },
        { key: "golden_ducks", label: "Golden ducks", value: record.golden_ducks, balls: record.balls },
      ],
    },
    {
      title: "Boundaries & control",
      rows: [
        { key: "fours", label: "Fours", value: record.fours, balls: record.balls },
        { key: "sixes", label: "Sixes", value: record.sixes, balls: record.balls },
        { key: "boundary_pct", label: "Boundary % of runs", value: record.boundary_pct, balls: record.balls },
        { key: "balls_per_boundary", label: "Balls per boundary", value: record.balls_per_boundary, balls: record.balls },
        { key: "dot_pct", label: "Dot %", value: record.dot_pct, balls: record.balls },
        { key: "singles", label: "Singles", value: record.singles, balls: record.balls },
        { key: "twos", label: "Twos", value: record.twos, balls: record.balls },
        { key: "threes", label: "Threes", value: record.threes, balls: record.balls },
        { key: "balls_per_dismissal", label: "Balls per dismissal", value: record.balls_per_dismissal, balls: record.balls },
      ],
    },
    {
      title: "By phase",
      rows: phaseRows,
      chartRows: phaseRows,
    },
  ];
  return groups;
}

function bowlingGroups(record, percentiles, splits = {}) {
  if (!record) return [];
  const phaseRows = ["powerplay", "middle", "death"].map((key) => {
    const row = splits?.[key]?.bowling || {};
    return { key, label: key, value: row.economy, display: fmtNum(row.economy, 2), balls: row.legal_balls, pctKey: "economy", lowerBetter: true };
  });
  return [
    {
      title: "Wickets & economy",
      rows: [
        { key: "matches", label: "Matches", value: record.matches, balls: record.legal_balls },
        { key: "innings", label: "Innings", value: record.innings, balls: record.legal_balls },
        { key: "legal_balls", label: "Legal balls", value: record.legal_balls, balls: record.legal_balls },
        { key: "overs", label: "Overs", value: record.overs, display: record.overs, balls: record.legal_balls },
        { key: "runs", label: "Runs conceded", value: record.runs, balls: record.legal_balls },
        { key: "wickets", label: "Wickets", value: record.wickets, balls: record.legal_balls },
        { key: "economy", label: "Economy", value: record.economy, balls: record.legal_balls, lowerBetter: true },
        { key: "average", label: "Average", value: record.average, balls: record.legal_balls, lowerBetter: true },
        { key: "strike_rate", label: "Strike rate", value: record.strike_rate, balls: record.legal_balls, lowerBetter: true },
        { key: "dot_pct", label: "Dot %", value: record.dot_pct, balls: record.legal_balls },
        { key: "maidens", label: "Maidens", value: record.maidens, balls: record.legal_balls },
        { key: "best", label: "Best figures", value: record.best ? `${record.best.wickets}/${record.best.runs}` : null, display: record.best ? `${record.best.wickets}/${record.best.runs}` : "—", balls: record.best?.balls },
        { key: "two_w", label: "2W hauls", value: record.two_w, balls: record.legal_balls },
        { key: "three_w", label: "3W hauls", value: record.three_w, balls: record.legal_balls },
        { key: "four_w", label: "4W hauls", value: record.four_w, balls: record.legal_balls },
        { key: "five_w", label: "5W hauls", value: record.five_w, balls: record.legal_balls },
      ],
    },
    {
      title: "Extras & boundaries",
      rows: [
        { key: "fours", label: "Fours conceded", value: record.fours, balls: record.legal_balls },
        { key: "sixes", label: "Sixes conceded", value: record.sixes, balls: record.legal_balls },
        { key: "balls_per_boundary", label: "Balls per boundary conceded", value: record.balls_per_boundary, balls: record.legal_balls, lowerBetter: true },
        { key: "wides", label: "Wides", value: record.wides, balls: record.legal_balls },
        { key: "no_balls", label: "No-balls (Overstep)", value: record.no_balls, balls: record.legal_balls },
        { key: "other_extras", label: "Other extras", value: record.other_extras, balls: record.legal_balls },
        { key: "total_extras", label: "Total extras charged", value: record.total_extras, balls: record.legal_balls },
        { key: "byes_legbyes", label: "Byes + leg-byes (not charged)", value: record.byes_legbyes, balls: record.legal_balls },
        { key: "extras_per_match", label: "Extras per match", value: record.extras_per_match, balls: record.legal_balls },
      ],
    },
    { title: "Economy by phase", rows: phaseRows, chartRows: phaseRows },
  ];
}

function comparisonRows(payload, side) {
  const keys = side === "batting" ? BAT_HEADLINES : BOWL_HEADLINES;
  return keys.map(([key, label, , ballsKey]) => {
    const record = payload?.[side] || {};
    return {
      key,
      label,
      value: record[key],
      display: record[key] === null || record[key] === undefined ? "—" : valueText(record[key], key),
      balls: record[ballsKey],
    };
  });
}

export default function StatsPanel({ playerId, playerName, role = "batter", compact = false }) {
  const [state, setState] = useState({ loading: true, error: null, data: null });
  const [split, setSplit] = useState("career");
  const [tab, setTab] = useState(role === "bowler" ? "bowling" : "batting");
  const [pressureOnly, setPressureOnly] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareState, setCompareState] = useState({ loading: false, error: null, data: null });
  const [compareOptions, setCompareOptions] = useState([]);
  const [compareId, setCompareId] = useState("");
  const chart = useChartTheme();

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, error: null, data: null });
    api
      .stats(playerId)
      .then((data) => {
        if (cancelled) return;
        setState({ loading: false, error: null, data });
        setTab(data.batting ? "batting" : "bowling");
      })
      .catch((error) => {
        if (!cancelled) setState({ loading: false, error: error.message, data: null });
      });
    return () => {
      cancelled = true;
    };
  }, [playerId]);

  useEffect(() => {
    if (!compareOpen || compareOptions.length) return;
    api
      .statsIndex({})
      .then((payload) => {
        const rows = (payload.rows || [])
          .filter((row) => String(row.player_id) !== String(playerId))
          .filter((row) => row.role === role || row.role === "both")
          .sort((a, b) => a.name.localeCompare(b.name));
        setCompareOptions(rows);
      })
      .catch((error) => setCompareState({ loading: false, error: error.message, data: null }));
  }, [compareOpen, compareOptions.length, playerId, role]);

  useEffect(() => {
    if (!compareId) {
      setCompareState({ loading: false, error: null, data: null });
      return;
    }
    let cancelled = false;
    setCompareState({ loading: true, error: null, data: null });
    api
      .stats(compareId)
      .then((data) => {
        if (!cancelled) setCompareState({ loading: false, error: null, data });
      })
      .catch((error) => {
        if (!cancelled) setCompareState({ loading: false, error: error.message, data: null });
      });
    return () => {
      cancelled = true;
    };
  }, [compareId]);

  const data = state.data;
  const effectiveSplit = pressureOnly ? "pressure" : split;
  const selected = data?.splits?.[effectiveSplit] || data?.splits?.career || {};
  const batting = selected.batting;
  const bowling = selected.bowling;
  const percentiles = data?.percentiles || {};
  const canBat = Boolean(batting);
  const canBowl = Boolean(bowling);
  const activeTab = tab === "bowling" && canBowl ? "bowling" : canBat ? "batting" : "bowling";
  const activeRecord = activeTab === "batting" ? batting : bowling;
  const activePercentiles = percentiles[activeTab] || {};
  const headline = activeTab === "batting" ? BAT_HEADLINES : BOWL_HEADLINES;
  const groups = activeTab === "batting" ? battingGroups(activeRecord, activePercentiles, data?.splits) : bowlingGroups(activeRecord, activePercentiles, data?.splits);
  const splitOptions = useMemo(
    () =>
      (data?.available_splits || []).filter((entry) => {
        if (activeTab === "batting") return BATTER_SPLITS.has(entry.key);
        return true;
      }),
    [data, activeTab],
  );

  if (state.loading) return <LoadingBlock rows={5} />;
  if (state.error) return <ErrorNote message={state.error} />;
  if (!data) return null;

  const battingBalls = batting?.balls || 0;
  const bowlingBalls = bowling?.legal_balls || 0;

  if (tab === "matchups") {
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 dark:border-slate-700 dark:bg-slate-900">
            {canBat ? (
              <button type="button" className="rounded-md px-3 py-1 text-xs font-semibold text-slate-500" onClick={() => setTab("batting")}>
                Batting
              </button>
            ) : null}
            {canBowl ? (
              <button type="button" className="rounded-md px-3 py-1 text-xs font-semibold text-slate-500" onClick={() => setTab("bowling")}>
                Bowling
              </button>
            ) : null}
            <button type="button" className="rounded-md bg-rr-600 px-3 py-1 text-xs font-semibold text-white">
              Matchups
            </button>
          </div>
        </div>
        <MatchupsPanel playerId={playerId} playerName={playerName} role={role} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 dark:border-slate-700 dark:bg-slate-900">
          {canBat ? (
            <button type="button" className={cx("rounded-md px-3 py-1 text-xs font-semibold", activeTab === "batting" ? "bg-rr-600 text-white" : "text-slate-500")} onClick={() => setTab("batting")}>
              Batting
            </button>
          ) : null}
          {canBowl ? (
            <button type="button" className={cx("rounded-md px-3 py-1 text-xs font-semibold", activeTab === "bowling" ? "bg-rr-600 text-white" : "text-slate-500")} onClick={() => setTab("bowling")}>
              Bowling
            </button>
          ) : null}
          <button type="button" className={cx("rounded-md px-3 py-1 text-xs font-semibold", tab === "matchups" ? "bg-rr-600 text-white" : "text-slate-500")} onClick={() => setTab("matchups")}>
            Matchups
          </button>
        </div>
        <label className="ml-auto flex items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400">
          <span>Split</span>
          <select
            className="select h-8 w-[13rem] py-1 text-xs"
            value={effectiveSplit}
            disabled={pressureOnly}
            onChange={(event) => setSplit(event.target.value)}
          >
            {splitOptions.map((entry) => (
              <option key={entry.key} value={entry.key}>
                {entry.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] font-semibold text-amber-800 dark:border-amber-800/60 dark:bg-amber-950/30 dark:text-amber-200">
          <input
            type="checkbox"
            checked={pressureOnly}
            onChange={(event) => {
              setPressureOnly(event.target.checked);
              if (!event.target.checked && split === "pressure") setSplit("career");
            }}
            className="h-3.5 w-3.5 rounded border-amber-300"
          />
          Pressure only (descriptive, rule-based)
        </label>
        <button
          type="button"
          className="btn-ghost h-8 px-2 py-1 text-[11px]"
          onClick={() => setCompareOpen((value) => !value)}
        >
          Compare with
        </button>
      </div>

      <p className="text-[10px] leading-relaxed text-slate-400 dark:text-slate-500">
        {activeTab === "batting" ? `Batting sample: ${fmtInt(battingBalls)} balls` : `Bowling sample: ${fmtInt(bowlingBalls)} legal balls`} · small sample under 30 balls · percentile against qualified players (batters ≥100 balls, bowlers ≥120 legal balls). Pressure is a separate descriptive, rule-based split; the engine composite rank and score are unchanged.
      </p>

      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4 lg:grid-cols-8">
        {headline.map(([key, label, , ballsKey]) => {
          const value = activeRecord?.[key];
          const balls = activeRecord?.[ballsKey];
          return (
            <div key={key} className="rounded-xl border border-slate-200 bg-slate-50/60 p-2.5 dark:border-slate-800 dark:bg-slate-950/40" title={data.definitions?.[activeTab]?.[key] || label}>
              <p className="text-[9px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">{label}</p>
              <p className="num mt-1 text-lg font-black leading-none text-slate-900 dark:text-white">{key === "best" ? (value ? `${value.wickets}/${value.runs}` : "—") : valueText(value, key)}</p>
              <p className="mt-1 flex flex-wrap items-center gap-1 text-[9px] text-slate-400 dark:text-slate-500">
                n={balls ?? "—"}
                <SampleTag balls={balls} />
              </p>
            </div>
          );
        })}
      </div>

      {compareOpen ? (
        <section className="card p-4">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-200">Compare {playerName}</h3>
            <select className="select h-8 w-[15rem] py-1 text-xs" value={compareId} onChange={(event) => setCompareId(event.target.value)}>
              <option value="">Choose a player…</option>
              {compareOptions.map((row) => (
                <option key={row.player_id} value={row.player_id}>{row.name}</option>
              ))}
            </select>
          </div>
          {compareState.error ? <p className="mt-2 text-xs text-red-600">{compareState.error}</p> : null}
          {compareState.data ? (
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {[["This player", data], [compareState.data.name, compareState.data]].map(([label, payload]) => (
                <div key={label} className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
                  <p className="text-xs font-bold text-slate-800 dark:text-slate-100">{label}</p>
                  <MetricTable rows={comparisonRows(payload, activeTab)} percentiles={payload.percentiles?.[activeTab]} ballsLabel={activeTab === "batting" ? "balls" : "legal balls"} />
                </div>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {groups.map((group) => (
          <Group key={group.title} title={group.title} rows={group.chartRows || group.rows} accent={chart.pink}>
            {group.title === "Run scoring" || group.title === "Wickets & economy" ? (
              <>
                <MetricTable rows={group.rows} percentiles={activePercentiles} ballsLabel={activeTab === "batting" ? "balls" : "legal balls"} />
                {batting ? (
                  <div className="mt-2 rounded-lg bg-slate-50 p-2 text-[10px] text-slate-500 dark:bg-slate-950/40 dark:text-slate-400">
                    Most used position: <strong>{batting.position ?? "—"}</strong> · average entry point:{" "}
                    <strong>{batting.entry !== null && batting.entry !== undefined ? `${fmtNum(batting.entry, 2)} overs` : "—"}</strong>
                  </div>
                ) : null}
                {bowling ? (
                  <div className="mt-2 rounded-lg bg-slate-50 p-2 text-[10px] text-slate-500 dark:bg-slate-950/40 dark:text-slate-400">
                    Best figures: <strong>{bowling.best ? `${bowling.best.wickets}/${bowling.best.runs}` : "—"}</strong> · 4W+ hauls: <strong>{bowling.four_w + bowling.five_w}</strong>
                  </div>
                ) : null}
              </>
            ) : (
              <MetricTable rows={group.rows} percentiles={activePercentiles} ballsLabel={activeTab === "batting" ? "balls" : "legal balls"} />
            )}
          </Group>
        ))}
      </div>

      {activeTab === "batting" && batting ? (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <Group title="Start performance" subtitle="Breakdown by balls faced in each innings" rows={Object.entries(batting.start || {}).map(([key, row]) => ({ label: key.replaceAll("_", " "), value: row.strike_rate, balls: row.balls }))} accent={chart.sky}>
              <MetricTable
                rows={Object.entries(batting.start || {}).map(([key, row]) => ({
                  key,
                  label: key.replaceAll("_", " "),
                  value: row.strike_rate,
                  balls: row.balls,
                  pctKey: "strike_rate",
                }))}
                percentiles={activePercentiles}
              />
            </Group>
            <Group title="Off-side vs on-side" rows={Object.entries(batting.side || {}).map(([key, row]) => ({ label: key, value: row.runs, balls: row.balls }))} accent={chart.emerald}>
              <MetricTable
                rows={Object.entries(batting.side || {}).map(([key, row]) => ({
                  key,
                  label: key,
                  value: row.runs,
                  balls: row.balls,
                  display: `${fmtInt(row.runs)} runs · SR ${fmtNum(row.strike_rate)}`,
                }))}
                percentiles={activePercentiles}
              />
            </Group>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Group title="Dismissal types" rows={Object.entries(batting.dismissal_types || {}).map(([key, value]) => ({ label: key, value, balls: batting.balls }))} accent={chart.amber}>
              <MetricTable rows={Object.entries(batting.dismissal_types || {}).map(([key, value]) => ({ key, label: key, value, balls: batting.balls }))} percentiles={{}} />
            </Group>
            <Group title="Runs by stroke" subtitle="Top strokes by balls, with boundaries and dismissals" rows={Object.entries(batting.stroke || {}).map(([key, row]) => ({ label: key, value: row.runs, balls: row.balls }))} accent={chart.sky}>
              <MetricTable
                rows={Object.entries(batting.stroke || {}).map(([key, row]) => ({
                  key,
                  label: key,
                  value: row.runs,
                  balls: row.balls,
                  display: `${fmtInt(row.runs)} runs · ${fmtInt(row.boundaries)} bdry · ${fmtInt(row.dismissals)} out`,
                }))}
                percentiles={{}}
              />
            </Group>
          </div>
        </>
      ) : null}

      {activeTab === "bowling" && bowling ? (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <Group title="Wickets by type" rows={Object.entries(bowling.wicket_types || {}).map(([key, value]) => ({ label: key, value, balls: bowling.legal_balls }))} accent={chart.amber}>
              <MetricTable rows={Object.entries(bowling.wicket_types || {}).map(([key, value]) => ({ key, label: key, value, balls: bowling.legal_balls }))} percentiles={{}} />
            </Group>
            <Group title="Speed" subtitle="Recorded values > 0; plausible range 50–160 km/h shown separately" rows={[]} chart={false}>
              <MetricTable
                rows={bowling.speed ? [
                  { key: "speed_n", label: "Recorded deliveries", value: bowling.speed.n, balls: bowling.speed.n, display: fmtInt(bowling.speed.n) },
                  { key: "speed_avg", label: "Average speed (all records)", value: bowling.speed.average, balls: bowling.speed.n, display: `${fmtNum(bowling.speed.average, 1)} km/h` },
                  { key: "speed_max", label: "Maximum (all records)", value: bowling.speed.max, balls: bowling.speed.n, display: `${fmtNum(bowling.speed.max, 1)} km/h` },
                  { key: "speed_plausible_avg", label: "Average, plausible range", value: bowling.speed.plausible_average, balls: bowling.speed.plausible_n, display: `${fmtNum(bowling.speed.plausible_average, 1)} km/h` },
                  { key: "speed_plausible_max", label: "Maximum, plausible range", value: bowling.speed.plausible_max, balls: bowling.speed.plausible_n, display: `${fmtNum(bowling.speed.plausible_max, 1)} km/h` },
                ] : []}
                percentiles={{}}
              />
            </Group>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Group title="First-over performance" rows={[]} chart={false}>
              <MetricTable
                rows={bowling.first_over ? [
                  { key: "innings", label: "Innings bowling first over", value: bowling.first_over.innings, balls: bowling.first_over.balls },
                  { key: "balls", label: "Legal balls", value: bowling.first_over.balls, balls: bowling.first_over.balls },
                  { key: "runs", label: "Runs", value: bowling.first_over.runs, balls: bowling.first_over.balls },
                  { key: "wickets", label: "Wickets", value: bowling.first_over.wickets, balls: bowling.first_over.balls },
                  { key: "economy", label: "Economy", value: bowling.first_over.economy, balls: bowling.first_over.balls, lowerBetter: true },
                  { key: "dot_pct", label: "Dot %", value: bowling.first_over.dot_pct, balls: bowling.first_over.balls },
                ] : []}
                percentiles={{}}
              />
            </Group>
            <Group title="Delivery style" subtitle="Top styles by legal balls" rows={Object.entries(bowling.style || {}).map(([key, row]) => ({ label: key, value: row.economy, balls: row.balls }))} accent={chart.sky}>
              <MetricTable
                rows={Object.entries(bowling.style || {}).map(([key, row]) => ({
                  key,
                  label: key,
                  value: row.economy,
                  balls: row.balls,
                  display: `Econ ${fmtNum(row.economy, 2)} · ${fmtInt(row.wickets)}W`,
                  lowerBetter: true,
                }))}
                percentiles={{}}
                lowerBetter
              />
            </Group>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Group title="On-side / off-side & over / around" rows={Object.entries({ ...bowling.side, ...bowling.angle }).map(([key, row]) => ({ label: key, value: row.economy, balls: row.balls }))} accent={chart.emerald}>
              <MetricTable
                rows={Object.entries({ ...bowling.side, ...bowling.angle }).map(([key, row]) => ({
                  key,
                  label: key,
                  value: row.economy,
                  balls: row.balls,
                  display: `Econ ${fmtNum(row.economy, 2)} · ${fmtInt(row.wickets)}W`,
                  lowerBetter: true,
                }))}
                percentiles={{}}
                lowerBetter
              />
            </Group>
            <Group title="Runs per completed over" rows={(bowling.runs_per_over || []).map((row) => ({ label: String(row.runs), value: row.count, balls: row.count * 6 }))} accent={chart.amber}>
              <MetricTable
                rows={(bowling.runs_per_over || []).map((row) => ({
                  key: String(row.runs),
                  label: `${row.runs} runs`,
                  value: row.count,
                  balls: row.count * 6,
                  display: `${fmtInt(row.count)} overs`,
                }))}
                percentiles={{}}
              />
            </Group>
          </div>
        </>
      ) : null}

      <p className="rounded-xl border border-dashed border-slate-300 p-3 text-[10px] leading-relaxed text-slate-500 dark:border-slate-700 dark:text-slate-400">
        No fielding statistics are shown: the supplied data has no fielder IDs. All aggregates exclude super overs (innings 3–4), the two Emerging tournaments, and DLS/shortened matches. Wides and Overstep are not legal balls. Batter runs are bat runs only; bowler runs include bat runs plus chargeable extras, not byes, leg-byes or penalties. Bowler wickets exclude run-outs, retired-out and obstructing the field.
      </p>
    </div>
  );
}
