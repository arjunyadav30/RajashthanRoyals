import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import { FlagBadge, FlagBadges, PlayerAvatar, RankChip, StatusPill } from "../components/Badges";
import CurrentTeamEditor from "../components/CurrentTeamEditor";
import RecentMatchesPanel from "../components/RecentMatchesPanel";
import SaveIndicator from "../components/SaveIndicator";
import StatsPanel from "../components/StatsPanel";
import ScoreRangeBar from "../components/ScoreRangeBar";
import { ErrorNote, LoadingBlock } from "../components/States";
import { useChartTheme } from "../theme";
import {
  cx,
  flagBadges,
  fmtInt,
  fmtNum,
  fmtPct,
  fmtSigned,
  isNumber,
  statusMeta,
  STATUS_ORDER,
} from "../utils";

function MiniStat({ label, value, hint, accent }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-950/40">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
        {label}
      </p>
      <p
        className={cx(
          "num mt-0.5 text-lg font-bold leading-tight",
          accent === "pink" && "text-rr-700 dark:text-rr-300",
          accent === "sky" && "text-sky-700 dark:text-sky-300",
          accent === "emerald" && "text-emerald-700 dark:text-emerald-300",
          !accent && "text-slate-900 dark:text-white",
        )}
      >
        {value}
      </p>
      {hint ? (
        <p className="mt-0.5 text-[10px] leading-snug text-slate-400 dark:text-slate-500">{hint}</p>
      ) : null}
    </div>
  );
}

function RubricCard({ player }) {
  const rubric = player.rubric;
  if (!rubric) return null;
  const role = player.player_type;
  const riskTone =
    rubric.risk === "Low"
      ? "bg-emerald-100 text-emerald-800 ring-emerald-600/20 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-400/30"
      : rubric.risk === "High"
        ? "bg-red-100 text-red-800 ring-red-600/20 dark:bg-red-500/15 dark:text-red-300 dark:ring-red-400/30"
        : "bg-amber-100 text-amber-900 ring-amber-600/20 dark:bg-amber-500/15 dark:text-amber-300 dark:ring-amber-400/30";

  const headline =
    role === "batter"
      ? [
          { label: "Matches", value: fmtInt(rubric.matches) },
          { label: "Innings", value: fmtInt(rubric.innings) },
          { label: "Runs", value: fmtInt(rubric.runs) },
          { label: "Average", value: fmtNum(rubric.average) },
          { label: "Strike rate", value: fmtNum(rubric.strike_rate) },
          { label: "4s / 6s", value: `${fmtInt(rubric.fours)} / ${fmtInt(rubric.sixes)}` },
          { label: "Balls / boundary", value: fmtNum(rubric.balls_per_boundary, 1) },
          { label: "Experience", value: rubric.experience },
        ]
      : [
          { label: "Matches", value: fmtInt(rubric.matches) },
          { label: "Innings", value: fmtInt(rubric.innings) },
          { label: "Wickets", value: fmtInt(rubric.wickets) },
          { label: "Average", value: fmtNum(rubric.average) },
          { label: "Economy", value: fmtNum(rubric.economy) },
          { label: "Dot-ball %", value: fmtPct(rubric.dot_pct) },
          { label: "Experience", value: rubric.experience },
          { label: "Risk", value: rubric.risk },
        ];

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-slate-900 dark:text-white">
            Auction rating
          </h2>
          <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
            {role === "bowler" ? "Bowling" : "Batting"} rubric out of 100: performance,
            pressure, consistency, boundary/economy, dot-ball control, phases, styles,
            form, experience and sample size
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="num text-4xl font-black tracking-tight text-rr-700 dark:text-rr-300">
              {fmtNum(rubric.total, 1)}
            </p>
            <p className="num text-[11px] text-slate-500 dark:text-slate-400">
              /100 · skill fit {fmtNum(rubric.role_fit, 1)}
            </p>
          </div>
          <span
            className={cx(
              "inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ring-1 ring-inset",
              riskTone,
            )}
          >
            {rubric.risk} risk
          </span>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {headline.map((item) => (
          <MiniStat key={item.label} label={item.label} value={item.value} />
        ))}
      </div>

      <div className="mt-4 space-y-2">
        {rubric.criteria.map((criterion) => {
          const ratio = criterion.max ? criterion.score / criterion.max : 0;
          return (
            <div key={criterion.key} className="flex items-center gap-3">
              <span className="w-40 shrink-0 text-[11px] text-slate-600 dark:text-slate-300">
                {criterion.label}
              </span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                <div
                  className={cx(
                    "h-full rounded-full",
                    ratio >= 0.7
                      ? "bg-emerald-500"
                      : ratio >= 0.45
                        ? "bg-rr-500"
                        : "bg-amber-500",
                  )}
                  style={{ width: `${Math.max(2, Math.min(100, ratio * 100))}%` }}
                />
              </div>
              <span className="num w-16 shrink-0 text-right text-[11px] font-semibold text-slate-700 dark:text-slate-200">
                {fmtNum(criterion.score, 1)}/{criterion.max}
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-4 grid gap-3 border-t border-slate-100 pt-3 text-[11px] sm:grid-cols-2 dark:border-slate-800">
        <div>
          <p className="font-bold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
            Strengths
          </p>
          <ul className="mt-1 space-y-0.5 text-slate-600 dark:text-slate-300">
            {(rubric.strengths?.length ? rubric.strengths : ["Balanced profile — no standout yet"]).map(
              (item) => (
                <li key={item}>{item}</li>
              ),
            )}
          </ul>
        </div>
        <div>
          <p className="font-bold uppercase tracking-wide text-amber-700 dark:text-amber-400">
            Watch-outs
          </p>
          <ul className="mt-1 space-y-0.5 text-slate-600 dark:text-slate-300">
            {(rubric.weaknesses?.length ? rubric.weaknesses : ["No weak criterion below 45%"]).map(
              (item) => (
                <li key={item}>{item}</li>
              ),
            )}
          </ul>
        </div>
      </div>
      <p className="mt-2 text-[10px] leading-relaxed text-slate-400 dark:text-slate-500">
        {rubric.risk_reason} Experience marks: {rubric.experience_marks}/7 · sample marks:{" "}
        {fmtNum(rubric.sample_marks, 1)}/6.
      </p>
    </section>
  );
}

function PressureChart({ player }) {
  const chart = useChartTheme();
  const data = useMemo(
    () =>
      [
        { name: "Pressure", value: player.impact100, color: chart.pink },
        { name: "Normal", value: player.normal_impact, color: chart.sky },
      ].filter((entry) => isNumber(entry.value)),
    [player.impact100, player.normal_impact, chart.pink, chart.sky],
  );

  if (data.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-slate-500 dark:text-slate-400">
        Pressure and normal impact were not supplied for this player.
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={190}>
      <BarChart data={data} layout="vertical" margin={{ top: 8, right: 48, bottom: 4, left: 4 }}>
        <CartesianGrid horizontal={false} stroke={chart.grid} />
        <XAxis
          type="number"
          stroke={chart.axis}
          tick={{ fontSize: 11, fill: chart.axis }}
          tickFormatter={(value) => fmtNum(value, 0)}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={72}
          stroke={chart.axis}
          tick={{ fontSize: 12, fill: chart.axis }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={chart.tooltip}
          cursor={{ fill: chart.grid, opacity: 0.35 }}
          formatter={(value) => [fmtNum(value), "Impact / 100 balls"]}
        />
        <ReferenceLine x={0} stroke={chart.axis} />
        <Bar dataKey="value" barSize={22} radius={4} isAnimationActive={false}>
          {data.map((entry) => (
            <Cell key={entry.name} fill={entry.color} />
          ))}
          <LabelList
            dataKey="value"
            position="right"
            formatter={(value) => fmtNum(value)}
            style={{ fontSize: 11, fill: chart.axis, fontWeight: 600 }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function componentMetrics(role) {
  if (role === "bowler") {
    return [
      { key: "dots_pct", label: "Dot-ball %", hint: "Higher is better", format: (v) => fmtPct(v) },
      {
        key: "boundaries_pct",
        label: "Boundary conceded %",
        hint: "Lower is better",
        format: (v) => fmtPct(v),
      },
      { key: "wickets_pct", label: "Wicket %", hint: "Higher is better", format: (v) => fmtPct(v) },
      {
        key: "economy_above_expected",
        label: "Economy vs expected",
        hint: "Lower is better",
        format: (v) => fmtNum(v),
      },
    ];
  }
  return [
    { key: "boundaries_pct", label: "Boundary %", hint: "Higher is better", format: (v) => fmtPct(v) },
    { key: "dots_pct", label: "Dot-ball %", hint: "Lower is better", format: (v) => fmtPct(v) },
    {
      key: "consistency",
      label: "Consistency",
      hint: "Higher is more repeatable",
      format: (v) => fmtNum(v, 2),
    },
    { key: "wpa100", label: "Win-prob added /100", hint: "Higher is better", format: (v) => fmtNum(v, 2) },
  ];
}

function ComponentsChart({ player }) {
  const chart = useChartTheme();
  const metrics = componentMetrics(player.player_type);
  const palette = [chart.pink, chart.sky, chart.emerald, chart.amber];
  const data = metrics
    .filter((metric) => isNumber(player[metric.key]))
    .map((metric, index) => ({
      name: metric.label,
      value: player[metric.key],
      hint: metric.hint,
      display: metric.format(player[metric.key]),
      color: palette[index % palette.length],
    }));

  if (data.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-slate-500 dark:text-slate-400">
        Component metrics are not available for this player.
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={Math.max(170, data.length * 46)}>
      <BarChart data={data} layout="vertical" margin={{ top: 6, right: 64, bottom: 4, left: 4 }}>
        <CartesianGrid horizontal={false} stroke={chart.grid} />
        <XAxis type="number" stroke={chart.axis} tick={{ fontSize: 10, fill: chart.axis }} />
        <YAxis
          type="category"
          dataKey="name"
          width={126}
          stroke={chart.axis}
          tick={{ fontSize: 11, fill: chart.axis }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={chart.tooltip}
          cursor={{ fill: chart.grid, opacity: 0.35 }}
          formatter={(value, _name, item) => [item?.payload?.display ?? fmtNum(value), item?.payload?.hint]}
        />
        <Bar dataKey="value" barSize={18} radius={4} isAnimationActive={false}>
          {data.map((entry) => (
            <Cell key={entry.name} fill={entry.color} />
          ))}
          <LabelList
            dataKey="display"
            position="right"
            style={{ fontSize: 10, fill: chart.axis, fontWeight: 600 }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function FitEditor({ player, allowedStatuses, onSaved }) {
  const [form, setForm] = useState({
    status: player.status ?? "unknown",
    note: player.note ?? "",
    rr_fit: player.rr_fit ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [saveState, setSaveState] = useState(null);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    setForm({
      status: player.status ?? "unknown",
      note: player.note ?? "",
      rr_fit: player.rr_fit ?? "",
    });
  }, [player.player_id, player.status, player.note, player.rr_fit]);

  useEffect(() => {
    setMessage(null);
  }, [player.player_id]);

  const statuses = allowedStatuses?.length ? allowedStatuses : STATUS_ORDER;
  const dirty =
    form.status !== (player.status ?? "unknown") ||
    form.note !== (player.note ?? "") ||
    form.rr_fit !== (player.rr_fit ?? "");

  const save = async () => {
    setSaving(true);
    setSaveState("saving");
    setMessage(null);
    try {
      await api.updateStatus({
        name: player.name,
        status: form.status,
        note: form.note,
        rr_fit: form.rr_fit,
      });
      await onSaved?.();
      setSaveState("saved");
      setMessage({ type: "ok", text: "Saved to the app database." });
    } catch (error) {
      setSaveState("error");
      setMessage({ type: "error", text: error.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-bold text-slate-900 dark:text-white">Availability &amp; RR fit</h2>
          <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
            Saved to the backend SQLite store, keyed by player name.
          </p>
        </div>
        <StatusPill status={form.status} />
      </div>

      <div className="mt-4 space-y-3">
        <div>
          <label htmlFor="fit-status" className="label">
            Availability status
          </label>
          <select
            id="fit-status"
            value={form.status}
            onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))}
            className="select mt-1"
          >
            {statuses.map((status) => (
              <option key={status} value={status}>
                {statusMeta(status).label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-[10px] leading-snug text-slate-400 dark:text-slate-500">
            {statusMeta(form.status).description}
          </p>
        </div>

        <div>
          <label htmlFor="fit-text" className="label">
            RR fit note
          </label>
          <textarea
            id="fit-text"
            rows={3}
            value={form.rr_fit}
            onChange={(event) => setForm((current) => ({ ...current, rr_fit: event.target.value }))}
            placeholder="e.g. Powerplay enforcer; fits RR top order"
            className="input mt-1 resize-y"
          />
        </div>

        <div>
          <label htmlFor="fit-note" className="label">
            Availability note
          </label>
          <textarea
            id="fit-note"
            rows={2}
            value={form.note}
            onChange={(event) => setForm((current) => ({ ...current, note: event.target.value }))}
            placeholder="e.g. Reported auction entry; unverified"
            className="input mt-1 resize-y"
          />
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button type="button" className="btn-primary" onClick={save} disabled={saving || !dirty}>
          {saving ? "Saving…" : "Save"}
        </button>
        <SaveIndicator state={saveState} />
        {message ? (
          <span
            role="status"
            className={cx(
              "text-[11px] font-medium",
              message.type === "ok"
                ? "text-emerald-700 dark:text-emerald-400"
                : "text-red-600 dark:text-red-400",
            )}
          >
            {message.text}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export default function PlayerPage() {
  const { role, playerId } = useParams();
  const [state, setState] = useState({ loading: true, error: null, data: null, status: null });
  const [tab, setTab] = useState("overview");

  const load = useCallback(() => {
    return Promise.all([api.player(role, playerId), api.status()])
      .then(([data, status]) => setState({ loading: false, error: null, data, status }))
      .catch((error) =>
        setState({ loading: false, error: error.message, data: null, status: null }),
      );
  }, [role, playerId]);

  useEffect(() => {
    setState({ loading: true, error: null, data: null, status: null });
    load();
  }, [load]);

  useEffect(() => {
    setTab("overview");
  }, [playerId]);

  if (state.loading) {
    return (
      <div className="space-y-4">
        <LoadingBlock rows={3} />
        <LoadingBlock rows={5} />
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="space-y-4">
        <Link to={`/${role}s`} className="text-sm font-medium text-rr-700 hover:underline dark:text-rr-300">
          ← Back to {role}s
        </Link>
        <ErrorNote message={state.error} onRetry={load} />
      </div>
    );
  }

  const player = state.data.player;
  const badges = flagBadges(player);
  const rolePlural = `${player.player_type}s`;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to={`/${rolePlural}`}
          className="text-sm font-medium text-rr-700 hover:underline dark:text-rr-300"
        >
          ← Back to {rolePlural}
        </Link>
        <Link
          to="/availability"
          className="text-xs font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
        >
          Open availability workspace
        </Link>
      </div>

      <header className="card flex flex-wrap items-center gap-4 p-5 sm:p-6">
        <PlayerAvatar name={player.name} role={player.player_type} size="lg" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-black tracking-tight text-slate-900 sm:text-3xl dark:text-white">
              {player.name}
            </h1>
            <StatusPill status={player.status} />
            <CurrentTeamEditor
              name={player.name}
              currentTeam={player.current_team}
              currentTeamType={player.current_team_type}
              dataTeam={player.latest_IPL_team || player.latest_team}
              dataTeams={state.status?.data_teams ?? []}
              typedTeams={state.status?.typed_teams ?? []}
              status={player.status}
              onChanged={load}
            />
            {player.is_shortlist ? (
              <FlagBadge label="SHORTLIST" tone="emerald" title="Clean top 10 in this role" />
            ) : null}
            {player.is_reserve ? (
              <FlagBadge label="RESERVE" tone="sky" title="Clean ranks 11–20 in this role" />
            ) : null}
          </div>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {player.player_type === "batter" ? "Batter" : "Bowler"} · {player.role || "role n/a"} ·{" "}
            dominant phase {player.dominant_phase || "—"}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <FlagBadges row={player} />
            {badges.length === 0 ? (
              <span className="text-[11px] text-slate-400 dark:text-slate-500">
                No sample or form warnings flagged
              </span>
            ) : null}
          </div>
        </div>
        <dl className="flex shrink-0 gap-4 text-right">
          <div>
            <dt className="label">Clean</dt>
            <dd className="mt-1 flex justify-end">
              <RankChip
                rank={player.clean_rank}
                tone={player.is_shortlist ? "shortlist" : player.is_reserve ? "reserve" : "default"}
              />
            </dd>
          </div>
          <div>
            <dt className="label">All rank</dt>
            <dd className="num mt-1 text-xl font-bold text-slate-900 dark:text-white">
              {fmtInt(player.all_rank ?? player.rank)}
            </dd>
          </div>
          <div>
            <dt className="label">Qual rank</dt>
            <dd className="mt-1 flex justify-end">
              <RankChip
                rank={player.qualified_rank}
                tone={
                  player.qualified_rank <= 10
                    ? "shortlist"
                    : player.qualified_rank <= 20
                      ? "reserve"
                      : "default"
                }
              />
            </dd>
          </div>
        </dl>
      </header>

      <div
        className="inline-flex rounded-xl border border-slate-200 bg-slate-100/70 p-1 dark:border-slate-800 dark:bg-slate-900/70"
        role="tablist"
        aria-label="Player sections"
      >
        {[
          { key: "overview", label: "Overview" },
          { key: "stats", label: "Stats Explorer" },
          { key: "recent", label: "Recent matches" },
        ].map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={tab === item.key}
            onClick={() => setTab(item.key)}
            className={cx(
              "rounded-lg px-4 py-1.5 text-sm font-semibold transition",
              tab === item.key
                ? "bg-white text-slate-900 shadow-sm dark:bg-slate-800 dark:text-white"
                : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "stats" ? (
        <StatsPanel
          playerId={player.player_id}
          playerName={player.name}
          role={player.player_type}
        />
      ) : tab === "recent" ? (
        <RecentMatchesPanel playerId={player.player_id} showFullLink />
      ) : (
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <RubricCard player={player} />
          <section className="card p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                  {player.ranking_source === "rr_2027_master" ? "Analysis score" : "Engine score"}
                </h2>
                <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
                  {player.ranking_source === "rr_2027_master"
                    ? "Supplied source score; ranks are not recomputed in the dashboard."
                    : "Engine composite score fitted from the full data pack."}
                </p>
              </div>
              <div className="text-right">
                <p className="num text-4xl font-black tracking-tight text-rr-700 dark:text-rr-300">
                  {fmtNum(player.score)}
                </p>
                <p className="num text-[11px] text-slate-500 dark:text-slate-400">
                  all-player rank {fmtInt(player.all_rank ?? player.rank)}
                  {player.qualified_rank ? ` · qualified rank ${player.qualified_rank}` : " · below minimum"}
                  {player.rank_interval ? ` · 90% ${player.rank_interval}` : ""}
                </p>
              </div>
            </div>
            <ScoreRangeBar
              score={player.score}
              lo={player.score_lo}
              hi={player.score_hi}
              className="mt-6"
            />
            {player.ranking_source === "rr_2027_master" ? (
              <div className="mt-4 grid grid-cols-2 gap-3">
                <MiniStat
                  label="Data confidence"
                  value={player.data_confidence_100 == null
                    ? "—"
                    : `${fmtNum(player.data_confidence_100, 1)}%`}
                />
                <MiniStat
                  label="Qualification"
                  value={player.source_qualification_status || "—"}
                />
              </div>
            ) : (
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <MiniStat label="Score low" value={fmtNum(player.score_lo)} hint="90% band" />
                <MiniStat label="Score high" value={fmtNum(player.score_hi)} hint="90% band" />
                <MiniStat
                  label="Rank low"
                  value={fmtInt(player.rank_lo)}
                  hint="Best plausible"
                  accent="emerald"
                />
                <MiniStat
                  label="Rank high"
                  value={fmtInt(player.rank_hi)}
                  hint="Worst plausible"
                  accent="pink"
                />
              </div>
            )}
          </section>

          {player.ranking_source === "rr_2027_master" &&
          player.player_type === "bowler" ? null : (
          <section className="card p-5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                  {player.ranking_source === "rr_2027_master"
                    ? "Pressure batting performance"
                    : "Pressure vs normal"}
                </h2>
                <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
                  {player.ranking_source === "rr_2027_master"
                    ? "Strike rate in pressure situations vs normal situations"
                    : "Impact per 100 balls under pressure vs normal conditions"}
                </p>
              </div>
              <p className="num text-xs text-slate-500 dark:text-slate-400">
                Delta{" "}
                <span
                  className={cx(
                    "font-bold",
                    isNumber(player.delta) && player.delta > 0
                      ? "text-emerald-700 dark:text-emerald-400"
                      : isNumber(player.delta) && player.delta < 0
                        ? "text-red-600 dark:text-red-400"
                        : "text-slate-600 dark:text-slate-300",
                  )}
                >
                  {fmtSigned(player.delta)}
                </span>
              </p>
            </div>
            <div className="mt-3">
              <PressureChart player={player} />
            </div>
            <p className="mt-2 text-[10px] leading-relaxed text-slate-400 dark:text-slate-500">
              {player.ranking_source === "rr_2027_master"
                ? "Pressure uses the second-innings chase criteria described in the supplied analysis package."
                : "Positive values are better in the engine impact convention. “Pressure” is the engine’s leverage-defined pressure sample, not the rule-based descriptive pressure module."}
            </p>
          </section>
          )}

          {player.ranking_source === "rr_2027_master" ? null : (
          <section className="card p-5">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">
              Component metrics
            </h2>
            <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
              Raw inputs shown before shrinkage. This is not a decomposition of the composite score.
            </p>
            <div className="mt-3">
              <ComponentsChart player={player} />
            </div>
            <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[10px] text-slate-400 sm:grid-cols-4 dark:text-slate-500">
              {componentMetrics(player.player_type).map((metric) => (
                <span key={metric.key}>
                  <span className="font-semibold text-slate-500 dark:text-slate-400">
                    {metric.label}:
                  </span>{" "}
                  {metric.hint}
                </span>
              ))}
            </div>
          </section>
          )}
        </div>

        <div className="space-y-4">
          <section className="card p-5">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">Sample &amp; stability</h2>
            <div className="mt-3 grid grid-cols-2 gap-2.5">
              <MiniStat label="Pressure balls" value={fmtInt(player.pressure_balls)} hint="Pressure sample" />
              {player.ranking_source === "rr_2027_master" ? (
                <MiniStat label="Balls (source scope)" value={fmtInt(player.IPL_balls)} />
              ) : (
                <>
                  <MiniStat label="IPL balls" value={fmtInt(player.IPL_balls)} />
                  <MiniStat label="T20I balls" value={fmtInt(player.T20I_balls)} />
                </>
              )}
              <MiniStat label="Pressure matches" value={fmtInt(player.pressure_matches)} />
              <MiniStat label="Matches" value={fmtInt(player.matches)} hint={player.experience} />
              {player.ranking_source === "rr_2027_master" ? (
                <>
                  <MiniStat
                    label="Data confidence"
                    value={player.data_confidence_100 == null
                      ? "—"
                      : `${fmtNum(player.data_confidence_100, 1)}%`}
                  />
                  <MiniStat label="Sample marks" value={`${fmtInt(player.sample_marks)}/6`} />
                </>
              ) : (
                <MiniStat
                  label="Experience marks"
                  value={`${fmtInt(player.experience_marks)}/7`}
                  hint="Fixed match table"
                />
              )}
              <MiniStat label="Consistency" value={fmtNum(player.consistency, 2)} hint="Higher is more repeatable" />
              {player.ranking_source === "rr_2027_master" ? null : (
                <>
                  <MiniStat label="EB weight" value={fmtNum(player.eb_weight, 2)} hint="Empirical-Bayes shrink weight" />
                  <MiniStat label="Shrunk perf." value={fmtNum(player.shrunk_performance)} hint="Shrunk performance" />
                  <MiniStat label="Shrunk delta" value={fmtNum(player.shrunk_delta)} hint="Shrunk pressure delta" />
                </>
              )}
            </div>
          </section>

          {player.ranking_source === "rr_2027_master" ? null : (
          <section className="card p-5">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">2026 form</h2>
              <FlagBadge
                label={`RECENT ${String(player.RECENT_FORM_FLAG ?? "—").toUpperCase()}`}
                tone={String(player.RECENT_FORM_FLAG).toUpperCase() === "LOW" ? "amber" : "emerald"}
                title="Recent-form flag from the engine's 2026 pressure sample"
              />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2.5">
              <MiniStat
                label="Played 2026 IPL"
                value={String(player.PLAYED_2026_IPL ?? "—").toUpperCase()}
                accent={String(player.PLAYED_2026_IPL).toUpperCase() === "Y" ? "emerald" : undefined}
              />
              <MiniStat label="2026 balls" value={fmtInt(player.form2026_balls)} hint="2026 IPL sample" />
              <MiniStat
                label="2026 impact /100"
                value={fmtNum(player.form2026_impact100)}
                hint="Recent-form impact"
                accent={
                  isNumber(player.form2026_impact100) && player.form2026_impact100 > 0
                    ? "emerald"
                    : undefined
                }
              />
              <MiniStat
                label="IPL pressure flag"
                value={String(player.IPL_PRESSURE_FLAG ?? "—").toUpperCase()}
                hint="Supplied sample flag"
              />
            </div>
            <p className="mt-3 text-[10px] leading-relaxed text-slate-400 dark:text-slate-500">
              Recent form is reported for information only. It is not an input to the score:
              every pressure ball from 2022-01-22 to 2026-11-01 carries equal weight, and the
              2026 flag is computed after the score. Thin samples are common — read alongside
              the ball count.
            </p>
          </section>
          )}

          <FitEditor
            player={player}
            allowedStatuses={state.status?.allowed_statuses}
            onSaved={load}
          />
        </div>
      </div>
      )}
    </div>
  );
}
