import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth, LockIcon } from "../auth";
import CurrentTeamEditor from "../components/CurrentTeamEditor";
import { ErrorNote, LoadingBlock } from "../components/States";
import { teamSourceLabel } from "../teams";
import { filterInactivePlayers } from "../availablePlayers";
import { cx, fmtInt, fmtNum } from "../utils";

const SHORTLIST_SIZE = 10;

function filterAndRankPlayers(players) {
  const activePlayers = filterInactivePlayers(players);
  const ranked = activePlayers
    .filter((row) => row.clean_rank !== null && row.clean_rank !== undefined)
    .sort((a, b) => a.clean_rank - b.clean_rank);
  const cleanRanks = new Map(
    ranked.map((row, index) => [String(row.player_id), index + 1]),
  );
  return activePlayers.map((row) => ({
    ...row,
    clean_rank: cleanRanks.get(String(row.player_id)) ?? null,
  }));
}

function TeamCell({ row, dataTeams, typedTeams, onChanged }) {
  return (
    <div className="flex items-center gap-2">
      <CurrentTeamEditor
        name={row.name}
        currentTeam={row.current_team}
        currentTeamType={row.current_team_type}
        dataTeam={row.data_team}
        dataTeams={dataTeams}
        typedTeams={typedTeams}
        status={row.status}
        onChanged={onChanged}
        subtle
      />
    </div>
  );
}

function BoardTable({ title, rows, dataTeams, typedTeams, onChanged, emptyHint }) {
  return (
    <section className="card overflow-hidden">
      <header className="flex items-baseline justify-between gap-2 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">{title}</h2>
        <span className="text-[10px] uppercase tracking-wider text-slate-400">
          {rows.length} of {SHORTLIST_SIZE}
        </span>
      </header>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-xs text-slate-500 dark:text-slate-400">{emptyHint}</p>
      ) : (
        <ul className="divide-y divide-slate-100 dark:divide-slate-800/70">
          {rows.map((row) => (
            <li key={`${row.player_type}-${row.player_id}`} className="flex items-center gap-3 px-4 py-2.5">
              <span className="num w-6 shrink-0 text-center text-xs font-black text-slate-400">
                {fmtInt(row.clean_rank)}
              </span>
              <div className="min-w-0 flex-1">
                <Link
                  to={`/player/${row.player_type}/${row.player_id}`}
                  className="block truncate text-sm font-semibold text-slate-900 hover:text-rr-700 dark:text-white dark:hover:text-rr-300"
                >
                  {row.name}
                </Link>
                <p className="num truncate text-[10px] text-slate-500 dark:text-slate-400">
                  {fmtInt(row.matches)} matches · {row.experience} · engine {fmtNum(row.score)}
                </p>
              </div>
              <div className="hidden shrink-0 text-right sm:block">
                <p className="num text-sm font-black text-rr-700 dark:text-rr-300">
                  {fmtNum(row.rating100, 1)}
                </p>
                <p className="text-[9px] uppercase tracking-wide text-slate-400">
                  rating /100
                </p>
              </div>
              <div className="shrink-0">
                <TeamCell
                  row={row}
                  dataTeams={dataTeams}
                  typedTeams={typedTeams}
                  onChanged={onChanged}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function AuctionBoardPage() {
  const { authenticated, openLogin } = useAuth();
  const [state, setState] = useState({
    loading: true,
    error: null,
    batters: [],
    bowlers: [],
    dataTeams: [],
    typedTeams: [],
  });
  const [excludedTeam, setExcludedTeam] = useState("");
  const [minMatches, setMinMatches] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);

  const load = useCallback(({ silent = false } = {}) => {
    if (!silent) setState((current) => ({ ...current, loading: true, error: null }));
    return Promise.all([
      api.players({ role: "batter", availableOnly: true }),
      api.players({ role: "bowler", availableOnly: true }),
      api.status(),
    ])
      .then(([batters, bowlers, status]) => {
        setState({
          loading: false,
          error: null,
          batters: filterAndRankPlayers(batters.players ?? []),
          bowlers: filterAndRankPlayers(bowlers.players ?? []),
          dataTeams: status.data_teams ?? [],
          typedTeams: status.typed_teams ?? [],
        });
      })
      .catch((error) => {
        setState((current) => ({ ...current, loading: false, error: error.message }));
      });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const allRows = useMemo(
    () => [...state.batters, ...state.bowlers],
    [state.batters, state.bowlers],
  );

  const teamOptions = useMemo(() => {
    const teams = new Set();
    for (const row of allRows) {
      if (row.effective_team) teams.add(row.effective_team);
    }
    return [...teams].sort((a, b) => a.localeCompare(b));
  }, [allRows]);

  const excludedKey = excludedTeam.trim().toLocaleLowerCase();
  const matchesMinimum = minMatches === "" ? 0 : Number(minMatches) || 0;
  const meetsMatches = useCallback(
    (row) => (Number(row.matches) || 0) >= matchesMinimum,
    [matchesMinimum],
  );
  const matchesExcluded = useCallback(
    (row) =>
      Boolean(excludedKey) &&
      String(row.effective_team ?? "").toLocaleLowerCase() === excludedKey,
    [excludedKey],
  );

  const removed = useMemo(() => {
    if (!excludedKey) return [];
    return allRows
      .filter(
        (row) =>
          matchesExcluded(row) &&
          meetsMatches(row) &&
          (row.clean_rank ?? 99) <= 20,
      )
      .sort((a, b) => (a.clean_rank ?? 99) - (b.clean_rank ?? 99));
  }, [allRows, excludedKey, matchesExcluded, meetsMatches]);

  const board = useMemo(() => {
    const pick = (rows) =>
      rows
        .filter((row) => !matchesExcluded(row) && meetsMatches(row))
        .sort((a, b) => (a.clean_rank ?? 99) - (b.clean_rank ?? 99))
        .slice(0, SHORTLIST_SIZE);
    return {
      batter: pick(state.batters),
      bowler: pick(state.bowlers),
    };
  }, [state.batters, state.bowlers, matchesExcluded, meetsMatches]);

  const boardRows = useMemo(() => [...board.batter, ...board.bowler], [board]);
  const boardSet = boardRows.filter((row) => row.current_team).length;
  const poolShortlistSet = allRows.filter(
    (row) => (row.clean_rank ?? 99) <= SHORTLIST_SIZE && row.current_team,
  ).length;
  const poolShortlist = allRows.filter((row) => (row.clean_rank ?? 99) <= SHORTLIST_SIZE).length;

  return (
    <div className="space-y-5">
      <div className="hidden print:block">
        <h1 className="text-xl font-black">RR IPL 2027 auction board</h1>
        <p className="text-xs text-slate-500">
          Availability-aware shortlists rated out of 100. Team shown is the current team where
          set, otherwise the latest team in the supplied data with a “(data)” tag.
        </p>
      </div>

      <header className="no-print flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label">Shortlist print view</p>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-900 sm:text-3xl dark:text-white">
            Auction board
          </h1>
          <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">
            The ten best available batters and bowlers after your availability, inactivity,
            minimum-match and team filters. Players whose last match was before 17 Nov 2024
            are excluded. Order comes from the 0–100 auction rating, which counts overall
            numbers, pressure, consistency, boundaries/economy, phases, form, experience and
            sample size. Current team drives the filter where you have set it; otherwise the
            latest team from the data is used and marked as unverified.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="btn-ghost"
            onClick={() => setDrawerOpen(true)}
            disabled={removed.length === 0}
          >
            Removed players ({removed.length})
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => (authenticated ? window.print() : openLogin())}
            title={authenticated ? "Print or save as PDF" : "Sign in to print or download"}
          >
            {authenticated ? null : <LockIcon className="h-4 w-4" />}
            Print / PDF
          </button>
        </div>
      </header>

      {state.error ? <ErrorNote message={state.error} onRetry={load} /> : null}

      <section className="card no-print p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[16rem]">
            <label htmlFor="board-exclude-team" className="label">
              Team filter — exclude players whose current team is
            </label>
            <select
              id="board-exclude-team"
              className="select mt-1"
              value={excludedTeam}
              onChange={(event) => setExcludedTeam(event.target.value)}
            >
              <option value="">No team excluded</option>
              {teamOptions.map((team) => (
                <option key={team} value={team}>
                  {team}
                </option>
              ))}
            </select>
          </div>
          <div className="min-w-[10rem]">
            <label htmlFor="board-min-matches" className="label">
              Minimum matches
            </label>
            <select
              id="board-min-matches"
              className="select mt-1"
              value={minMatches}
              onChange={(event) => setMinMatches(event.target.value)}
            >
              <option value="">Any</option>
              <option value="10">10+</option>
              <option value="25">25+</option>
              <option value="50">50+</option>
              <option value="75">75+</option>
            </select>
          </div>
          <div className="flex-1 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
            <p>
              Board current teams set:{" "}
              <strong className="num text-slate-700 dark:text-slate-200">{boardSet}</strong> of{" "}
              <span className="num">{boardRows.length}</span> · engine shortlist:{" "}
              <strong className="num text-slate-700 dark:text-slate-200">
                {poolShortlistSet}
              </strong>{" "}
              of <span className="num">{poolShortlist}</span> players have a current team set.
            </p>
            {excludedTeam ? (
              <p className="mt-1">
                {removed.length} players excluded by team. Open the drawer to see whether each
                exclusion came from your current team or the latest team in the data.
              </p>
            ) : null}
          </div>
          {excludedTeam ? (
            <button
              type="button"
              className="btn-ghost"
              onClick={() => setExcludedTeam("")}
            >
              Clear team filter
            </button>
          ) : null}
        </div>
      </section>

      {state.loading ? (
        <LoadingBlock rows={10} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <BoardTable
            title="Batters"
            rows={board.batter}
            dataTeams={state.dataTeams}
            typedTeams={state.typedTeams}
            onChanged={() => load({ silent: true })}
            emptyHint="No available batters match. Clear the team filter or adjust availability."
          />
          <BoardTable
            title="Bowlers"
            rows={board.bowler}
            dataTeams={state.dataTeams}
            typedTeams={state.typedTeams}
            onChanged={() => load({ silent: true })}
            emptyHint="No available bowlers match. Clear the team filter or adjust availability."
          />
        </div>
      )}
      <p className="text-[10px] leading-relaxed text-slate-400 no-print dark:text-slate-500">
        Shortlists use the clean rank (unavailable players and players whose last match was
        before 17 Nov 2024 removed, minimum-match filter applied) over the 0–100 auction rating.
        A manual current team overrides the latest team from the supplied data for the team
        filter. All team values are scouting judgements and unverified until official IPL announcements.
      </p>

      {drawerOpen ? (
        <div className="no-print fixed inset-0 z-50 flex justify-end">
          <button
            type="button"
            aria-label="Close removed players"
            className="absolute inset-0 bg-slate-950/40 backdrop-blur-[1px]"
            onClick={() => setDrawerOpen(false)}
          />
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="Removed players"
            className="relative flex h-full w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900"
          >
            <header className="flex items-start justify-between gap-3 border-b border-slate-200 p-4 dark:border-slate-800">
              <div>
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                  Removed players
                </h2>
                <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
                  {excludedTeam
                    ? `Excluded because their team is ${excludedTeam}.`
                    : "Set a team filter to see removals."}
                </p>
              </div>
              <button
                type="button"
                className="btn-ghost h-8 px-2.5 py-1 text-xs"
                onClick={() => setDrawerOpen(false)}
              >
                Close
              </button>
            </header>
            <div className="flex-1 overflow-y-auto p-4">
              {removed.length === 0 ? (
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  No shortlist or reserve players were removed with this filter.
                </p>
              ) : (
                <ul className="space-y-2">
                  {removed.map((row) => (
                    <li
                      key={`${row.player_type}-${row.player_id}`}
                      className="rounded-xl border border-slate-200 p-3 text-xs dark:border-slate-800"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate font-semibold text-slate-900 dark:text-white">
                            {row.name}
                          </p>
                          <p className="text-[10px] capitalize text-slate-500 dark:text-slate-400">
                            {row.player_type} · clean rank {fmtInt(row.clean_rank)} · team{" "}
                            {row.effective_team ?? "—"}
                          </p>
                        </div>
                        <span
                          className={cx(
                            "shrink-0 rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide ring-1 ring-inset",
                            row.team_source === "manual"
                              ? "bg-rr-50 text-rr-700 ring-rr-500/30 dark:bg-rr-500/10 dark:text-rr-300"
                              : "bg-slate-100 text-slate-600 ring-slate-400/30 dark:bg-slate-800 dark:text-slate-300",
                          )}
                        >
                          {row.team_source === "manual" ? "manual" : "data"}
                        </span>
                      </div>
                      <p className="mt-1.5 text-[10px] leading-relaxed text-slate-500 dark:text-slate-400">
                        Exclusion decided by {teamSourceLabel(row.team_source)}
                        {row.team_source === "data"
                          ? " — confirm the current team to override it."
                          : "."}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
