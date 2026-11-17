import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ErrorNote, LoadingBlock, ReadyBanner } from "../components/States";
import { filterInactivePlayers, getPlayerDirectoryTotals } from "../availablePlayers";
import { fmtInt, fmtNum } from "../utils";
import { IPL_TEAMS } from "../teams";

const QUICK_LINKS = [
  {
    to: "/players",
    eyebrow: "Player universe",
    title: "All players",
    detail: "Browse the complete directory and scouting filters.",
    icon: "01",
  },
  {
    to: "/auction-board",
    eyebrow: "Decision room",
    title: "Auction board",
    detail: "Build a role-by-role shortlist from the active pool.",
    icon: "02",
  },
  {
    to: "/teams",
    eyebrow: "Squad analysis",
    title: "Compare teams",
    detail: "Explore squad balance, strengths and best XIs.",
    icon: "03",
  },
  {
    to: "/stats-explorer",
    eyebrow: "Deep analysis",
    title: "Stats Explorer",
    detail: "Search and compare career aggregates across competitions.",
    icon: "04",
  },
];

function rankedActivePlayers(players) {
  const active = filterInactivePlayers(players ?? []);
  const available = active
    .filter((player) => player.available && player.clean_rank != null)
    .sort((a, b) => a.clean_rank - b.clean_rank);
  const cleanRanks = new Map(
    available.map((player, index) => [String(player.player_id), index + 1]),
  );
  return active
    .map((player) => ({
      ...player,
      clean_rank: cleanRanks.get(String(player.player_id)) ?? null,
    }))
    .sort((a, b) => (a.clean_rank ?? Infinity) - (b.clean_rank ?? Infinity));
}

function uniquePlayerCount(rows) {
  return new Set(rows.map((row) => String(row.player_id ?? row.name))).size;
}

function Spotlight({ role, players }) {
  const title = role === "batter" ? "Batting board" : "Bowling board";
  const subtitle =
    role === "batter" ? "Highest-ranked active batters" : "Highest-ranked active bowlers";

  return (
    <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <header className="flex items-end justify-between gap-3 border-b border-slate-100 px-5 py-4 dark:border-slate-800">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-rr-600 dark:text-rr-300">
            {subtitle}
          </p>
          <h2 className="mt-1 text-lg font-black text-slate-950 dark:text-white">{title}</h2>
        </div>
        <Link
          to={role === "batter" ? "/batters" : "/bowlers"}
          className="shrink-0 text-xs font-bold text-rr-700 hover:underline dark:text-rr-300"
        >
          Full rankings →
        </Link>
      </header>
      {players.length ? (
        <ol className="divide-y divide-slate-100 dark:divide-slate-800">
          {players.slice(0, 5).map((player, index) => (
            <li
              key={`${role}-${player.player_id}`}
              className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
            >
              <span className="num flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-black text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div className="min-w-0 flex-1">
                <Link
                  to={`/player/${role}/${player.player_id}`}
                  className="block truncate text-sm font-bold text-slate-900 hover:text-rr-700 dark:text-white dark:hover:text-rr-300"
                >
                  {player.name}
                </Link>
                <p className="mt-0.5 truncate text-[11px] text-slate-500 dark:text-slate-400">
                  {fmtInt(player.matches)} matches
                  {player.dominant_phase ? ` · ${player.dominant_phase}` : ""}
                  {player.effective_team ? ` · ${player.effective_team}` : ""}
                </p>
              </div>
              <div className="w-16 shrink-0 text-right">
                <p className="num text-sm font-black text-rr-700 dark:text-rr-300">
                  {fmtNum(player.rating100, 1)}
                </p>
                <p className="text-[9px] font-bold uppercase tracking-wide text-slate-400">
                  score /100
                </p>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p className="px-5 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
          No active available {role} rankings to show.
        </p>
      )}
    </section>
  );
}

export default function GuidePage() {
  const [state, setState] = useState({
    loading: true,
    error: null,
    loaded: false,
    ready: false,
    message: "",
    batters: [],
    bowlers: [],
    directoryTotals: null,
  });

  const load = useCallback(() => {
    setState((current) => ({ ...current, loading: true, error: null }));
    return Promise.all([
      api.players({ role: "batter", availableOnly: false }),
      api.players({ role: "bowler", availableOnly: false }),
    ])
      .then(([batterPayload, bowlerPayload]) => {
        setState({
          loading: false,
          error: null,
          loaded: true,
          ready: batterPayload.ready && bowlerPayload.ready,
          message: batterPayload.message || bowlerPayload.message || "",
          batters: rankedActivePlayers(batterPayload.players),
          bowlers: rankedActivePlayers(bowlerPayload.players),
          directoryTotals: getPlayerDirectoryTotals(
            batterPayload.players ?? [],
            bowlerPayload.players ?? [],
          ),
        });
      })
      .catch((error) => {
        setState((current) => ({
          ...current,
          loading: false,
          loaded: false,
          ready: false,
          error: error.message,
        }));
      });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const allPlayers = [...state.batters, ...state.bowlers];
  const uniquePlayers = uniquePlayerCount(allPlayers);
  const availablePlayers = uniquePlayerCount(allPlayers.filter((player) => player.available));
  const confirmedTeams = uniquePlayerCount(allPlayers.filter((player) => player.current_team));
  const recentlySeen = uniquePlayerCount(
    allPlayers.filter((player) => player.last_match_date?.startsWith("2026-")),
  );

  return (
    <div className="space-y-6">
      <section
        className="relative isolate overflow-hidden rounded-[2rem] bg-slate-950 px-5 py-7 text-white shadow-2xl shadow-rr-950/15 sm:px-8 sm:py-10 lg:px-11"
        style={{ backgroundColor: "#020617" }}
      >
        <div
          className="pointer-events-none absolute inset-0 opacity-70"
          style={{
            zIndex: 0,
            backgroundImage:
              "radial-gradient(circle at 78% 16%, rgba(244,63,94,.35), transparent 28%), radial-gradient(circle at 42% 100%, rgba(14,165,233,.16), transparent 34%), linear-gradient(135deg, #10131d 0%, #171827 55%, #260d1c 100%)",
          }}
        />
        <div
          className="pointer-events-none absolute top-12 hidden h-48 w-48 rounded-full border border-white/10 sm:block sm:h-72 sm:w-72"
          style={{ zIndex: 0, right: "4rem", left: "auto" }}
        />
        <div
          className="pointer-events-none absolute top-20 hidden h-36 w-36 rounded-full border border-white/10 sm:block sm:h-56 sm:w-56"
          style={{ zIndex: 0, right: "7rem", left: "auto" }}
        />

        <div
          className="grid gap-8 md:grid-cols-2 md:items-center md:gap-6"
          style={{ position: "relative", zIndex: 1 }}
        >
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-rr-300/30 bg-rr-500/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-rr-100">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,.9)]" />
              RR scouting intelligence · IPL 2027
            </div>
            <h1 className="mt-5 max-w-3xl text-4xl font-black leading-[1.03] tracking-tight sm:text-5xl md:text-4xl lg:text-5xl xl:text-6xl">
              Find the edge
              <span className="block bg-gradient-to-r from-rr-300 via-rose-200 to-amber-200 bg-clip-text text-transparent">
                before the auction.
              </span>
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-relaxed text-slate-300 sm:text-base">
              One data-led view of every active player: role-specific rankings, pressure
              performance, recent activity and an availability-aware shortlist for Rajasthan
              Royals.
            </p>
            <div className="mt-6 flex flex-wrap gap-2.5">
              <Link
                to="/auction-board"
                className="inline-flex items-center justify-center rounded-xl bg-rr-500 px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-rr-950/30 transition hover:-translate-y-0.5 hover:bg-rr-400"
              >
                Open auction board <span className="ml-2">↗</span>
              </Link>
              <Link
                to="/players"
                className="inline-flex items-center justify-center rounded-xl border border-white/20 bg-white/5 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/10"
              >
                Explore all players
              </Link>
            </div>
          </div>

          <div className="rounded-3xl border border-white/10 bg-white/[0.06] p-5 shadow-xl backdrop-blur-md">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                  Live rankings snapshot
                </p>
                <p className="mt-1 text-sm font-bold text-white">Active scouting pool</p>
              </div>
              <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 text-[9px] font-bold uppercase tracking-wider text-emerald-300">
                {state.loading ? "Loading data" : state.error ? "Data unavailable" : "Data loaded"}
              </span>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <div className="rounded-2xl bg-black/20 p-3.5">
                <p className="num text-2xl font-black">{state.loaded ? fmtInt(uniquePlayers) : "—"}</p>
                <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                  Ranked players
                </p>
              </div>
              <div className="rounded-2xl bg-black/20 p-3.5">
                <p className="num text-2xl font-black">{state.loaded ? fmtInt(availablePlayers) : "—"}</p>
                <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                  Ranked available
                </p>
              </div>
              <div className="rounded-2xl bg-black/20 p-3.5">
                <p className="num text-2xl font-black">{state.loaded ? fmtInt(recentlySeen) : "—"}</p>
                <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                  Seen in 2026
                </p>
              </div>
              <div className="rounded-2xl bg-black/20 p-3.5">
                <p className="num text-2xl font-black">{IPL_TEAMS.length}</p>
                <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                  IPL squads
                </p>
              </div>
            </div>
            <div className="mt-4 flex items-center justify-between border-t border-white/10 pt-3 text-[10px] text-slate-400">
              <span>Current teams confirmed</span>
              <span className="num font-bold text-white">
                {state.loaded ? fmtInt(confirmedTeams) : "—"}
              </span>
            </div>
          </div>
        </div>
      </section>

      {state.error ? <ErrorNote message={state.error} onRetry={load} /> : null}
      {!state.loading && !state.error ? (
        <ReadyBanner ready={state.ready} message={state.message} />
      ) : null}

      <section aria-label="All player directory totals">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-rr-600 dark:text-rr-300">
              All Players directory
            </p>
            <h2 className="mt-1 text-xl font-black tracking-tight text-slate-950 dark:text-white">
              Player pool at a glance
            </h2>
          </div>
          <Link
            to="/players"
            className="text-xs font-bold text-rr-700 hover:underline dark:text-rr-300"
          >
            Open full directory →
          </Link>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
          {[
            ["Players", "all"],
            ["IPL 2026 list", "ipl2026"],
            ["Not played since 2 years", "notPlayedSinceTwoYears"],
            ["Pakistan players", "pakistan"],
            ["Available", "available"],
            ["Other players", "other"],
          ].map(([label, key]) => (
            <div
              key={key}
              className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-rr-200 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-rr-500/40"
            >
              <p className="min-h-8 text-[10px] font-bold uppercase leading-relaxed tracking-[0.1em] text-slate-500 dark:text-slate-400">
                {label}
              </p>
              <p className="num mt-1 text-2xl font-black tracking-tight text-slate-950 dark:text-white sm:text-3xl">
                {state.loaded && state.directoryTotals
                  ? fmtInt(state.directoryTotals[key])
                  : "—"}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section aria-label="Player rankings" className="grid gap-4 lg:grid-cols-2">
        {state.loading ? (
          <>
            <LoadingBlock rows={5} />
            <LoadingBlock rows={5} />
          </>
        ) : state.error ? null : (
          <>
            <Spotlight role="batter" players={state.batters.filter((row) => row.available)} />
            <Spotlight role="bowler" players={state.bowlers.filter((row) => row.available)} />
          </>
        )}
      </section>

      <section aria-label="Explore the scouting dashboard">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-rr-600 dark:text-rr-300">
              From data to decision
            </p>
            <h2 className="mt-1 text-xl font-black tracking-tight text-slate-950 dark:text-white sm:text-2xl">
              Your scouting toolkit
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Built from IPL 2022–2026 and T20I analysis data
          </p>
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {QUICK_LINKS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="group rounded-2xl border border-slate-200 bg-white p-4 transition hover:-translate-y-1 hover:border-rr-300 hover:shadow-lg dark:border-slate-800 dark:bg-slate-900 dark:hover:border-rr-500/50"
            >
              <div className="flex items-center justify-between">
                <span className="num text-xs font-black text-rr-600 dark:text-rr-300">
                  {item.icon}
                </span>
                <span className="text-slate-400 transition group-hover:translate-x-1 group-hover:text-rr-600 dark:group-hover:text-rr-300">
                  ↗
                </span>
              </div>
              <p className="mt-4 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-400">
                {item.eyebrow}
              </p>
              <h3 className="mt-1 text-base font-black text-slate-900 dark:text-white">
                {item.title}
              </h3>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
                {item.detail}
              </p>
            </Link>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-[11px] leading-relaxed text-slate-500 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400 sm:flex-row sm:items-center sm:justify-between">
        <p>
          Players with no match since before 17 Nov 2024 are excluded from the active rankings.
          Ratings are decision support, not predictions or confirmed 2027 availability.
        </p>
        <Link
          to="/methods"
          className="shrink-0 font-bold text-rr-700 hover:underline dark:text-rr-300"
        >
          How the data works →
        </Link>
      </section>
    </div>
  );
}
