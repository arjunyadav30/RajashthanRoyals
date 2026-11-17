import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth, LockIcon } from "../auth";
import { LockBanner } from "../components/AuthGate";
import { FlagBadge, FlagBadges, PlayerAvatar, RankChip, StatusPill } from "../components/Badges";
import CurrentTeamEditor from "../components/CurrentTeamEditor";
import DataTable from "../components/DataTable";
import Modal from "../components/Modal";
import { EmptyState, ErrorNote, LoadingBlock, ReadyBanner } from "../components/States";
import { IPL_TEAMS, NO_TEAM, RELEASED_TEAM, teamTypeFor } from "../teams";
import { filterInactivePlayers } from "../availablePlayers";
import {
  compareValues,
  cx,
  downloadCsv,
  fmtInt,
  fmtNum,
  fmtPct,
  isNumber,
  normaliseName,
  PUBLIC_ROW_LIMIT,
} from "../utils";

const PHASES = ["Powerplay", "Middle", "Death"];
const KEEP_TEAM = "__keep__";
const CLEAR_TEAM = "__clear__";
const OTHER_TEAM = "__other__";

const PHASE_DOT = {
  Powerplay: "bg-amber-500",
  Middle: "bg-sky-500",
  Death: "bg-rr-500",
};

function rankTone(cleanRank) {
  if (!isNumber(cleanRank)) return "default";
  if (cleanRank <= 10) return "shortlist";
  if (cleanRank <= 20) return "reserve";
  return "default";
}

function buildCleanMap(players) {
  const map = new Map();
  const rankedPlayers = players
    .filter((player) => player.clean_rank !== null && player.clean_rank !== undefined)
    .sort((a, b) => a.clean_rank - b.clean_rank);
  for (const [index, player] of rankedPlayers.entries()) {
    map.set(String(player.player_id), index + 1);
  }
  return map;
}

function buildRoleRankMap(players) {
  const map = new Map();
  for (const player of players) {
    map.set(
      String(player.player_id),
      player.all_rank ?? player.rank ?? null,
    );
  }
  return map;
}

function defaultDirection(key) {
  return ["clean_rank", "rank", "all_rank", "batter_rank", "bowler_rank", "qualified_rank", "name", "current_team", "dominant_phase", "status"].includes(key)
    ? "asc"
    : "desc";
}

function csvColumns(role) {
  const base = [
    { header: "clean_rank", value: (r) => r.clean_rank },
    { header: "rating_100", value: (r) => r.rating100 },
    { header: "data_confidence_100", value: (r) => r.data_confidence_100 },
    { header: "role_fit_100", value: (r) => r.role_fit },
    { header: "risk", value: (r) => r.risk },
    { header: "all_rank", value: (r) => r.all_rank },
    { header: "batter_rank", value: (r) => r.batter_rank },
    { header: "bowler_rank", value: (r) => r.bowler_rank },
    { header: "qualified_rank", value: (r) => r.qualified_rank },
    { header: "qualification_status", value: (r) => r.qualification_status },
    { header: "raw_rank", value: (r) => r.rank },
    { header: "name", value: (r) => r.name },
    { header: "player_id", value: (r) => r.player_id },
    { header: "role", value: () => role },
    { header: "best_use", value: (r) => r.role },
    { header: "team", value: (r) => r.team_label },
    { header: "current_team", value: (r) => r.current_team },
    { header: "current_team_type", value: (r) => r.current_team_type },
    { header: "team_source", value: (r) => r.team_source },
    { header: "effective_team", value: (r) => r.effective_team },
    { header: "matches", value: (r) => r.matches },
    { header: "experience", value: (r) => r.experience },
    { header: "experience_marks_7", value: (r) => r.experience_marks },
    { header: "sample_marks_6", value: (r) => r.sample_marks },
    { header: "innings", value: (r) => r.career_innings },
    { header: "runs", value: (r) => r.career_runs },
    { header: "wickets", value: (r) => r.career_wickets },
    { header: "average", value: (r) => r.career_average },
    { header: "strike_rate", value: (r) => r.career_sr },
    { header: "economy", value: (r) => r.career_econ },
    { header: "dot_pct", value: (r) => r.career_dot_pct },
    { header: "fours", value: (r) => r.career_fours },
    { header: "sixes", value: (r) => r.career_sixes },
    { header: "balls_per_boundary", value: (r) => r.balls_per_boundary },
    { header: "score", value: (r) => r.score },
    { header: "score_lo", value: (r) => r.score_lo },
    { header: "score_hi", value: (r) => r.score_hi },
    { header: "rank_lo", value: (r) => r.rank_lo },
    { header: "rank_hi", value: (r) => r.rank_hi },
    { header: "pressure_balls", value: (r) => r.pressure_balls },
    { header: "balls_in_source_scope", value: (r) => r.IPL_balls },
    { header: "T20I_balls", value: (r) => r.T20I_balls },
    { header: "impact100", value: (r) => r.impact100 },
    { header: "normal_impact", value: (r) => r.normal_impact },
    { header: "delta", value: (r) => r.delta },
    { header: "consistency", value: (r) => r.consistency },
    { header: "dots_pct", value: (r) => r.dots_pct },
    { header: "boundaries_pct", value: (r) => r.boundaries_pct },
    { header: "wickets_pct", value: (r) => r.wickets_pct },
    { header: "economy", value: (r) => r.economy },
    { header: "economy_above_expected", value: (r) => r.economy_above_expected },
    { header: "dominant_phase", value: (r) => r.dominant_phase },
    { header: "pressure_matches", value: (r) => r.pressure_matches },
    { header: "eb_weight", value: (r) => r.eb_weight },
    { header: "shrunk_performance", value: (r) => r.shrunk_performance },
    { header: "shrunk_wpa", value: (r) => r.shrunk_wpa },
    { header: "shrunk_delta", value: (r) => r.shrunk_delta },
    { header: "form2026_balls", value: (r) => r.form2026_balls },
    { header: "form2026_impact100", value: (r) => r.form2026_impact100 },
    { header: "IPL_PLAYED", value: (r) => r.IPL_PLAYED },
    { header: "PLAYED_2026_IPL", value: (r) => r.PLAYED_2026_IPL },
    { header: "RECENT_FORM_FLAG", value: (r) => r.RECENT_FORM_FLAG },
    { header: "IPL_PRESSURE_FLAG", value: (r) => r.IPL_PRESSURE_FLAG },
    { header: "SAMPLE_FLAG", value: (r) => r.SAMPLE_FLAG },
    { header: "status", value: (r) => r.status },
    { header: "note", value: (r) => r.note },
    { header: "rr_fit", value: (r) => r.rr_fit },
  ];
  return base;
}

function Columns(role, showStatus, teamContext) {
  const columns = [
    {
      key: "clean_rank",
      label: "Clean",
      sortable: true,
      align: "center",
      cell: (row) => (
        <span title="Clean rank after the availability filter">
          <RankChip rank={row.clean_rank} tone={rankTone(row.clean_rank)} />
        </span>
      ),
      sortValue: (row) => row.clean_rank,
    },
    {
      key: "rating100",
      label: "Score /100",
      sortable: true,
      align: "center",
      cell: (row) => (
        <div className="leading-tight">
          <span className="num text-base font-black text-rr-700 dark:text-rr-300">
            {fmtNum(row.rating100, 1)}
          </span>
          <p className="num text-[10px] text-slate-400 dark:text-slate-500">
            {isNumber(row.data_confidence_100)
              ? `${fmtNum(row.data_confidence_100, 1)}% confidence`
              : "source score"}
          </p>
        </div>
      ),
      sortValue: (row) => row.rating100,
    },
    {
      key: "all_rank",
      label: "All rank",
      sortable: true,
      align: "center",
      cell: (row) => (
        <div className="leading-tight">
          <span className="num text-sm font-semibold text-slate-800 dark:text-slate-200">
            {fmtInt(row.all_rank ?? row.rank)}
          </span>
          <p className="num text-[10px] text-slate-400 dark:text-slate-500">
            {row.rank_interval ? `90%: ${row.rank_interval}` : row.source_qualification_status || "all players"}
          </p>
        </div>
      ),
      sortValue: (row) => row.all_rank ?? row.rank,
    },
    {
      key: "batter_rank",
      label: "Batter rank",
      sortable: true,
      align: "center",
      cell: (row) => <span className="num">{fmtInt(row.batter_rank)}</span>,
      sortValue: (row) => row.batter_rank ?? 10 ** 6,
      headerClassName: "hidden md:table-cell",
      cellClassName: "hidden md:table-cell",
    },
    {
      key: "bowler_rank",
      label: "Bowler rank",
      sortable: true,
      align: "center",
      cell: (row) => <span className="num">{fmtInt(row.bowler_rank)}</span>,
      sortValue: (row) => row.bowler_rank ?? 10 ** 6,
      headerClassName: "hidden md:table-cell",
      cellClassName: "hidden md:table-cell",
    },
    {
      key: "qualified_rank",
      label: "Qual rank",
      sortable: true,
      align: "center",
      cell: (row) =>
        row.qualification_status === "BELOW_MIN" ? (
          <span title="Not enough pressure balls for a qualified rank">
            <FlagBadge label="BELOW_MIN" tone="amber" title="Does not meet the analysis package's role-specific qualification criteria." />
          </span>
        ) : (
          <RankChip
            rank={row.qualified_rank}
            tone={row.qualified_rank <= 10 ? "shortlist" : row.qualified_rank <= 20 ? "reserve" : "default"}
          />
        ),
      sortValue: (row) => row.qualified_rank ?? 10 ** 6,
      headerClassName: "hidden sm:table-cell",
      cellClassName: "hidden sm:table-cell",
    },
    {
      key: "name",
      label: "Player",
      sortable: true,
      cell: (row) => (
        <Link
          to={`/player/${role}/${row.player_id}`}
          className="group flex items-center gap-2.5"
        >
          <PlayerAvatar name={row.name} role={role} size="sm" />
          <span className="min-w-0">
            <span className="block truncate font-semibold text-slate-900 group-hover:text-rr-700 dark:text-white dark:group-hover:text-rr-300">
              {row.name}
            </span>
            <span className="block truncate text-[10px] text-slate-500 dark:text-slate-400">
              {row.role || role} · {row.dominant_phase || "—"}
            </span>
            {row.qualification_status === "BELOW_MIN" ? (
              <span className="mt-0.5 block text-[9px] font-semibold text-amber-700 dark:text-amber-400">
                low sample · source criteria
              </span>
            ) : null}
          </span>
        </Link>
      ),
      sortValue: (row) => row.name,
    },
    {
      key: "matches",
      label: "Matches",
      sortable: true,
      align: "right",
      cell: (row) => (
        <div className="leading-tight">
          <span className="num text-sm font-semibold text-slate-800 dark:text-slate-200">
            {fmtInt(row.matches)}
          </span>
          <p className="text-[10px] text-slate-400 dark:text-slate-500">
            {row.experience}
            {row.risk ? ` · ${row.risk} risk` : ""}
          </p>
        </div>
      ),
      sortValue: (row) => row.matches,
    },
    {
      key: "current_team",
      label: "Current team",
      sortable: true,
      cell: (row) => (
        <div className="flex flex-col items-start gap-1">
          <CurrentTeamEditor
            name={row.name}
            currentTeam={row.current_team}
            currentTeamType={row.current_team_type}
            dataTeam={row.latest_IPL_team || row.latest_team}
            dataTeams={teamContext.dataTeams}
            typedTeams={teamContext.typedTeams}
            status={row.status}
            onChanged={teamContext.onChanged}
          />
          {row.current_team && row.team_label ? (
            <span className="text-[9px] text-slate-400 dark:text-slate-500">
              data: {row.team_label}
            </span>
          ) : null}
        </div>
      ),
      sortValue: (row) => row.effective_team ?? row.team_label,
      headerClassName: "hidden sm:table-cell",
      cellClassName: "hidden sm:table-cell",
    },
    {
      key: "pressure_balls",
      label: "P balls",
      sortable: true,
      align: "right",
      cell: (row) => <span className="num text-xs">{fmtInt(row.pressure_balls)}</span>,
      sortValue: (row) => row.pressure_balls,
      headerClassName: "hidden sm:table-cell",
      cellClassName: "hidden sm:table-cell",
    },
    {
      key: "IPL_balls",
      label: "Balls",
      sortable: true,
      align: "right",
      cell: (row) => <span className="num text-xs">{fmtInt(row.IPL_balls)}</span>,
      sortValue: (row) => row.IPL_balls,
      headerClassName: "hidden lg:table-cell",
      cellClassName: "hidden lg:table-cell",
    },
    {
      key: "impact100",
      label: role === "batter" ? "Pressure SR" : "Pressure wkts/100",
      sortable: true,
      align: "right",
      cell: (row) => (
        <span
          className={cx(
            "num text-xs font-semibold",
            isNumber(row.impact100) && row.impact100 >= (row.normal_impact ?? 0)
              ? "text-emerald-700 dark:text-emerald-400"
              : "text-slate-700 dark:text-slate-300",
          )}
          title={role === "batter" ? "Batting strike rate in pressure situations" : "Bowling wickets per 100 pressure balls"}
        >
          {fmtNum(row.impact100)}
        </span>
      ),
      sortValue: (row) => row.impact100,
      headerClassName: "hidden xl:table-cell",
      cellClassName: "hidden xl:table-cell",
    },
    {
      key: "normal_impact",
      label: role === "batter" ? "Normal SR" : "Normal economy",
      sortable: true,
      align: "right",
      cell: (row) => <span className="num text-xs">{fmtNum(row.normal_impact)}</span>,
      sortValue: (row) => row.normal_impact,
      headerClassName: "hidden xl:table-cell",
      cellClassName: "hidden xl:table-cell",
    },
    {
      key: "delta",
      label: "Delta",
      sortable: true,
      align: "right",
      cell: (row) => (
        <span
          className={cx(
            "num text-xs font-semibold",
            isNumber(row.delta) && row.delta > 0
              ? "text-emerald-700 dark:text-emerald-400"
              : isNumber(row.delta) && row.delta < 0
                ? "text-red-600 dark:text-red-400"
                : "text-slate-500 dark:text-slate-400",
          )}
        >
          {fmtNum(row.delta)}
        </span>
      ),
      sortValue: (row) => row.delta,
      headerClassName: "hidden 2xl:table-cell",
      cellClassName: "hidden 2xl:table-cell",
    },
    {
      key: "dots_pct",
      label: "Dots %",
      sortable: true,
      align: "right",
      cell: (row) => <span className="num text-xs">{fmtPct(row.dots_pct)}</span>,
      sortValue: (row) => row.dots_pct,
      headerClassName: "hidden lg:table-cell",
      cellClassName: "hidden lg:table-cell",
    },
    {
      key: "boundaries_pct",
      label: "Boundary %",
      sortable: true,
      align: "right",
      cell: (row) => <span className="num text-xs">{fmtPct(row.boundaries_pct)}</span>,
      sortValue: (row) => row.boundaries_pct,
      headerClassName: "hidden lg:table-cell",
      cellClassName: "hidden lg:table-cell",
    },
    {
      key: "consistency",
      label: "Consistency",
      sortable: true,
      align: "right",
      cell: (row) => (
        <span className="num text-xs">
          {isNumber(row.consistency) ? `${fmtNum(row.consistency * 100, 0)}/100` : "—"}
        </span>
      ),
      sortValue: (row) => row.consistency,
      headerClassName: "hidden 2xl:table-cell",
      cellClassName: "hidden 2xl:table-cell",
    },
  ];

  if (role === "batter") {
    columns.push(
      {
        key: "career_sr",
        label: "SR",
        sortable: true,
        align: "right",
        cell: (row) => <span className="num text-xs">{fmtNum(row.career_sr)}</span>,
        sortValue: (row) => row.career_sr,
        title: "Career strike rate",
        headerClassName: "hidden xl:table-cell",
        cellClassName: "hidden xl:table-cell",
      },
      {
        key: "career_average",
        label: "Avg",
        sortable: true,
        align: "right",
        cell: (row) => <span className="num text-xs">{fmtNum(row.career_average)}</span>,
        sortValue: (row) => row.career_average,
        title: "Career batting average",
        headerClassName: "hidden xl:table-cell",
        cellClassName: "hidden xl:table-cell",
      },
      {
        key: "fours_sixes",
        label: "4s / 6s",
        sortable: false,
        align: "right",
        cell: (row) => (
          <span className="num text-xs">
            {fmtInt(row.career_fours)} / {fmtInt(row.career_sixes)}
          </span>
        ),
        headerClassName: "hidden 2xl:table-cell",
        cellClassName: "hidden 2xl:table-cell",
      },
      {
        key: "balls_per_boundary",
        label: "Balls/bdry",
        sortable: true,
        align: "right",
        cell: (row) => (
          <span className="num text-xs" title="Balls per boundary — lower is better">
            {fmtNum(row.balls_per_boundary, 1)}
          </span>
        ),
        sortValue: (row) => row.balls_per_boundary,
        headerClassName: "hidden xl:table-cell",
        cellClassName: "hidden xl:table-cell",
      },
    );
  }

  if (role === "bowler") {
    columns.push(
      {
        key: "career_wickets",
        label: "Wkts",
        sortable: true,
        align: "right",
        cell: (row) => <span className="num text-xs">{fmtInt(row.career_wickets)}</span>,
        sortValue: (row) => row.career_wickets,
        title: "Career wickets",
        headerClassName: "hidden xl:table-cell",
        cellClassName: "hidden xl:table-cell",
      },
      {
        key: "career_econ",
        label: "Economy",
        sortable: true,
        align: "right",
        cell: (row) => <span className="num text-xs">{fmtNum(row.career_econ)}</span>,
        sortValue: (row) => row.career_econ,
        title: "Career economy — lower is better",
        headerClassName: "hidden xl:table-cell",
        cellClassName: "hidden xl:table-cell",
      },
      {
        key: "career_dot_pct",
        label: "Dot %",
        sortable: true,
        align: "right",
        cell: (row) => <span className="num text-xs">{fmtPct(row.career_dot_pct)}</span>,
        sortValue: (row) => row.career_dot_pct,
        headerClassName: "hidden 2xl:table-cell",
        cellClassName: "hidden 2xl:table-cell",
      },
      {
        key: "wickets_pct",
        label: "Wkts %",
        sortable: true,
        align: "right",
        cell: (row) => <span className="num text-xs">{fmtPct(row.wickets_pct)}</span>,
        sortValue: (row) => row.wickets_pct,
        headerClassName: "hidden xl:table-cell",
        cellClassName: "hidden xl:table-cell",
      },
      {
        key: "economy_above_expected",
        label: "Econ vs exp",
        sortable: true,
        align: "right",
        cell: (row) => (
          <span
            className={cx(
              "num text-xs font-semibold",
              isNumber(row.economy_above_expected) && row.economy_above_expected < 0
                ? "text-emerald-700 dark:text-emerald-400"
                : "text-slate-700 dark:text-slate-300",
            )}
            title="Negative is better: economy below expected"
          >
            {fmtNum(row.economy_above_expected)}
          </span>
        ),
        sortValue: (row) => row.economy_above_expected,
        headerClassName: "hidden xl:table-cell",
        cellClassName: "hidden xl:table-cell",
      },
    );
  }

  if (showStatus) {
    columns.push({
      key: "status",
      label: "Availability",
      sortable: true,
      cell: (row) => (
        <div className="flex flex-col items-start gap-1">
          <StatusPill status={row.status} />
          {row.note ? (
            <span
              className="max-w-[11rem] truncate text-[10px] text-slate-400 dark:text-slate-500"
              title={row.note}
            >
              {row.note}
            </span>
          ) : null}
        </div>
      ),
      sortValue: (row) => row.status,
      headerClassName: "hidden sm:table-cell",
      cellClassName: "hidden sm:table-cell",
    });
  }

  columns.push({
    key: "flags",
    label: "Flags",
    sortable: false,
    cell: (row) => <FlagBadges row={row} />,
    headerClassName: "hidden lg:table-cell",
    cellClassName: "hidden lg:table-cell",
  });

  return columns;
}

export default function RankingsPage({ role }) {
  const plural = `${role}s`;
  const { authenticated, openLogin } = useAuth();
  const [state, setState] = useState({
    loading: true,
    error: null,
    rows: [],
    ready: true,
    message: "",
  });
  const [filters, setFilters] = useState({
    search: "",
    availableOnly: true,
    qualifiedOnly: false,
    lastMatch2026Only: false,
    phase: "",
    team: "",
    minBalls: "",
    minMatches: "",
    currentTeamUnset: false,
  });
  const [sort, setSort] = useState({ key: "all_rank", dir: "asc" });
  const [selected, setSelected] = useState(() => new Set());
  const [bulkTeam, setBulkTeam] = useState(KEEP_TEAM);
  const [bulkOther, setBulkOther] = useState("");
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const [bulkSaving, setBulkSaving] = useState(false);
  const [bulkError, setBulkError] = useState(null);
  const [toast, setToast] = useState(null);

  const load = useCallback(() => {
    setState((current) => ({ ...current, loading: true, error: null }));
    return Promise.all([
      api.players({ role, availableOnly: true }),
      api.players({ role, availableOnly: false }),
      api.players({
        role: role === "batter" ? "bowler" : "batter",
        availableOnly: false,
      }),
    ])
      .then(([pool, all, otherRole]) => {
        const activePool = filterInactivePlayers(pool.players);
        const cleanMap = buildCleanMap(activePool);
        const primaryRankMap = buildRoleRankMap(all.players);
        const otherRankMap = buildRoleRankMap(otherRole.players);
        const batterRankMap = role === "batter" ? primaryRankMap : otherRankMap;
        const bowlerRankMap = role === "bowler" ? primaryRankMap : otherRankMap;
        const rows = filterInactivePlayers(all.players).map((row) => {
          const playerId = String(row.player_id);
          return {
            ...row,
            clean_rank: cleanMap.get(playerId) ?? null,
            batter_rank: batterRankMap.get(playerId) ?? null,
            bowler_rank: bowlerRankMap.get(playerId) ?? null,
          };
        });
        setState({
          loading: false,
          error: null,
          rows,
          ready: all.ready,
          message: all.message,
        });
      })
      .catch((error) => {
        setState((current) => ({ ...current, loading: false, error: error.message }));
        throw error;
      });
  }, [role]);

  useEffect(() => {
    setState({ loading: true, error: null, rows: [], ready: true, message: "" });
    setSelected(new Set());
    setBulkTeam(KEEP_TEAM);
    setBulkOther("");
    setBulkError(null);
    setFilters({
      search: "",
      availableOnly: true,
      qualifiedOnly: false,
      lastMatch2026Only: false,
      phase: "",
      team: "",
      minBalls: "",
      minMatches: "",
      currentTeamUnset: false,
    });
    setSort({ key: "all_rank", dir: "asc" });
    load().catch(() => {});
  }, [load]);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const teamLists = useMemo(() => {
    const dataTeams = new Set();
    const typedTeams = new Set();
    for (const row of state.rows) {
      if (row.latest_team) dataTeams.add(row.latest_team);
      if (row.latest_IPL_team) dataTeams.add(row.latest_IPL_team);
      if (row.current_team_type === "other" && row.current_team) {
        typedTeams.add(row.current_team);
      }
    }
    return {
      dataTeams: [...dataTeams].sort((a, b) => a.localeCompare(b)),
      typedTeams: [...typedTeams].sort((a, b) => a.localeCompare(b)),
    };
  }, [state.rows]);

  const teams = useMemo(() => {
    const values = new Set();
    for (const row of state.rows) {
      if (row.effective_team) values.add(row.effective_team);
    }
    return [...values].sort((a, b) => a.localeCompare(b));
  }, [state.rows]);

  const filtered = useMemo(() => {
    const query = normaliseName(filters.search);
    const minBalls =
      filters.minBalls === "" ? null : Math.max(0, Number(filters.minBalls) || 0);
    const minMatches =
      filters.minMatches === "" ? null : Math.max(0, Number(filters.minMatches) || 0);
    return state.rows.filter((row) => {
      if (filters.availableOnly && !row.available) return false;
      if (filters.qualifiedOnly && row.qualification_status !== "QUALIFIED") return false;
      if (filters.lastMatch2026Only && !row.last_match_date?.startsWith("2026-")) return false;
      if (filters.phase && row.dominant_phase !== filters.phase) return false;
      if (filters.team && row.effective_team !== filters.team) return false;
      if (filters.currentTeamUnset && row.current_team) return false;
      if (minBalls !== null && (!isNumber(row.IPL_balls) || row.IPL_balls < minBalls)) {
        return false;
      }
      if (minMatches !== null && (!isNumber(row.matches) || row.matches < minMatches)) {
        return false;
      }
      if (query) {
        const haystack = `${normaliseName(row.name)} ${normaliseName(row.effective_team)} ${normaliseName(row.team_label)}`;
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
  }, [state.rows, filters]);

  const columns = useMemo(
    () =>
      Columns(role, !filters.availableOnly, {
        dataTeams: teamLists.dataTeams,
        typedTeams: teamLists.typedTeams,
        onChanged: load,
      }),
    [role, filters.availableOnly, teamLists, load],
  );

  const sortColumn = useMemo(
    () => columns.find((column) => column.key === sort.key),
    [columns, sort.key],
  );

  const sorted = useMemo(() => {
    const accessor =
      sortColumn?.sortValue ??
      (() => null);
    const copy = [...filtered];
    copy.sort((a, b) => {
      const result = compareValues(accessor(a), accessor(b));
      return sort.dir === "asc" ? result : -result;
    });
    return copy;
  }, [filtered, sortColumn, sort.dir]);

  const onSort = useCallback(
    (key) => {
      setSort((current) =>
        current.key === key
          ? { key, dir: current.dir === "asc" ? "desc" : "asc" }
          : { key, dir: defaultDirection(key) },
      );
    },
    [],
  );

  const exportCsv = useCallback(() => {
    if (!authenticated) {
      openLogin();
      return;
    }
    const filename = `rr-${plural}-${new Date().toISOString().slice(0, 10)}.csv`;
    downloadCsv(filename, csvColumns(role), sorted);
  }, [authenticated, openLogin, plural, role, sorted]);

  const tableRows = authenticated ? sorted : sorted.slice(0, PUBLIC_ROW_LIMIT);
  const rowKey = (row) => `${role}-${row.player_id}`;
  const selectedRows = state.rows.filter((row) => selected.has(rowKey(row)));
  const visibleKeys = tableRows.map(rowKey);
  const allSelected =
    visibleKeys.length > 0 && visibleKeys.every((key) => selected.has(key));
  const someSelected = visibleKeys.some((key) => selected.has(key));
  const bulkTeamValue =
    bulkTeam === OTHER_TEAM
      ? bulkOther.trim()
      : bulkTeam === CLEAR_TEAM
        ? null
        : bulkTeam === KEEP_TEAM
          ? undefined
          : bulkTeam;
  const bulkChangeCount =
    bulkTeamValue === undefined
      ? 0
      : selectedRows.filter((row) => (row.current_team ?? null) !== bulkTeamValue).length;
  const bulkTeamValid = bulkTeam !== OTHER_TEAM || Boolean(bulkOther.trim());

  const toggleSelected = (key, checked) => {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(key);
      else next.delete(key);
      return next;
    });
  };

  const toggleAllSelected = (checked) => {
    setSelected((current) => {
      const next = new Set(current);
      for (const key of visibleKeys) {
        if (checked) next.add(key);
        else next.delete(key);
      }
      return next;
    });
  };

  const applyBulkTeam = async () => {
    if (!authenticated) {
      openLogin();
      return;
    }
    if (bulkTeamValue === undefined || !bulkTeamValid) return;
    setBulkSaving(true);
    setBulkError(null);
    try {
      const result = await api.bulkStatus({
        names: selectedRows.map((row) => row.name),
        current_team: bulkTeamValue,
        current_team_type: teamTypeFor(bulkTeamValue),
      });
      await load();
      setSelected(new Set());
      setBulkTeam(KEEP_TEAM);
      setBulkOther("");
      setBulkConfirmOpen(false);
      setToast({ type: "ok", text: `${result.summary}; current team and status updated.` });
    } catch (error) {
      setBulkError(error.message);
    } finally {
      setBulkSaving(false);
    }
  };

  const hasFilters =
    filters.search !== "" ||
    filters.availableOnly ||
    filters.qualifiedOnly ||
    filters.lastMatch2026Only ||
    filters.phase !== "" ||
    filters.team !== "" ||
    filters.minBalls !== "" ||
    filters.minMatches !== "" ||
    filters.currentTeamUnset;

  const resetFilters = () => {
    setFilters({
      search: "",
      availableOnly: true,
      qualifiedOnly: false,
      lastMatch2026Only: false,
      phase: "",
      team: "",
      minBalls: "",
      minMatches: "",
      currentTeamUnset: false,
    });
    setSort({ key: "all_rank", dir: "asc" });
  };

  const availableCount = state.rows.filter((row) => row.available).length;
  const qualifiedCount = state.rows.filter(
    (row) => row.qualification_status === "QUALIFIED",
  ).length;
  const shortlistCount = sorted.filter(
    (row) => isNumber(row.clean_rank) && row.clean_rank <= 10,
  ).length;
  const shortlistRows = state.rows.filter(
    (row) => isNumber(row.clean_rank) && row.clean_rank <= 10,
  );
  const shortlistTeamCount = shortlistRows.filter((row) => row.current_team).length;
  const unsetCount = state.rows.filter((row) => !row.current_team).length;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label">RR 2027 analysis rankings</p>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-900 sm:text-3xl dark:text-white">
            {role === "batter" ? "Batters" : "Bowlers"}
          </h1>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">
            Ranks and scores come from the supplied player-analysis package, covering IPL
            2022–2026 and the T20I competitions in that data pack. Batter and bowler lists use
            their separate all-player ranks; low-sample players remain included. Players whose
            last match was before 17 Nov 2024 are excluded.
          </p>
        </div>
        <button type="button" className="btn-ghost" onClick={exportCsv} disabled={sorted.length === 0}>
          {authenticated ? null : <LockIcon className="h-4 w-4" />}
          Export CSV
        </button>
      </header>

      <ReadyBanner ready={state.ready} message={state.message} />
      {state.error ? <ErrorNote message={state.error} onRetry={load} /> : null}
      {toast ? (
        <p
          role="status"
          className={cx(
            "rounded-xl border px-3 py-2 text-xs",
            toast.type === "error"
              ? "border-red-200 bg-red-50 text-red-800 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-200"
              : "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-200",
          )}
        >
          {toast.text}
        </p>
      ) : null}

      <section className="card p-4" aria-label="Filters">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-12">
          <div className="lg:col-span-2">
            <label htmlFor="rank-search" className="label">
              Search player or team
            </label>
            <div className="relative mt-1">
              <input
                id="rank-search"
                type="search"
                value={filters.search}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, search: event.target.value }))
                }
                placeholder="e.g. Buttler, Rajasthan"
                className="input pr-8"
              />
              {filters.search ? (
                <button
                  type="button"
                  onClick={() => setFilters((current) => ({ ...current, search: "" }))}
                  className="absolute inset-y-0 right-2 my-auto h-5 w-5 rounded text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                  aria-label="Clear search"
                >
                  ×
                </button>
              ) : null}
            </div>
          </div>

          <div className="lg:col-span-2">
            <label htmlFor="rank-team" className="label">
              Current team / country
            </label>
            <select
              id="rank-team"
              value={filters.team}
              onChange={(event) =>
                setFilters((current) => ({ ...current, team: event.target.value }))
              }
              className="select mt-1"
            >
              <option value="">All teams</option>
              {teams.map((team) => (
                <option key={team} value={team}>
                  {team}
                </option>
              ))}
            </select>
          </div>

          <div className="lg:col-span-2">
            <label htmlFor="rank-phase" className="label">
              Dominant phase
            </label>
            <select
              id="rank-phase"
              value={filters.phase}
              onChange={(event) =>
                setFilters((current) => ({ ...current, phase: event.target.value }))
              }
              className="select mt-1"
            >
              <option value="">All phases</option>
              {PHASES.map((phase) => (
                <option key={phase} value={phase}>
                  {phase}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2 lg:col-span-3">
            <div>
              <label htmlFor="rank-balls" className="label">
                Min balls
              </label>
              <input
                id="rank-balls"
                type="number"
                min="0"
                step="25"
                inputMode="numeric"
                value={filters.minBalls}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, minBalls: event.target.value }))
                }
                placeholder="0"
                className="input mt-1"
              />
            </div>
            <div>
              <label htmlFor="rank-matches" className="label">
                Min matches
              </label>
              <input
                id="rank-matches"
                type="number"
                min="0"
                step="5"
                inputMode="numeric"
                value={filters.minMatches}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, minMatches: event.target.value }))
                }
                placeholder="0"
                className="input mt-1"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-end gap-2 lg:col-span-3">
            <label className="flex h-[38px] cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-3 text-sm dark:border-slate-700">
              <input
                type="checkbox"
                checked={filters.qualifiedOnly}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, qualifiedOnly: event.target.checked }))
                }
                className="h-4 w-4 rounded border-slate-300 text-rr-600 focus:ring-rr-500 dark:border-slate-600 dark:bg-slate-800"
              />
              <span className="whitespace-nowrap text-xs font-medium text-slate-700 dark:text-slate-200">
                Qualified only (source criteria)
              </span>
            </label>
            <label className="flex h-[38px] cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-3 text-sm dark:border-slate-700">
              <input
                type="checkbox"
                checked={filters.lastMatch2026Only}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    lastMatch2026Only: event.target.checked,
                  }))
                }
                className="h-4 w-4 rounded border-slate-300 text-rr-600 focus:ring-rr-500 dark:border-slate-600 dark:bg-slate-800"
              />
              <span className="whitespace-nowrap text-xs font-medium text-slate-700 dark:text-slate-200">
                Last match in 2026 (all data)
              </span>
            </label>
            <label className="flex h-[38px] cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-3 text-sm dark:border-slate-700">
              <input
                type="checkbox"
                checked={filters.availableOnly}
                onChange={(event) => {
                  const availableOnly = event.target.checked;
                  setFilters((current) => ({ ...current, availableOnly }));
                  setSort({
                    key: availableOnly ? "clean_rank" : "all_rank",
                    dir: "asc",
                  });
                }}
                className="h-4 w-4 rounded border-slate-300 text-rr-600 focus:ring-rr-500 dark:border-slate-600 dark:bg-slate-800"
              />
              <span className="whitespace-nowrap text-xs font-medium text-slate-700 dark:text-slate-200">
                Available only
              </span>
            </label>
            <label className="flex h-[38px] cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-3 text-sm dark:border-slate-700">
              <input
                type="checkbox"
                checked={filters.currentTeamUnset}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    currentTeamUnset: event.target.checked,
                  }))
                }
                className="h-4 w-4 rounded border-slate-300 text-rr-600 focus:ring-rr-500 dark:border-slate-600 dark:bg-slate-800"
              />
              <span className="whitespace-nowrap text-xs font-medium text-slate-700 dark:text-slate-200">
                Current team not set
              </span>
            </label>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-slate-100 pt-3 text-[11px] text-slate-500 dark:border-slate-800 dark:text-slate-400">
          <span>
            Showing <strong className="num text-slate-700 dark:text-slate-200">{tableRows.length}</strong>{" "}
            of <span className="num">{state.rows.length}</span> ranked {plural}
            {authenticated ? null : " (preview)"}
          </span>
          <span aria-hidden="true">·</span>
          <span>
            Available pool: <strong className="num text-slate-700 dark:text-slate-200">{availableCount}</strong>
          </span>
          <span aria-hidden="true">·</span>
          <span>
            Qualified: <strong className="num text-slate-700 dark:text-slate-200">{qualifiedCount}</strong>
            {" "}of {state.rows.length}
          </span>
          <span aria-hidden="true">·</span>
          <span>
            Shortlist in view: <strong className="num text-slate-700 dark:text-slate-200">{shortlistCount}</strong>
          </span>
          <span aria-hidden="true">·</span>
          <span title="Clean ranks 1–10 with a current team set">
            Current team set for the shortlist:{" "}
            <strong className="num text-slate-700 dark:text-slate-200">
              {shortlistTeamCount} of {shortlistRows.length}
            </strong>
          </span>
          <span aria-hidden="true">·</span>
          <span>
            Missing current team:{" "}
            <strong className="num text-slate-700 dark:text-slate-200">{unsetCount}</strong>
          </span>
          {hasFilters ? (
            <button
              type="button"
              onClick={resetFilters}
              className="ml-auto font-semibold text-rr-700 hover:underline dark:text-rr-300"
            >
              Reset filters
            </button>
          ) : null}
        </div>
      </section>

      {authenticated && selected.size > 0 ? (
        <section className="card sticky top-2 z-20 p-3" aria-label="Bulk set current team">
          <div className="flex flex-wrap items-end gap-2">
            <div className="mr-2">
              <p className="text-xs font-bold text-slate-900 dark:text-white">
                {selected.size} selected
              </p>
              <p className="text-[10px] text-slate-500 dark:text-slate-400">
                {bulkChangeCount} selected players will change
              </p>
            </div>
            <div className="min-w-[14rem]">
              <label htmlFor="rank-bulk-current-team" className="label">
                Set current team
              </label>
              <select
                id="rank-bulk-current-team"
                className="select mt-1 h-9 py-1 text-xs"
                value={bulkTeam}
                onChange={(event) => {
                  setBulkTeam(event.target.value);
                  setBulkError(null);
                }}
              >
                <option value={KEEP_TEAM}>Choose a team…</option>
                <option value={CLEAR_TEAM}>Clear current team</option>
                <optgroup label="IPL franchises">
                  {IPL_TEAMS.map((team) => (
                    <option key={team} value={team}>
                      {team}
                    </option>
                  ))}
                </optgroup>
                <optgroup label="IPL availability">
                  <option value={RELEASED_TEAM}>{RELEASED_TEAM}</option>
                  <option value={NO_TEAM}>{NO_TEAM}</option>
                </optgroup>
                <option value={OTHER_TEAM}>Other team…</option>
              </select>
            </div>
            {bulkTeam === OTHER_TEAM ? (
              <div className="min-w-[14rem]">
                <label htmlFor="rank-bulk-other-team" className="label">
                  Other team name
                </label>
                <input
                  id="rank-bulk-other-team"
                  className="input mt-1 h-9 py-1 text-xs"
                  value={bulkOther}
                  list={`rank-bulk-team-suggestions-${role}`}
                  onChange={(event) => setBulkOther(event.target.value)}
                  placeholder="Enter team name"
                  maxLength={80}
                />
                <datalist id={`rank-bulk-team-suggestions-${role}`}>
                  {[...teamLists.dataTeams, ...teamLists.typedTeams].map((team) => (
                    <option key={team} value={team} />
                  ))}
                </datalist>
              </div>
            ) : null}
            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setSelected(new Set())}
                disabled={bulkSaving}
              >
                Clear selection
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={
                  bulkSaving ||
                  bulkTeamValue === undefined ||
                  !bulkTeamValid ||
                  bulkChangeCount === 0
                }
                onClick={() => {
                  setBulkError(null);
                  setBulkConfirmOpen(true);
                }}
              >
                Set team for {selected.size}
              </button>
            </div>
          </div>
          {bulkError ? (
            <p role="alert" className="mt-2 text-xs text-red-700 dark:text-red-300">
              {bulkError}
            </p>
          ) : null}
        </section>
      ) : null}

      {state.loading ? (
        <LoadingBlock rows={8} />
      ) : (
        <section className="card overflow-hidden" aria-label={`${plural} ranking table`}>
          <DataTable
            columns={columns}
            rows={tableRows}
            sort={sort}
            onSort={onSort}
            rowKey={rowKey}
            selection={
              authenticated
                ? {
                    selected,
                    allSelected,
                    someSelected,
                    onToggle: toggleSelected,
                    onToggleAll: toggleAllSelected,
                  }
                : undefined
            }
            rowClassName={(row) =>
              isNumber(row.clean_rank) && row.clean_rank <= 10
                ? "bg-rr-50/80 hover:bg-rr-50 dark:bg-rr-500/[0.08] dark:hover:bg-rr-500/[0.13]"
                : isNumber(row.clean_rank) && row.clean_rank <= 20
                  ? "bg-sky-50/70 hover:bg-sky-50 dark:bg-sky-500/[0.07] dark:hover:bg-sky-500/[0.12]"
                  : !row.available
                    ? "opacity-60"
                    : undefined
            }
            empty={
              <EmptyState
                className="border-0"
                title="No players match these filters"
                hint="Try clearing the search, raising the IPL-ball minimum, or allowing all availability statuses."
              />
            }
            caption={`${role} source analysis rankings with qualification and availability`}
          />

          {authenticated ? null : (
            <LockBanner
              shown={tableRows.length}
              total={sorted.length}
              noun={plural}
              className="m-4"
            />
          )}

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-slate-200 px-4 py-3 text-[11px] text-slate-500 dark:border-slate-800 dark:text-slate-400">
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm bg-rr-500" />
              Clean ranks 1–10 (shortlist)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm bg-sky-400" />
              Clean ranks 11–20 (reserves)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm bg-slate-300 dark:bg-slate-700" />
              Outside the shortlist
            </span>
            <span className="ml-auto hidden sm:inline">
              {role === "bowler"
                ? "Bowling ranks are descriptive, not a stable skill hierarchy."
                : "Composite scores are relative ratings, not predictions of future performance."}
            </span>
          </div>
        </section>
      )}

      <Modal
        open={bulkConfirmOpen}
        title="Set current team"
        subtitle={`${bulkChangeCount} of ${selectedRows.length} selected players will change`}
        onClose={() => {
          if (!bulkSaving) {
            setBulkConfirmOpen(false);
            setBulkError(null);
          }
        }}
        footer={
          <>
            <button
              type="button"
              className="btn-ghost"
              disabled={bulkSaving}
              onClick={() => setBulkConfirmOpen(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={bulkSaving || bulkChangeCount === 0}
              onClick={applyBulkTeam}
            >
              {bulkSaving ? "Applying…" : `Set team for ${bulkChangeCount}`}
            </button>
          </>
        }
      >
        <div className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
          <p>
            The selected players’ current team will be set to{" "}
            <strong className="text-slate-900 dark:text-white">
              {bulkTeamValue || "no team"}
            </strong>
            . IPL franchise and availability choices will also update their mapped status.
          </p>
          {bulkError ? (
            <p role="alert" className="text-xs text-red-700 dark:text-red-300">
              {bulkError}
            </p>
          ) : null}
        </div>
      </Modal>

      <p className="text-[11px] leading-relaxed text-slate-400 dark:text-slate-500">
        All-player ranks and scores are taken directly from the supplied analysis CSV; the
        qualified rank and qualification status are also source-provided. Clean rank filters
        players by the availability status you maintain here. The source covers IPL 2022–2026
        and T20I competitions, but does not verify 2027 registration, contracts, injuries, or
        auction availability. Current team is your manual value when set; otherwise the team
        filter falls back to the latest team in the data. See{" "}
        <Link to="/availability" className="link">
          the availability workspace
        </Link>{" "}
        to edit them.
      </p>
    </div>
  );
}
