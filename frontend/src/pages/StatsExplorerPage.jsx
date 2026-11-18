import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth, LockIcon } from "../auth";
import DataTable from "../components/DataTable";
import { EmptyState, ErrorNote, LoadingBlock } from "../components/States";
import { fmtInt, fmtNum } from "../utils";

const BATTING_COLUMNS = [
  ["batting.matches", "Mat", "int"],
  ["batting.innings", "Inn", "int"],
  ["batting.runs", "Runs", "int"],
  ["batting.balls", "Balls", "int"],
  ["batting.strike_rate", "SR", "num2"],
  ["batting.average", "Avg", "num2"],
  ["batting.highest", "HS", "int"],
  ["batting.fifties", "50s", "int"],
  ["batting.hundreds", "100s", "int"],
  ["batting.ducks", "Ducks", "int"],
  ["batting.boundary_pct", "Bdry %", "num1"],
  ["batting.dot_pct", "Dot %", "num1"],
  ["batting.balls_per_boundary", "B/Bdry", "num1"],
  ["batting.position", "Pos", "int"],
];

const BOWLING_COLUMNS = [
  ["bowling.matches", "Mat", "int"],
  ["bowling.innings", "Inn", "int"],
  ["bowling.legal_balls", "Legal balls", "int"],
  ["bowling.overs", "Overs", "text"],
  ["bowling.runs", "Runs", "int"],
  ["bowling.wickets", "Wkts", "int"],
  ["bowling.economy", "Econ", "num2"],
  ["bowling.average", "Avg", "num2"],
  ["bowling.strike_rate", "SR", "num2"],
  ["bowling.dot_pct", "Dot %", "num1"],
  ["bowling.maidens", "Maidens", "int"],
  ["bowling.best", "Best", "best"],
  ["bowling.four_w", "4W+", "int"],
  ["bowling.balls_per_boundary", "B/Bdry", "num1"],
];

const MIXED_COLUMNS = [
  ["batting.matches", "Bat Mat", "int"],
  ["batting.runs", "Bat runs", "int"],
  ["batting.balls", "Bat balls", "int"],
  ["batting.strike_rate", "Bat SR", "num2"],
  ["bowling.matches", "Bowl Mat", "int"],
  ["bowling.legal_balls", "Bowl balls", "int"],
  ["bowling.wickets", "Wkts", "int"],
  ["bowling.economy", "Econ", "num2"],
  ["bowling.dot_pct", "Bowl dot %", "num1"],
  ["bowling.best", "Best", "best"],
];

const DEFAULTS = {
  batter: [
    "batting.matches",
    "batting.runs",
    "batting.balls",
    "batting.strike_rate",
    "batting.average",
    "batting.highest",
    "batting.fifties",
    "batting.boundary_pct",
  ],
  bowler: [
    "bowling.matches",
    "bowling.legal_balls",
    "bowling.wickets",
    "bowling.economy",
    "bowling.average",
    "bowling.strike_rate",
    "bowling.dot_pct",
    "bowling.four_w",
  ],
  all: [
    "batting.runs",
    "batting.strike_rate",
    "bowling.legal_balls",
    "bowling.wickets",
    "bowling.economy",
    "bowling.dot_pct",
    "bowling.best",
  ],
};

function columnDefs(mode) {
  if (mode === "batter") return BATTING_COLUMNS;
  if (mode === "bowler") return BOWLING_COLUMNS;
  return MIXED_COLUMNS;
}

function getPath(row, path) {
  return path.split(".").reduce((value, key) => (value == null ? null : value[key]), row);
}

function formatValue(value, kind) {
  if (value === null || value === undefined) return "—";
  if (kind === "best") return `${value.wickets}/${value.runs}`;
  if (kind === "text") return String(value);
  if (kind === "num2") return fmtNum(value, 2);
  if (kind === "num1") return fmtNum(value, 1);
  return fmtInt(value);
}

function csvCell(value) {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function downloadCsv(name, header, rows) {
  const lines = [header.map(csvCell).join(","), ...rows.map((row) => row.map(csvCell).join(","))];
  const blob = new Blob([`${lines.join("\n")}\n`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export default function StatsExplorerPage() {
  const { authenticated, openLogin } = useAuth();
  const [state, setState] = useState({ loading: true, error: null, data: null });
  const [mode, setMode] = useState("batter");
  const [team, setTeam] = useState("");
  const [competition, setCompetition] = useState("");
  const [season, setSeason] = useState("");
  const [minBalls, setMinBalls] = useState("0");
  const [query, setQuery] = useState("");
  const [visible, setVisible] = useState(DEFAULTS.batter);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [sort, setSort] = useState({ key: "batting.runs", dir: "desc" });

  useEffect(() => {
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: null }));
    api
      .statsIndex({
        role: mode === "all" ? undefined : mode,
        team: team || undefined,
        competition: competition || undefined,
        season: season || undefined,
        minBalls: minBalls === "" ? 0 : Number(minBalls),
      })
      .then((data) => {
        if (!cancelled) setState({ loading: false, error: null, data });
      })
      .catch((error) => {
        if (!cancelled) setState({ loading: false, error: error.message, data: null });
      });
    return () => {
      cancelled = true;
    };
  }, [mode, team, competition, season, minBalls]);

  useEffect(() => {
    setVisible(DEFAULTS[mode]);
    setSort({ key: columnDefs(mode)[2][0], dir: "desc" });
  }, [mode]);

  const defs = useMemo(() => columnDefs(mode), [mode]);
  const options = state.data?.options || {};
  const rows = useMemo(() => {
    const source = state.data?.rows || [];
    const needle = query.trim().toLowerCase();
    const filtered = needle
      ? source.filter(
          (row) =>
            String(row.name || "").toLowerCase().includes(needle) ||
            String(row.latest_team || "").toLowerCase().includes(needle),
        )
      : source;
    const active = defs.find(([key]) => key === sort.key);
    const sorted = [...filtered];
    if (active) {
      sorted.sort((a, b) => {
        const av = getPath(a, active[0]);
        const bv = getPath(b, active[0]);
        if (av === null || av === undefined) return 1;
        if (bv === null || bv === undefined) return -1;
        if (typeof av === "number" && typeof bv === "number") {
          return sort.dir === "asc" ? av - bv : bv - av;
        }
        const cmp = String(av).localeCompare(String(bv));
        return sort.dir === "asc" ? cmp : -cmp;
      });
    }
    return sorted;
  }, [state.data, query, sort, defs]);

  const columns = [
    {
      key: "name",
      label: "Player",
      sortable: false,
      cell: (row) => (
        <Link
          to={
            row.ranked_role
              ? `/player/${row.ranked_role}/${row.player_id}`
              : `/recent-form/${row.player_id}`
          }
          className="font-semibold text-slate-900 hover:text-rr-700 dark:text-white dark:hover:text-rr-300"
          title={row.ranked_role ? "Open player profile" : "Open recent form"}
        >
          {row.name}
        </Link>
      ),
    },
    {
      key: "role",
      label: "Role",
      sortable: false,
      cell: (row) => <span className="capitalize">{row.role}</span>,
    },
    {
      key: "team",
      label: "Team",
      sortable: false,
      cell: (row) => row.latest_team || "—",
    },
    ...defs
      .filter(([key]) => visible.includes(key))
      .map(([key, label, kind]) => ({
        key,
        label,
        align: "right",
        sortable: true,
        cell: (row) => {
          const value = getPath(row, key);
          const balls =
            key === "batting.balls"
              ? getPath(row, "batting.balls")
              : key === "bowling.legal_balls"
                ? getPath(row, "bowling.legal_balls")
                : null;
          return (
            <span className="num">
              {formatValue(value, kind)}
              {balls !== null && balls !== undefined && balls < 30 ? (
                <span className="ml-1 rounded bg-amber-50 px-1 text-[8px] font-bold uppercase text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                  ss
                </span>
              ) : null}
            </span>
          );
        },
      })),
  ];

  const onSort = (key) =>
    setSort((current) =>
      current.key === key
        ? { key, dir: current.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "desc" },
    );

  const exportRows = () => {
    if (!authenticated) {
      openLogin();
      return;
    }
    const header = ["Player", "Role", "Team", ...defs.filter(([key]) => visible.includes(key)).map(([, label]) => label)];
    const body = rows.map((row) => [
      row.name,
      row.role,
      row.latest_team || "",
      ...defs.filter(([key]) => visible.includes(key)).map(([key, , kind]) => {
        const value = getPath(row, key);
        if (kind === "best" && value) return `${value.wickets}/${value.runs}`;
        return value ?? "";
      }),
    ]);
    downloadCsv("rr-stats-explorer.csv", header, body);
  };

  const meta = state.data?.meta || {};
  const threshold = state.data?.threshold_balls;
  const tableRows = rows;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rr-600 dark:text-rr-300">
            Stats Explorer
          </p>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-900 dark:text-white">
            Batting and bowling aggregates
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-500 dark:text-slate-400">
            Derived from the confidential delivery data by precompute.py. Only aggregate tables are
            exposed; no delivery-level rows leave the backend. Click a ranked player to open their
            profile, with separate Stats Explorer and Recent matches tabs. Percentile thresholds: {meta.bat_percentile_balls ?? 100} batting balls /{" "}
            {meta.bowl_percentile_balls ?? 120} legal balls.
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" className="btn-ghost" onClick={() => setPickerOpen((value) => !value)}>
            Columns
          </button>
          <button type="button" className="btn-primary" onClick={exportRows} disabled={!rows.length}>
            {authenticated ? null : <LockIcon className="h-4 w-4" />}
            Export CSV
          </button>
        </div>
      </div>

      <section className="card space-y-3 p-4">
        <div className="flex flex-wrap items-end gap-2">
          <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 dark:border-slate-700 dark:bg-slate-900">
            {[
              ["batter", "Batters"],
              ["bowler", "Bowlers"],
              ["all", "All"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setMode(value)}
                className={
                  mode === value
                    ? "rounded-md bg-rr-600 px-3 py-1 text-xs font-semibold text-white"
                    : "rounded-md px-3 py-1 text-xs font-semibold text-slate-500"
                }
              >
                {label}
              </button>
            ))}
          </div>
          <label className="text-[11px] text-slate-500 dark:text-slate-400">
            <span className="mb-0.5 block font-semibold uppercase tracking-wide">Search</span>
            <input
              className="input h-8 w-44 py-1 text-xs"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Player or team"
            />
          </label>
          <label className="text-[11px] text-slate-500 dark:text-slate-400">
            <span className="mb-0.5 block font-semibold uppercase tracking-wide">Team</span>
            <select className="select h-8 w-44 py-1 text-xs" value={team} onChange={(event) => setTeam(event.target.value)}>
              <option value="">All teams</option>
              {(options.teams || []).map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>
          <label className="text-[11px] text-slate-500 dark:text-slate-400">
            <span className="mb-0.5 block font-semibold uppercase tracking-wide">Competition</span>
            <select className="select h-8 w-32 py-1 text-xs" value={competition} onChange={(event) => setCompetition(event.target.value)}>
              <option value="">All</option>
              {(options.competitions || []).map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>
          <label className="text-[11px] text-slate-500 dark:text-slate-400">
            <span className="mb-0.5 block font-semibold uppercase tracking-wide">Season</span>
            <select className="select h-8 w-28 py-1 text-xs" value={season} onChange={(event) => setSeason(event.target.value)}>
              <option value="">All</option>
              {(options.seasons || []).map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>
          <label className="text-[11px] text-slate-500 dark:text-slate-400">
            <span className="mb-0.5 block font-semibold uppercase tracking-wide">Min balls</span>
            <input
              type="number"
              min="0"
              step="10"
              className="input h-8 w-24 py-1 text-xs"
              value={minBalls}
              onChange={(event) => setMinBalls(event.target.value)}
            />
          </label>
          <p className="num ml-auto text-xs text-slate-500 dark:text-slate-400">
            {state.data ? `${fmtInt(state.data.count)} players` : "—"}
            {threshold ? ` · percentile cohort ≥ ${threshold} balls` : ""}
          </p>
        </div>

        {pickerOpen ? (
          <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Visible columns
            </p>
            <div className="mt-2 grid grid-cols-2 gap-1.5 sm:grid-cols-4 lg:grid-cols-6">
              {defs.map(([key, label]) => (
                <label key={key} className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300">
                  <input
                    type="checkbox"
                    className="h-3.5 w-3.5 rounded border-slate-300 text-rr-600"
                    checked={visible.includes(key)}
                    onChange={(event) =>
                      setVisible((current) =>
                        event.target.checked
                          ? [...current, key]
                          : current.filter((item) => item !== key),
                      )
                    }
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      {state.error ? <ErrorNote message={state.error} /> : null}
      {state.loading && !state.data ? <LoadingBlock rows={8} /> : null}

      {state.data ? (
        state.data.ready ? (
          <section className="card overflow-hidden">
            <DataTable
              columns={columns}
              rows={tableRows}
              sort={sort}
              onSort={onSort}
              rowKey={(row) => row.player_id}
              caption="Stats Explorer"
              empty={
                <EmptyState
                  title="No players match"
                  hint="Relax the filters or lower the minimum balls."
                />
              }
            />
          </section>
        ) : (
          <EmptyState
            title="Stats aggregates are not built yet"
            hint="Run python precompute.py from the project root to create data_derived/stats."
          />
        )
      ) : null}

      <p className="text-[10px] leading-relaxed text-slate-400 dark:text-slate-500">
        Small sample = fewer than 30 balls in the relevant split (marked ss). No fielding stats are
        available: the supplied data has no fielder IDs. Career values exclude super overs, the two
        Emerging tournaments and DLS/shortened matches.
      </p>
    </div>
  );
}
