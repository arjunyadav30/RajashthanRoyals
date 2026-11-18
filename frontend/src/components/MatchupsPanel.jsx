import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { ErrorNote, LoadingBlock } from "./States";
import { cx, fmtInt, fmtNum } from "../utils";

const MIN_OPTIONS = [6, 12, 24];

function rate(value, digits = 1) {
  return value === null || value === undefined ? "—" : fmtNum(value, digits);
}

function pct(value) {
  return value === null || value === undefined ? "—" : `${fmtNum(value, 1)}%`;
}

export default function MatchupsPanel({ playerId, playerName, role = "batter" }) {
  const [state, setState] = useState({ loading: true, error: null, data: null });
  const [side, setSide] = useState(role === "bowler" ? "bowling" : "batting");
  const [minBalls, setMinBalls] = useState(6);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, error: null, data: null });
    api
      .matchups(playerId, { role })
      .then((data) => {
        if (!cancelled) setState({ loading: false, error: null, data });
      })
      .catch((error) => {
        if (!cancelled) setState({ loading: false, error: error.message, data: null });
      });
    return () => {
      cancelled = true;
    };
  }, [playerId, role]);

  const data = state.data;
  const canBat = Boolean(data?.batting?.length);
  const canBowl = Boolean(data?.bowling?.length);
  const activeSide = side === "bowling" && canBowl ? "bowling" : canBat ? "batting" : "bowling";
  const rows = data?.[activeSide] || [];
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return rows
      .filter((row) => row.balls >= minBalls)
      .filter((row) => !needle || row.opponent.toLowerCase().includes(needle))
      .sort((a, b) => b.balls - a.balls || a.opponent.localeCompare(b.opponent));
  }, [rows, minBalls, query]);
  const totalBalls = filtered.reduce((sum, row) => sum + row.balls, 0);

  if (state.loading) return <LoadingBlock rows={5} />;
  if (state.error) return <ErrorNote message={state.error} />;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <p className="text-sm font-bold text-slate-900 dark:text-white">Head-to-head matchups</p>
          <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
            {canBat && activeSide === "batting"
              ? `${playerName} against each bowler`
              : `${playerName} against each batter`}
            {" · "}
            {fmtInt(filtered.length)} opponents, {fmtInt(totalBalls)} balls shown
          </p>
        </div>
        {canBat && canBowl ? (
          <div className="ml-auto inline-flex rounded-lg border border-slate-200 bg-white p-0.5 dark:border-slate-700 dark:bg-slate-900">
            <button
              type="button"
              className={cx(
                "rounded-md px-3 py-1 text-xs font-semibold",
                activeSide === "batting" ? "bg-rr-600 text-white" : "text-slate-500",
              )}
              onClick={() => setSide("batting")}
            >
              As batter
            </button>
            <button
              type="button"
              className={cx(
                "rounded-md px-3 py-1 text-xs font-semibold",
                activeSide === "bowling" ? "bg-rr-600 text-white" : "text-slate-500",
              )}
              onClick={() => setSide("bowling")}
            >
              As bowler
            </button>
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400">
          <span>Search opponent</span>
          <input
            className="input h-8 w-48 py-1 text-xs"
            value={query}
            placeholder="Name…"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label className="flex items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400">
          <span>Minimum balls</span>
          <select
            className="select h-8 w-20 py-1 text-xs"
            value={minBalls}
            onChange={(event) => setMinBalls(Number(event.target.value))}
          >
            {MIN_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <p className="text-[10px] text-slate-400 dark:text-slate-500">
          Every pair with 6+ balls is stored; raise the minimum to reduce noise.
        </p>
      </div>

      {filtered.length ? (
        <div className="max-h-[34rem] overflow-auto rounded-xl border border-slate-200 dark:border-slate-800">
          <table className="w-full min-w-[820px] border-collapse text-xs">
            <thead className="sticky top-0 z-10 bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500 dark:bg-slate-900 dark:text-slate-400">
              <tr>
                <th className="px-3 py-2 text-left">Opponent</th>
                <th className="px-2 py-2 text-right">Balls</th>
                <th className="px-2 py-2 text-right">Runs</th>
                <th className="px-2 py-2 text-right">{activeSide === "batting" ? "Outs" : "Wkts"}</th>
                <th className="px-2 py-2 text-right">{activeSide === "batting" ? "SR" : "Econ"}</th>
                <th className="px-2 py-2 text-right">Dot %</th>
                <th className="px-2 py-2 text-right">Boundary %</th>
                <th className="px-2 py-2 text-right">Pressure B/R/{activeSide === "batting" ? "O" : "W"}</th>
                <th className="px-2 py-2 text-right">IPL / T20I balls</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr
                  key={`${row.opponent_id}-${row.balls}`}
                  className="border-t border-slate-100 text-slate-700 odd:bg-white even:bg-slate-50/50 dark:border-slate-800 dark:text-slate-200 dark:odd:bg-slate-950 dark:even:bg-slate-900/40"
                >
                  <td className="px-3 py-1.5 font-semibold">
                    {row.opponent}
                    {row.balls < 12 ? (
                      <span
                        className="ml-1.5 rounded bg-amber-100 px-1 py-0.5 text-[9px] font-bold text-amber-800 dark:bg-amber-950/50 dark:text-amber-200"
                        title="Fewer than 12 balls: descriptive only"
                      >
                        small
                      </span>
                    ) : null}
                  </td>
                  <td className="num px-2 py-1.5 text-right font-semibold">{fmtInt(row.balls)}</td>
                  <td className="num px-2 py-1.5 text-right">{fmtInt(row.runs)}</td>
                  <td className="num px-2 py-1.5 text-right">
                    {fmtInt(activeSide === "batting" ? row.dismissals : row.wickets)}
                  </td>
                  <td className="num px-2 py-1.5 text-right">
                    {activeSide === "batting" ? rate(row.strike_rate) : rate(row.economy, 2)}
                  </td>
                  <td className="num px-2 py-1.5 text-right">{pct(row.dot_pct)}</td>
                  <td className="num px-2 py-1.5 text-right">{pct(row.boundary_pct)}</td>
                  <td className="num px-2 py-1.5 text-right text-slate-500 dark:text-slate-400">
                    {fmtInt(row.pressure_balls)}/{fmtInt(row.pressure_runs)}/
                    {fmtInt(activeSide === "batting" ? row.pressure_dismissals : row.pressure_wickets)}
                  </td>
                  <td className="num px-2 py-1.5 text-right text-slate-500 dark:text-slate-400">
                    {fmtInt(row.ipl_balls)} / {fmtInt(row.t20i_balls)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-slate-300 p-4 text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
          No {activeSide === "batting" ? "bowler" : "batter"} matchup has {minBalls}+ balls
          {query ? ` matching “${query}”` : ""}. Lower the minimum or clear the search.
        </p>
      )}

      <p className="rounded-xl border border-dashed border-slate-300 p-3 text-[10px] leading-relaxed text-slate-500 dark:border-slate-700 dark:text-slate-400">
        Aggregate head-to-head records across IPL and T20I matches from 2022-01-22 to
        2026-11-01. Balls faced exclude wides; bowler balls are legal deliveries. Runs are bat
        runs for batters and charged runs for bowlers. Outs include all dismissals; bowler
        wickets exclude run-outs and retirements. Pressure is the descriptive, rule-based split,
        not the engine leverage flag. Pairs under 12 balls are marked small. No delivery-level
        rows are exposed.
      </p>
    </div>
  );
}
