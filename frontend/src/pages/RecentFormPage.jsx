import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import RecentMatchesPanel from "../components/RecentMatchesPanel";
import StatsPanel from "../components/StatsPanel";
import { ErrorNote, LoadingBlock } from "../components/States";
import { cx } from "../utils";

export default function RecentFormPage() {
  const { playerId } = useParams();
  const [state, setState] = useState({
    loading: true,
    error: null,
    recent: null,
    stats: null,
  });
  const [tab, setTab] = useState("form");

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, error: null, recent: null, stats: null });
    Promise.allSettled([api.recent(playerId), api.stats(playerId)]).then(([recent, stats]) => {
      if (cancelled) return;
      const recentValue = recent.status === "fulfilled" ? recent.value : null;
      const statsValue = stats.status === "fulfilled" ? stats.value : null;
      const error =
        recentValue || statsValue
          ? null
          : recent.reason?.message || stats.reason?.message || "No data found for this player.";
      setState({ loading: false, error, recent: recentValue, stats: statsValue });
      setTab(recentValue ? "form" : "stats");
    });
    return () => {
      cancelled = true;
    };
  }, [playerId]);

  if (state.loading) return <LoadingBlock rows={6} />;

  const profile = state.recent?.player?.profile;
  const name = state.stats?.name || profile?.name || `Player ${playerId}`;
  const role = state.stats?.role || profile?.role || "batter";
  const latestTeam = state.stats?.latest_team || profile?.latest_team;
  const ranking = state.recent?.ranking;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link
          to="/stats-explorer"
          className="text-sm font-medium text-rr-700 hover:underline dark:text-rr-300"
        >
          ← Back to Stats Explorer
        </Link>
        {ranking ? (
          <Link
            to={`/player/${ranking.player_type || role}/${playerId}`}
            className="text-xs font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
          >
            Open player profile →
          </Link>
        ) : null}
      </div>

      <header className="card flex flex-wrap items-center justify-between gap-3 p-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">{name}</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            <span className="capitalize">{role}</span>
            {latestTeam ? ` · ${latestTeam}` : ""}
            {profile?.first_match_date ? ` · data ${profile.first_match_date} → ${profile.last_match_date}` : ""}
          </p>
        </div>
        <div className="text-right text-xs text-slate-400 dark:text-slate-500">
          <p>Recent form is shown for context; the supplied analysis score includes its own recent-form component.</p>
          <p>Aggregate stats are computed separately from deliveries.</p>
        </div>
      </header>

      <div
        className="inline-flex rounded-xl border border-slate-200 bg-slate-100/70 p-1 dark:border-slate-800 dark:bg-slate-900/70"
        role="tablist"
        aria-label="Recent form sections"
      >
        {[
          { key: "form", label: "Recent form" },
          { key: "stats", label: "Stats" },
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
        <StatsPanel playerId={playerId} playerName={name} role={role} />
      ) : (
        <RecentMatchesPanel
          playerId={playerId}
          recent={state.recent}
          error={state.error}
          fetchOnMount={false}
        />
      )}
    </div>
  );
}
