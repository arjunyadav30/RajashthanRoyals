import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { FlagBadges, PlayerAvatar, StatusPill } from "../components/Badges";
import StatCard from "../components/StatCard";
import { ErrorNote, LoadingBlock, ReadyBanner } from "../components/States";
import { fmtDateTime, fmtInt, fmtNum } from "../utils";

function TopFiveRow({ row, index }) {
  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <span className="num w-5 shrink-0 text-sm font-bold text-slate-400 dark:text-slate-500">
        {index + 1}
      </span>
      <PlayerAvatar name={row.name} role={row.player_type} size="sm" />
      <div className="min-w-0 flex-1">
        <Link
          to={`/player/${row.player_type}/${row.player_id}`}
          className="block truncate text-sm font-semibold text-slate-900 hover:text-rr-700 dark:text-white dark:hover:text-rr-300"
        >
          {row.name}
        </Link>
        <p className="truncate text-[11px] text-slate-500 dark:text-slate-400">
          {row.team_label || "Team unknown"} · {row.dominant_phase || "—"}
        </p>
      </div>
      <div className="shrink-0 text-right">
        <p className="num text-sm font-black text-rr-700 dark:text-rr-300">
          {fmtNum(row.rating100, 1)}
        </p>
        <p className="num text-[10px] text-slate-400 dark:text-slate-500">
          /100 · {fmtInt(row.matches)} matches
        </p>
      </div>
      <div className="hidden w-24 shrink-0 justify-end sm:flex">
        <FlagBadges row={row} />
      </div>
    </li>
  );
}

function TopFiveCard({ title, rows, role }) {
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">{title}</h3>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            Top 5 available by 0–100 auction rating
          </p>
        </div>
        <Link
          to={`/${role}s`}
          className="text-xs font-semibold text-rr-700 hover:underline dark:text-rr-300"
        >
          View all
        </Link>
      </div>
      {rows.length === 0 ? (
        <p className="px-4 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
          No available {role}s yet. Set availability statuses to build the pool.
        </p>
      ) : (
        <ul className="divide-y divide-slate-100 dark:divide-slate-800/70">
          {rows.map((row, index) => (
            <TopFiveRow key={`${row.player_type}-${row.player_id}`} row={row} index={index} />
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Overview() {
  const [state, setState] = useState({ loading: true, error: null, data: null });

  const load = useCallback(() => {
    setState({ loading: true, error: null, data: null });
    api
      .summary()
      .then((data) => setState({ loading: false, error: null, data }))
      .catch((error) => setState({ loading: false, error: error.message, data: null }));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const summary = state.data;

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-3xl border border-rr-200/60 bg-gradient-to-br from-white via-white to-rr-50 p-6 shadow-card sm:p-8 dark:border-rr-500/20 dark:from-slate-900 dark:via-slate-900 dark:to-rr-900/25">
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-rr-400/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 right-24 h-48 w-48 rounded-full bg-sky-400/10 blur-3xl" />
        <div className="relative max-w-3xl">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-rr-700 dark:text-rr-300">
            SupeRR Selector · Season 2 · IPL 2027 auction
          </p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-900 sm:text-4xl dark:text-white">
            Reliability Under Pressure
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600 sm:text-base dark:text-slate-300">
            Player ranks and 100-point scores come from the supplied RR 2027 analysis package,
            covering IPL 2022–2026 and T20I competitions in the pack. Compare the separate
            batter and bowler rankings, then use the availability workspace to build a shortlist.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link to="/batters" className="btn-primary">
              Batter rankings
            </Link>
            <Link to="/bowlers" className="btn-ghost">
              Bowler rankings
            </Link>
            <Link to="/availability" className="btn-ghost">
              Availability workspace
            </Link>
          </div>
        </div>
      </section>

      {state.error ? <ErrorNote message={state.error} onRetry={load} /> : null}
      {state.loading ? <LoadingBlock rows={4} /> : null}

      {summary ? (
        <>
          <ReadyBanner ready={summary.ready} message={summary.message} />

          <section aria-label="Key figures">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
              <StatCard
                label="Ranked batters"
                value={fmtInt(summary.qualifying_batters)}
                hint="Source-ranked batter rows"
                accent="pink"
              />
              <StatCard
                label="Ranked bowlers"
                value={fmtInt(summary.qualifying_bowlers)}
                hint="Source-ranked bowler rows"
                accent="sky"
              />
              <StatCard
                label="Available pool"
                value={fmtInt(summary.available_pool)}
                hint="Pool + unknown status"
                accent="emerald"
              />
              <StatCard
                label="Available batters"
                value={fmtInt(summary.available_batters)}
                hint="Eligible for clean batter rank"
              />
              <StatCard
                label="Available bowlers"
                value={fmtInt(summary.available_bowlers)}
                hint="Eligible for clean bowler rank"
              />
              <StatCard
                label="Last precompute"
                value={
                  <span className="text-sm font-semibold leading-tight">
                    {summary.last_updated ? fmtDateTime(summary.last_updated) : "—"}
                  </span>
                }
                hint="data_derived/meta.json"
              />
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-2" aria-label="Top available players">
            <TopFiveCard
              title="Top 5 available batters"
              rows={summary.top5?.batter ?? []}
              role="batter"
            />
            <TopFiveCard
              title="Top 5 available bowlers"
              rows={summary.top5?.bowler ?? []}
              role="bowler"
            />
          </section>

          <section className="grid gap-4 lg:grid-cols-3">
            <div className="card p-5 lg:col-span-2">
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">How to read this dashboard</h2>
              <ul className="mt-3 space-y-2 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                <li>
                  <span className="font-semibold text-slate-900 dark:text-white">Analysis score</span>{" "}
                  is the supplied role-specific score out of 100. Data confidence is shown
                  separately and is not added to the score.
                </li>
                <li>
                  <span className="font-semibold text-slate-900 dark:text-white">Clean rank</span>{" "}
                  re-numbers the available pool by source score within each role. The all-player
                  and qualified ranks are taken directly from the analysis package.
                </li>
                <li>
                  <span className="font-semibold text-slate-900 dark:text-white">Availability</span>{" "}
                  is scouting judgement keyed by player name in <code>status.json</code>. Pool and
                  unknown count as available; retained, RR-owned and no-IPL do not.
                </li>
                <li>
                  <span className="font-semibold text-slate-900 dark:text-white">Pressure</span>{" "}
                  columns describe the source analysis and are not predictions of future performance.
                </li>
              </ul>
            </div>

            <div className="card p-5">
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">Readiness</h2>
              <dl className="mt-3 space-y-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500 dark:text-slate-400">Ranking files</dt>
                  <dd>
                    <StatusPill status={summary.ready ? "pool" : "unknown"} />
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500 dark:text-slate-400">Batter rows</dt>
                  <dd className="num font-semibold">{fmtInt(summary.qualifying_batters)}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500 dark:text-slate-400">Bowler rows</dt>
                  <dd className="num font-semibold">{fmtInt(summary.qualifying_bowlers)}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-slate-500 dark:text-slate-400">Pool size</dt>
                  <dd className="num font-semibold">{fmtInt(summary.available_pool)}</dd>
                </div>
              </dl>
              {summary.message ? (
                <p className="mt-4 rounded-lg bg-slate-50 p-2.5 text-[11px] leading-relaxed text-slate-500 dark:bg-slate-950 dark:text-slate-400">
                  {summary.message}
                </p>
              ) : null}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
