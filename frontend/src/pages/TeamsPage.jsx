import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { LockBanner } from "../components/AuthGate";
import { RankChip } from "../components/Badges";
import { EmptyState, ErrorNote, LoadingBlock } from "../components/States";
import { cx, fmtInt, fmtNum, PUBLIC_ROW_LIMIT } from "../utils";

const CARD_METRICS = [
  { key: "batting", label: "Batting" },
  { key: "bowling", label: "Bowling" },
  { key: "depth", label: "Depth" },
  { key: "pressure", label: "Pressure" },
  { key: "experience", label: "Experience" },
];

const DIMENSION_LABELS = {
  batting: "Batting",
  bowling: "Bowling",
  depth: "Depth",
  pressure: "Pressure",
  experience: "Experience",
  death_options: "Death options",
  powerplay_batters: "PP batters",
  all_rounders: "All-rounders",
};

function rankTone(rank) {
  if (rank <= 3) return "shortlist";
  if (rank <= 6) return "reserve";
  return "default";
}

function metricValue(key, value) {
  return key === "experience" ? fmtInt(value) : fmtNum(value);
}

function TeamCard({ team }) {
  const headliners = team.xi.slice(0, 5).map((player) => player.name);
  const remaining = team.xi.length - headliners.length;
  return (
    <Link
      to={`/teams/${team.slug}`}
      className="card group flex flex-col gap-4 p-5 transition hover:-translate-y-0.5 hover:border-rr-300 hover:shadow-md dark:hover:border-rr-700"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            IPL 2027 squad
          </p>
          <h2 className="mt-0.5 truncate text-lg font-black tracking-tight text-slate-900 group-hover:text-rr-700 dark:text-white dark:group-hover:text-rr-300">
            {team.name}
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {team.roster_count} players · {team.scored_count} scored · {team.overseas} overseas in XI
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="num text-2xl font-black leading-none text-slate-900 dark:text-white">
            {fmtNum(team.xi_average)}
          </p>
          <p className="mt-1 text-[10px] font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">
            XI average
          </p>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-1.5 rounded-xl border border-slate-100 bg-slate-50/70 p-2 text-center dark:border-slate-800 dark:bg-slate-900/40">
        {CARD_METRICS.map(({ key, label }) => (
          <div key={key} className="min-w-0">
            <p className="num truncate text-sm font-bold text-slate-800 dark:text-slate-100">
              {metricValue(key, team[key])}
            </p>
            <p className="truncate text-[9px] font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">
              {label}
            </p>
            <p className="num text-[9px] text-slate-400 dark:text-slate-500">#{team.ranks[key]}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <div className="rounded-lg border border-emerald-200/70 bg-emerald-50/60 p-2.5 dark:border-emerald-900/50 dark:bg-emerald-950/20">
          <p className="text-[9px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
            Strengths
          </p>
          <ul className="mt-1 space-y-1">
            {team.strengths.map((item) => (
              <li key={item.key} className="flex items-start gap-1.5 text-[11px] leading-snug">
                <span className="num mt-px shrink-0 font-bold text-emerald-700 dark:text-emerald-400">
                  #{item.rank}
                </span>
                <span className="min-w-0 text-slate-700 dark:text-slate-300">{item.label}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-red-200/70 bg-red-50/60 p-2.5 dark:border-red-900/50 dark:bg-red-950/20">
          <p className="text-[9px] font-bold uppercase tracking-wider text-red-700 dark:text-red-400">
            Weaknesses
          </p>
          <ul className="mt-1 space-y-1">
            {team.weaknesses.map((item) => (
              <li key={item.key} className="flex items-start gap-1.5 text-[11px] leading-snug">
                <span className="num mt-px shrink-0 font-bold text-red-700 dark:text-red-400">
                  #{item.rank}
                </span>
                <span className="min-w-0 text-slate-700 dark:text-slate-300">{item.label}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
          Likely XI
        </p>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-600 dark:text-slate-400">
          {headliners.join(", ")}
          {remaining > 0 ? ` +${remaining} more` : ""}
        </p>
      </div>

      <div className="mt-auto flex items-center justify-between border-t border-slate-100 pt-3 text-[11px] dark:border-slate-800">
        <div className="flex flex-wrap items-center gap-1">
          {["batting", "bowling", "death_options"].map((key) => (
            <span
              key={key}
              className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-1.5 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
              title={`${DIMENSION_LABELS[key]} league rank`}
            >
              {DIMENSION_LABELS[key]}
              <RankChip rank={team.ranks[key]} tone={rankTone(team.ranks[key])} />
            </span>
          ))}
        </div>
        <span className="font-semibold text-rr-700 group-hover:underline dark:text-rr-300">
          Full profile →
        </span>
      </div>
    </Link>
  );
}

export default function TeamsPage() {
  const { authenticated } = useAuth();
  const [state, setState] = useState({ loading: true, error: null, payload: null, empty: false });

  const load = useCallback(() => {
    setState((current) => ({ ...current, loading: true, error: null }));
    return api
      .teams()
      .then((payload) => setState({ loading: false, error: null, payload, empty: false }))
      .catch((error) => {
        if (error.status === 404) {
          setState({ loading: false, error: null, payload: null, empty: true });
          return;
        }
        setState((current) => ({ ...current, loading: false, error: error.message }));
      });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const summary = useMemo(() => {
    const teams = state.payload?.teams ?? [];
    const roster = teams.reduce((sum, team) => sum + team.roster_count, 0);
    const scored = teams.reduce((sum, team) => sum + team.scored_count, 0);
    const xiAverage =
      teams.length > 0
        ? teams.reduce((sum, team) => sum + team.xi_average, 0) / teams.length
        : null;
    return { teams: teams.length, roster, scored, xiAverage };
  }, [state.payload]);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label">IPL 2027 squads</p>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-900 sm:text-3xl dark:text-white">
            Teams
          </h1>
          <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">
            Every squad assigned a current team, scored with the same pressure engine used for the
            auction pool. Each profile shows league ranks, the data-driven best XI, strengths and
            weaknesses, and the players left on the bench.
          </p>
        </div>
        {state.payload ? (
          <div className="flex flex-wrap gap-2 text-center">
            <div className="rounded-xl border border-slate-200 px-3 py-2 dark:border-slate-800">
              <p className="num text-lg font-black text-slate-900 dark:text-white">{summary.teams}</p>
              <p className="text-[10px] uppercase tracking-wide text-slate-400">Teams</p>
            </div>
            <div className="rounded-xl border border-slate-200 px-3 py-2 dark:border-slate-800">
              <p className="num text-lg font-black text-slate-900 dark:text-white">{summary.roster}</p>
              <p className="text-[10px] uppercase tracking-wide text-slate-400">Players</p>
            </div>
            <div className="rounded-xl border border-slate-200 px-3 py-2 dark:border-slate-800">
              <p className="num text-lg font-black text-slate-900 dark:text-white">{summary.scored}</p>
              <p className="text-[10px] uppercase tracking-wide text-slate-400">Scored</p>
            </div>
            <div className="rounded-xl border border-slate-200 px-3 py-2 dark:border-slate-800">
              <p className="num text-lg font-black text-slate-900 dark:text-white">
                {fmtNum(summary.xiAverage)}
              </p>
              <p className="text-[10px] uppercase tracking-wide text-slate-400">Avg XI</p>
            </div>
          </div>
        ) : null}
      </header>

      {state.error ? <ErrorNote message={state.error} onRetry={load} /> : null}

      {state.loading ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <LoadingBlock rows={4} />
          <LoadingBlock rows={4} className="hidden lg:block" />
        </div>
      ) : state.empty ? (
        <EmptyState
          title="No teams assigned yet"
          hint="Set a current team for players in the Availability workspace, then this page will build every squad profile automatically."
          className="card py-16"
        />
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            {(state.payload?.teams ?? [])
              .slice(0, authenticated ? undefined : PUBLIC_ROW_LIMIT)
              .map((team) => (
                <TeamCard key={team.slug} team={team} />
              ))}
          </div>
          {authenticated ? null : (
            <LockBanner
              shown={Math.min(summary.teams, PUBLIC_ROW_LIMIT)}
              total={summary.teams}
              noun="teams"
            />
          )}
          <p className="text-[11px] leading-relaxed text-slate-400 dark:text-slate-500">
            Squads come from the current-team field you set in{" "}
            <Link to="/availability" className="link">
              Availability
            </Link>
            . Ranks are 1–10 across the ten squads (1 is best); the XI is selected by source score
            with a wicketkeeper, at least five batting and four bowling options, and a maximum of
            four overseas players.
          </p>
        </>
      )}
    </div>
  );
}
