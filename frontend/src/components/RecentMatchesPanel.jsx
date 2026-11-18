import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { EmptyState, ErrorNote, LoadingBlock } from "./States";
import { fmtInt, fmtNum } from "../utils";

const WINDOWS = [
  ["last5", "Last 5 matches"],
  ["last10", "Last 10 matches"],
  ["last20", "Last 20 matches"],
  ["career", "Career window"],
];

function Mini({ label, value, hint }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-950/40">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
        {label}
      </p>
      <p className="num mt-1 text-lg font-black leading-none text-slate-900 dark:text-white">
        {value}
      </p>
      {hint ? (
        <p className="mt-1 text-[9px] text-slate-400 dark:text-slate-500">{hint}</p>
      ) : null}
    </div>
  );
}

function WindowSummary({ window }) {
  if (!window) return null;
  const batting = window.batting;
  const bowling = window.bowling;
  return (
    <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
      <Mini
        label="Matches"
        value={fmtInt(window.matches)}
        hint={`${window.from_date || "—"} → ${window.to_date || "—"}`}
      />
      {batting ? (
        <>
          <Mini label="Runs" value={fmtInt(batting.runs)} hint={`${fmtInt(batting.balls)} balls`} />
          <Mini
            label="Strike rate"
            value={fmtNum(batting.strike_rate, 1)}
            hint={`${fmtInt(batting.fours)} fours · ${fmtInt(batting.sixes)} sixes`}
          />
          <Mini
            label="Dismissals"
            value={fmtInt(batting.dismissals)}
            hint={`Dot % ${fmtNum(batting.dot_pct, 1)}`}
          />
        </>
      ) : null}
      {bowling ? (
        <>
          <Mini
            label="Legal balls"
            value={fmtInt(bowling.legal_balls)}
            hint={bowling.small_sample ? "Small sample" : "≥ 30 legal balls"}
          />
          <Mini
            label="Wickets"
            value={fmtInt(bowling.wickets)}
            hint={`${fmtInt(bowling.runs)} runs conceded`}
          />
          <Mini
            label="Economy"
            value={fmtNum(bowling.economy, 2)}
            hint={`Dot % ${fmtNum(bowling.dot_pct, 1)}`}
          />
          <Mini
            label="Wicket %"
            value={fmtNum(bowling.wicket_pct, 1)}
            hint="Wickets per 100 legal balls"
          />
        </>
      ) : null}
    </div>
  );
}

export default function RecentMatchesPanel({
  playerId,
  recent: providedRecent,
  error: providedError,
  fetchOnMount = true,
  showFullLink = false,
}) {
  const [state, setState] = useState({ loading: fetchOnMount, error: null, recent: null });
  const [windowKey, setWindowKey] = useState("last20");

  useEffect(() => {
    setWindowKey("last20");
    if (!fetchOnMount) {
      setState({ loading: false, error: null, recent: null });
      return undefined;
    }

    let cancelled = false;
    setState({ loading: true, error: null, recent: null });
    api
      .recent(playerId)
      .then((recent) => {
        if (!cancelled) setState({ loading: false, error: null, recent });
      })
      .catch((error) => {
        if (!cancelled) setState({ loading: false, error: error.message, recent: null });
      });
    return () => {
      cancelled = true;
    };
  }, [fetchOnMount, playerId]);

  if (fetchOnMount && state.loading) return <LoadingBlock rows={5} />;
  const recent = fetchOnMount ? state.recent : providedRecent;
  const error = fetchOnMount ? state.error : providedError;
  if (error && !recent) return <ErrorNote message={error} />;
  if (!recent) {
    return (
      <EmptyState
        title="No recent-match data for this player"
        hint="Career and split aggregates remain available in the Stats Explorer tab."
      />
    );
  }

  const window = recent.player?.windows?.[windowKey];
  const matches = recent.player?.matches || [];
  const matchesForWindow =
    windowKey === "career"
      ? matches
      : matches.slice(0, windowKey === "last5" ? 5 : windowKey === "last10" ? 10 : 20);
  const visibleMatches = matchesForWindow;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Match window
        </label>
        <select
          className="select h-8 w-44 py-1 text-xs"
          value={windowKey}
          onChange={(event) => setWindowKey(event.target.value)}
        >
          {WINDOWS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <span className="text-[10px] text-slate-400 dark:text-slate-500">
          Matches where the player batted or bowled.
        </span>
        {showFullLink ? (
          <Link
            to={`/recent-form/${playerId}`}
            className="ml-auto text-xs font-medium text-rr-700 hover:underline dark:text-rr-300"
          >
            Open full recent-form view →
          </Link>
        ) : null}
      </div>

      <section className="card p-5">
        <WindowSummary window={window} />
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-left text-[10px] uppercase tracking-wider text-slate-400 dark:border-slate-800">
                <th className="py-1.5 pr-3 font-semibold">Date</th>
                <th className="py-1.5 pr-3 font-semibold">Competition</th>
                <th className="py-1.5 pr-3 font-semibold">Opponent</th>
                <th className="py-1.5 pr-3 text-right font-semibold">Batting</th>
                <th className="py-1.5 text-right font-semibold">Bowling</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/70">
              {visibleMatches.map((match) => (
                <tr key={match.match_id}>
                  <td className="num py-1.5 pr-3 text-slate-500 dark:text-slate-400">
                    {match.match_date}
                  </td>
                  <td className="py-1.5 pr-3 text-slate-600 dark:text-slate-300">
                    {match.competition}
                  </td>
                  <td className="py-1.5 pr-3 text-slate-600 dark:text-slate-300">
                    {match.opponent}
                  </td>
                  <td className="num py-1.5 pr-3 text-right text-slate-700 dark:text-slate-200">
                    {match.batting
                      ? `${fmtInt(match.batting.runs)} (${fmtInt(match.batting.balls)})${match.batting.dismissed ? "" : " *"}`
                      : "—"}
                  </td>
                  <td className="num py-1.5 text-right text-slate-700 dark:text-slate-200">
                    {match.bowling
                      ? `${fmtInt(match.bowling.wickets)}/${fmtInt(match.bowling.runs)} · ${fmtNum(match.bowling.economy, 2)} econ`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {error ? <p className="mt-3 text-[10px] text-amber-700 dark:text-amber-400">{error}</p> : null}
      </section>
    </div>
  );
}
