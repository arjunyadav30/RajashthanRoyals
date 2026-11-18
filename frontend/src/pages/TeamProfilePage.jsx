import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth, LockIcon } from "../auth";
import { FlagBadge, PlayerAvatar, RankChip, StatusPill } from "../components/Badges";
import DataTable from "../components/DataTable";
import { ErrorNote, LoadingBlock } from "../components/States";
import { compareValues, cx, fmtDateTime, fmtInt, fmtNum, isNumber } from "../utils";

const DIMENSIONS = [
  { key: "batting", label: "Batting", hint: "Average 0–100 rating of the top five XI batters" },
  { key: "bowling", label: "Bowling", hint: "Average 0–100 rating of the top four XI bowlers" },
  { key: "depth", label: "Depth", hint: "Players rated 60+ with 100+ pressure balls" },
  { key: "pressure", label: "Pressure", hint: "Mean pressure-vs-normal delta across the XI" },
  { key: "experience", label: "Experience", hint: "Combined matches across the XI" },
  { key: "death_options", label: "Death options", hint: "XI bowlers whose dominant phase is death" },
  { key: "powerplay_batters", label: "PP batters", hint: "XI batters whose dominant phase is powerplay" },
  { key: "all_rounders", label: "All-rounders", hint: "XI players qualified with both bat and ball" },
];

function metricValue(key, value) {
  if (key === "experience") return fmtInt(value);
  if (["batting", "bowling", "pressure"].includes(key)) return fmtNum(value);
  return fmtInt(value);
}

function playerRole(player) {
  return player.is_batter ? "batter" : "bowler";
}

function PlayerLink({ player, avatarSize = "sm" }) {
  return (
    <Link
      to={`/player/${playerRole(player)}/${player.player_id}`}
      className="group flex items-center gap-2.5"
    >
      <PlayerAvatar name={player.name} role={playerRole(player)} size={avatarSize} />
      <span className="min-w-0">
        <span className="block truncate font-semibold text-slate-900 group-hover:text-rr-700 dark:text-white dark:group-hover:text-rr-300">
          {player.name}
        </span>
        <span className="block truncate text-[10px] text-slate-500 dark:text-slate-400">
          {player.player_type || "Squad"}
          {player.dominant_phase ? ` · ${player.dominant_phase}` : ""}
          {player.overseas ? ` · ${player.country || "Overseas"}` : ""}
        </span>
      </span>
    </Link>
  );
}

function PlayerFlags({ player }) {
  return (
    <span className="flex flex-wrap gap-1">
      {player.wk ? <FlagBadge label="WK" tone="sky" title={`Wicketkeeper, ${player.wk_matches} matches`} /> : null}
      {player.captain ? <FlagBadge label="C" tone="emerald" title="Captained in the data" /> : null}
      {player.overseas ? (
        <FlagBadge label="OS" tone="slate" title={player.country ? `Overseas — ${player.country}` : "Overseas player"} />
      ) : null}
      {!player.selectable ? <FlagBadge label="SMALL" tone="amber" title="Below the 50-pressure-ball role minimum — wide uncertainty" /> : null}
    </span>
  );
}

function ScoreCell({ value, lo, hi }) {
  return (
    <div className="leading-tight">
      <span className="num text-sm font-bold text-slate-900 dark:text-white">{fmtNum(value)}</span>
      {isNumber(lo) && isNumber(hi) ? (
        <p className="num text-[10px] text-slate-400 dark:text-slate-500">
          {fmtNum(lo)}–{fmtNum(hi)}
        </p>
      ) : null}
    </div>
  );
}

const XI_COLUMNS = [
  {
    key: "order",
    label: "#",
    align: "center",
    cell: (row) => <span className="num text-xs font-bold text-slate-500 dark:text-slate-400">{row.order}</span>,
  },
  {
    key: "name",
    label: "Player",
    cell: (row) => <PlayerLink player={row} />,
  },
  {
    key: "flags",
    label: "Flags",
    cell: (row) => <PlayerFlags player={row} />,
    headerClassName: "hidden sm:table-cell",
    cellClassName: "hidden sm:table-cell",
  },
  {
    key: "score",
    label: "Score",
    align: "right",
    cell: (row) => <ScoreCell value={row.score} lo={row.score_lo} hi={row.score_hi} />,
  },
  {
    key: "pressure_balls",
    label: "P balls",
    align: "right",
    cell: (row) => <span className="num text-xs">{fmtInt(row.pressure_balls)}</span>,
    headerClassName: "hidden sm:table-cell",
    cellClassName: "hidden sm:table-cell",
  },
  {
    key: "split",
    label: "Bat / Bowl",
    align: "right",
    cell: (row) => (
      <span className="num text-xs">
        {fmtNum(row.batting_score)} / {fmtNum(row.bowling_score)}
      </span>
    ),
    headerClassName: "hidden md:table-cell",
    cellClassName: "hidden md:table-cell",
  },
  {
    key: "status",
    label: "Status",
    cell: (row) => <StatusPill status={row.status} />,
    headerClassName: "hidden lg:table-cell",
    cellClassName: "hidden lg:table-cell",
  },
];

function BenchColumns() {
  return [
    { key: "name", label: "Player", cell: (row) => <PlayerLink player={row} /> },
    {
      key: "score",
      label: "Score",
      align: "right",
      cell: (row) => <ScoreCell value={row.score} lo={row.score_lo} hi={row.score_hi} />,
    },
    {
      key: "pressure_balls",
      label: "P balls",
      align: "right",
      cell: (row) => <span className="num text-xs">{fmtInt(row.pressure_balls)}</span>,
    },
    {
      key: "split",
      label: "Bat / Bowl",
      align: "right",
      cell: (row) => (
        <span className="num text-xs">
          {fmtNum(row.batting_score)} / {fmtNum(row.bowling_score)}
        </span>
      ),
      headerClassName: "hidden sm:table-cell",
      cellClassName: "hidden sm:table-cell",
    },
  ];
}

function RosterColumns() {
  return [
    { key: "name", label: "Player", cell: (row) => <PlayerLink player={row} /> },
    { key: "score", label: "Score", sortable: true, align: "right", cell: (row) => <ScoreCell value={row.score} lo={row.score_lo} hi={row.score_hi} />, sortValue: (row) => row.score },
    { key: "pressure_balls", label: "P balls", sortable: true, align: "right", cell: (row) => <span className="num text-xs">{fmtInt(row.pressure_balls)}</span>, sortValue: (row) => row.pressure_balls },
    { key: "batting_score", label: "Bat", sortable: true, align: "right", cell: (row) => <span className="num text-xs">{fmtNum(row.batting_score)}</span>, sortValue: (row) => row.batting_score, headerClassName: "hidden sm:table-cell", cellClassName: "hidden sm:table-cell" },
    { key: "bowling_score", label: "Bowl", sortable: true, align: "right", cell: (row) => <span className="num text-xs">{fmtNum(row.bowling_score)}</span>, sortValue: (row) => row.bowling_score, headerClassName: "hidden sm:table-cell", cellClassName: "hidden sm:table-cell" },
    { key: "strike_rate", label: "SR", sortable: true, align: "right", cell: (row) => <span className="num text-xs">{fmtNum(row.strike_rate)}</span>, sortValue: (row) => row.strike_rate, headerClassName: "hidden md:table-cell", cellClassName: "hidden md:table-cell" },
    { key: "economy", label: "Econ", sortable: true, align: "right", cell: (row) => <span className="num text-xs">{fmtNum(row.economy, 2)}</span>, sortValue: (row) => row.economy, headerClassName: "hidden md:table-cell", cellClassName: "hidden md:table-cell" },
    { key: "overseas", label: "Nat", cell: (row) => (row.overseas ? <FlagBadge label="OS" tone="slate" title={row.country || "Overseas"} /> : <span className="text-xs text-slate-400 dark:text-slate-500">IND</span>), headerClassName: "hidden lg:table-cell", cellClassName: "hidden lg:table-cell" },
    { key: "status", label: "Status", cell: (row) => <StatusPill status={row.status} />, headerClassName: "hidden lg:table-cell", cellClassName: "hidden lg:table-cell" },
  ];
}

const DEFAULT_ROSTER_SORT = { key: "score", dir: "desc" };

const ROLE_LABEL = { keeping: "Keeper", batting: "Batting", bowling: "Bowling" };

function ShapeChips({ draft }) {
  const keeper = draft.some((p) => p.wk);
  const batters = draft.filter((p) => p.bat_option).length;
  const bowlers = draft.filter((p) => p.bowl_option).length;
  const overseas = draft.filter((p) => p.overseas).length;
  const chips = [
    ["WK", keeper, keeper ? "1 keeper" : "no keeper"],
    ["Bat", batters >= 5, `${batters}/5 batting options`],
    ["Bowl", bowlers >= 4, `${bowlers}/4 bowling options`],
    ["OS", overseas <= 4, `${overseas}/4 overseas`],
  ];
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {chips.map(([label, ok, text]) => (
        <span
          key={label}
          title={text}
          className={cx(
            "rounded-full px-2 py-0.5 text-[10px] font-bold ring-1 ring-inset",
            ok
              ? "bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-300"
              : "bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300",
          )}
        >
          {label} {text}
        </span>
      ))}
    </div>
  );
}

function DimensionBar({ dimension, metrics }) {
  const rank = metrics.ranks?.[dimension.key];
  const value = metrics[dimension.key];
  const width = isNumber(rank) ? ((11 - rank) / 10) * 100 : 0;
  return (
    <div title={dimension.hint}>
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="font-medium text-slate-700 dark:text-slate-200">{dimension.label}</span>
        <span className="num text-slate-500 dark:text-slate-400">
          {metricValue(dimension.key, value)}
          {isNumber(rank) ? <span className="ml-1.5 text-slate-400 dark:text-slate-500">#{rank}</span> : null}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className={cx(
            "h-full rounded-full",
            isNumber(rank) && rank <= 3
              ? "bg-emerald-500"
              : isNumber(rank) && rank >= 9
                ? "bg-red-500"
                : "bg-rr-500",
          )}
          style={{ width: `${Math.max(width, 4)}%` }}
        />
      </div>
    </div>
  );
}

function StrengthList({ title, items, tone }) {
  return (
    <div
      className={cx(
        "rounded-xl border p-3",
        tone === "good"
          ? "border-emerald-200/70 bg-emerald-50/60 dark:border-emerald-900/50 dark:bg-emerald-950/20"
          : "border-red-200/70 bg-red-50/60 dark:border-red-900/50 dark:bg-red-950/20",
      )}
    >
      <p
        className={cx(
          "text-[10px] font-bold uppercase tracking-wider",
          tone === "good" ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400",
        )}
      >
        {title}
      </p>
      <ul className="mt-2 space-y-2">
        {items.map((item) => (
          <li key={item.key} className="flex items-start gap-2">
            <RankChip rank={item.rank} tone={item.rank <= 3 ? "shortlist" : "default"} />
            <span className="min-w-0">
              <span className="block text-xs font-semibold text-slate-800 dark:text-slate-100">
                {item.label}
              </span>
              <span className="block text-[11px] leading-snug text-slate-600 dark:text-slate-400">
                {item.text}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function TeamProfilePage() {
  const { slug } = useParams();
  const { authenticated, openLogin } = useAuth();
  const [state, setState] = useState({ loading: true, error: null, team: null });
  const [rosterOpen, setRosterOpen] = useState(false);
  const [rosterSort, setRosterSort] = useState(DEFAULT_ROSTER_SORT);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState("");

  const load = useCallback(() => {
    setState((current) => ({ ...current, loading: true, error: null }));
    return api
      .team(slug)
      .then((team) => setState({ loading: false, error: null, team }))
      .catch((error) => setState((current) => ({ ...current, loading: false, error: error.message })));
  }, [slug]);

  useEffect(() => {
    setRosterOpen(false);
    setRosterSort(DEFAULT_ROSTER_SORT);
    setDraft(null);
    setEditError("");
    load();
  }, [load]);

  const rosterColumns = useMemo(() => RosterColumns(), []);
  const rosterSortColumn = useMemo(
    () => rosterColumns.find((column) => column.key === rosterSort.key),
    [rosterColumns, rosterSort.key],
  );
  const sortedRoster = useMemo(() => {
    if (!state.team) return [];
    const accessor = rosterSortColumn?.sortValue ?? (() => null);
    const copy = [...state.team.roster];
    copy.sort((a, b) => {
      const result = compareValues(accessor(a), accessor(b));
      return rosterSort.dir === "asc" ? result : -result;
    });
    return copy;
  }, [state.team, rosterSortColumn, rosterSort.dir]);

  const xiColumns = useMemo(() => {
    const fitOptions = state.team?.fit_options || {};
    const bestByPlayer = {};
    const suggested = new Set();
    for (const row of state.team?.xi || []) {
      const option = fitOptions[String(row.player_id ?? "")];
      const players = option?.players || [];
      const pick = players.find((candidate) => !suggested.has(candidate.name)) || players[0];
      if (pick) {
        bestByPlayer[String(row.player_id ?? "")] = pick;
        suggested.add(pick.name);
      }
    }
    return [
      ...XI_COLUMNS,
      {
        key: "best_fit",
        label: "Best fit",
        cell: (row) => {
          const option = fitOptions[String(row.player_id ?? "")];
          const best = bestByPlayer[String(row.player_id ?? "")];
          if (!best) return <span className="text-xs text-slate-400 dark:text-slate-500">—</span>;
          return (
            <div className="leading-tight">
              <span className="block max-w-[9rem] truncate text-xs font-semibold text-slate-700 dark:text-slate-200">
                {best.name}
              </span>
              <span className="num text-[10px] text-slate-400 dark:text-slate-500">
                {ROLE_LABEL[option.role] || option.role} fit {fmtNum(best.fit_score)}/100
                {best.source === "pool" ? " · pool" : " · squad"}
                {best.best_use ? ` · ${best.best_use}` : ""}
              </span>
            </div>
          );
        },
      },
    ];
  }, [state.team]);

  const onRosterSort = useCallback((key) => {
    setRosterSort((current) =>
      current.key === key
        ? { key, dir: current.dir === "asc" ? "desc" : "asc" }
        : { key, dir: key === "name" ? "asc" : "desc" },
    );
  }, []);

  if (state.loading) {
    return (
      <div className="space-y-5">
        <LoadingBlock rows={6} />
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="space-y-5">
        <ErrorNote message={state.error} onRetry={load} />
        <Link to="/teams" className="link text-sm">
          ← Back to all teams
        </Link>
      </div>
    );
  }

  const team = state.team;
  const metrics = team.metrics;

  const startEdit = () => {
    if (!authenticated) {
      openLogin();
      return;
    }
    setEditError("");
    setDraft(team.xi.map((player) => ({ ...player })));
  };

  const cancelEdit = () => {
    setDraft(null);
    setEditError("");
  };

  const saveXi = async () => {
    if (!draft) return;
    setSaving(true);
    setEditError("");
    try {
      const payload = await api.saveTeamXi(slug, draft.map((player) => player.name));
      setState({ loading: false, error: null, team: payload });
      setDraft(null);
    } catch (error) {
      setEditError(error.message);
    } finally {
      setSaving(false);
    }
  };

  const resetXi = async () => {
    if (!window.confirm("Reset the XI to the data-driven best selection?")) return;
    setSaving(true);
    setEditError("");
    try {
      const payload = await api.resetTeamXi(slug);
      setState({ loading: false, error: null, team: payload });
      setDraft(null);
    } catch (error) {
      setEditError(error.message);
    } finally {
      setSaving(false);
    }
  };

  const replaceSlot = (index, name) => {
    const player = team.roster.find((row) => row.name === name);
    if (!player) return;
    setDraft((current) => current.map((row, i) => (i === index ? { ...player } : row)));
  };

  const moveSlot = (index, delta) => {
    setDraft((current) => {
      const next = [...current];
      const target = index + delta;
      if (target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const slotCandidates = (player) => {
    const option = team.fit_options?.[String(player.player_id ?? "")];
    const role = option?.role || (player.wk ? "keeping" : player.is_batter ? "batting" : "bowling");
    const inDraft = new Set((draft || []).map((row) => row.name));
    const scored = team.roster.filter(
      (row) =>
        row.name !== player.name && !inDraft.has(row.name) && row.score !== null,
    );
    const roleMatches = (row) =>
      role === "keeping" ? row.wk : role === "bowling" ? row.is_bowler : row.is_batter;
    const roleScore = (row) =>
      role === "bowling"
        ? row.bowling_rating ?? row.rating ?? row.bowling_score ?? row.score
        : row.batting_rating ?? row.rating ?? row.batting_score ?? row.score;
    const fits = scored
      .filter(roleMatches)
      .sort((a, b) => (roleScore(b) ?? 0) - (roleScore(a) ?? 0))
      .slice(0, 5)
      .map((row) => ({ ...row, fit_score: roleScore(row) }));
    const fitNames = new Set(fits.map((row) => row.name));
    const poolFits = (team.pool_fit?.[role] || []).filter(
      (row) => !inDraft.has(row.name),
    );
    const others = scored
      .filter((row) => !fitNames.has(row.name))
      .sort((a, b) => (b.rating ?? b.score ?? 0) - (a.rating ?? a.score ?? 0));
    return { role, fits, poolFits, others };
  };

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link to="/teams" className="text-xs font-semibold text-rr-700 hover:underline dark:text-rr-300">
            ← All teams
          </Link>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-900 sm:text-3xl dark:text-white">
            {team.name}
          </h1>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">
            {team.roster.length} players in the squad · {metrics.scored} scored by the engine ·{" "}
            {metrics.unscored > 0 ? `${metrics.unscored} without a score` : "every player scored"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-center">
          <div className="rounded-xl border border-slate-200 px-3 py-2 dark:border-slate-800">
            <p className="num text-lg font-black text-slate-900 dark:text-white">{fmtNum(metrics.xi_average)}</p>
            <p className="text-[10px] uppercase tracking-wide text-slate-400">XI rating /100</p>
          </div>
          <div className="rounded-xl border border-slate-200 px-3 py-2 dark:border-slate-800">
            <p className="num text-lg font-black text-slate-900 dark:text-white">{fmtNum(metrics.xi_top)}</p>
            <p className="text-[10px] uppercase tracking-wide text-slate-400">Top rating /100</p>
          </div>
          <div className="rounded-xl border border-slate-200 px-3 py-2 dark:border-slate-800">
            <p className="num text-lg font-black text-slate-900 dark:text-white">{metrics.overseas}/4</p>
            <p className="text-[10px] uppercase tracking-wide text-slate-400">Overseas</p>
          </div>
          <div className="rounded-xl border border-slate-200 px-3 py-2 dark:border-slate-800">
            <p className="truncate text-sm font-black text-slate-900 dark:text-white">
              {metrics.keeper || "—"}
            </p>
            <p className="text-[10px] uppercase tracking-wide text-slate-400">Keeper</p>
          </div>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="card space-y-3 p-5 lg:col-span-2" aria-label="League dimension ranks">
          <div className="flex items-baseline justify-between gap-2">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">League profile</h2>
            <span className="text-[10px] text-slate-400 dark:text-slate-500">Rank 1–10 across squads, 1 is best</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {DIMENSIONS.map((dimension) => (
              <DimensionBar key={dimension.key} dimension={dimension} metrics={metrics} />
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 text-[11px] dark:border-slate-800">
            <span
              className={cx(
                "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-semibold ring-1 ring-inset",
                metrics.shape_ok
                  ? "bg-emerald-100 text-emerald-800 ring-emerald-600/20 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-400/30"
                  : "bg-amber-100 text-amber-900 ring-amber-600/20 dark:bg-amber-500/15 dark:text-amber-300 dark:ring-amber-400/30",
              )}
            >
              {metrics.shape_ok ? "XI shape valid" : "XI shape incomplete"}
            </span>
            <span className="text-slate-500 dark:text-slate-400">
              {metrics.batters} batting / {metrics.bowlers} bowling options in the XI
            </span>
            {metrics.low_sample > 0 ? (
              <span className="text-amber-700 dark:text-amber-400">
                {metrics.low_sample} selection(s) on a small pressure sample
              </span>
            ) : null}
          </div>
        </section>

        <section className="space-y-3" aria-label="Strengths and weaknesses">
          <StrengthList title="Strengths" items={team.strengths} tone="good" />
          <StrengthList title="Weaknesses" items={team.weaknesses} tone="bad" />
        </section>
      </div>

      <section className="card overflow-hidden" aria-label="Best XI">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
          <div>
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">
              {draft
                ? "Editing the XI"
                : team.xi_source === "custom"
                  ? "Custom XI"
                  : "Data-driven best XI"}
            </h2>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              {draft
                ? "Replace any slot with its best fit, reorder the batting order, then save."
                : team.xi_source === "custom" && team.xi_updated_at
                  ? `Saved XI · ${fmtDateTime(team.xi_updated_at)} · best-fit replacement shown per slot`
                  : "Best-fit replacement shown per slot · WK · C · OS · SMALL = small sample"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {draft ? (
              <>
                <button
                  type="button"
                  className="btn-ghost h-8 px-2.5 py-1 text-xs"
                  onClick={resetXi}
                  disabled={saving}
                >
                  Reset to best XI
                </button>
                <button
                  type="button"
                  className="btn-ghost h-8 px-2.5 py-1 text-xs"
                  onClick={cancelEdit}
                  disabled={saving}
                >
                  Cancel
                </button>
                <button type="button" className="btn-primary" onClick={saveXi} disabled={saving}>
                  {saving ? "Saving…" : "Save XI"}
                </button>
              </>
            ) : (
              <>
                {authenticated && team.xi_source === "custom" ? (
                  <button
                    type="button"
                    className="btn-ghost h-8 px-2.5 py-1 text-xs"
                    onClick={resetXi}
                    disabled={saving}
                  >
                    Reset to best XI
                  </button>
                ) : null}
                <button type="button" className="btn-ghost" onClick={startEdit}>
                  {authenticated ? null : <LockIcon className="h-4 w-4" />}
                  Edit XI
                </button>
              </>
            )}
          </div>
        </div>

        {draft ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50/60 px-4 py-2 dark:border-slate-800 dark:bg-slate-950/40">
              <ShapeChips draft={draft} />
              <span className="text-[10px] text-slate-400 dark:text-slate-500">
                Best fit comes only from this squad or the auction pool; any scored squad player
                can be picked.
              </span>
            </div>
            <ul className="divide-y divide-slate-100 dark:divide-slate-800/70">
              {draft.map((player, index) => {
                const candidates = slotCandidates(player);
                return (
                  <li
                    key={`${player.player_id ?? player.name}-${index}`}
                    className="flex flex-wrap items-center gap-2 px-4 py-2.5"
                  >
                    <span className="num w-6 shrink-0 text-center text-xs font-black text-slate-400">
                      {index + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <PlayerLink player={player} />
                    </div>
                    <span className="hidden sm:block">
                      <PlayerFlags player={player} />
                    </span>
                    <select
                      className="select h-8 w-56 py-1 text-xs"
                      value={player.name}
                      onChange={(event) => replaceSlot(index, event.target.value)}
                      aria-label={`Replace ${player.name}`}
                    >
                      <option value={player.name}>{player.name} (current)</option>
                      {candidates.fits.length ? (
                        <optgroup
                          label={`Best fits · squad · ${ROLE_LABEL[candidates.role] || candidates.role}`}
                        >
                          {candidates.fits.map((option) => (
                            <option key={option.name} value={option.name}>
                              {option.name} · {fmtNum(option.fit_score)}/100 ·{" "}
                              {fmtInt(option.matches)} mat
                            </option>
                          ))}
                        </optgroup>
                      ) : null}
                      {candidates.poolFits.length ? (
                        <optgroup label="Auction-pool targets (not in squad)">
                          {candidates.poolFits.map((option) => (
                            <option key={option.name} value={option.name} disabled>
                              {option.name} · {fmtNum(option.fit_score)}/100 · pool
                            </option>
                          ))}
                        </optgroup>
                      ) : null}
                      <optgroup label="Other squad players">
                        {candidates.others.map((option) => (
                          <option key={option.name} value={option.name}>
                            {option.name} · {fmtNum(option.score)} score
                          </option>
                        ))}
                      </optgroup>
                    </select>
                    <div className="flex shrink-0 gap-1">
                      <button
                        type="button"
                        className="btn-ghost h-8 px-2 py-1 text-xs"
                        onClick={() => moveSlot(index, -1)}
                        disabled={index === 0}
                        aria-label={`Move ${player.name} up`}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        className="btn-ghost h-8 px-2 py-1 text-xs"
                        onClick={() => moveSlot(index, 1)}
                        disabled={index === draft.length - 1}
                        aria-label={`Move ${player.name} down`}
                      >
                        ↓
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
            {editError ? (
              <p role="alert" className="px-4 py-2 text-xs font-semibold text-red-600 dark:text-red-400">
                {editError}
              </p>
            ) : null}
            <p className="px-4 py-2 text-[10px] leading-relaxed text-slate-400 dark:text-slate-500">
              Saving stores this XI for the team and re-ranks the team metrics from it. The shape
              chips warn when the XI loses its keeper or drops below five batting / four bowling
              options.
            </p>
          </>
        ) : (
          <>
            <DataTable
              columns={xiColumns}
              rows={team.xi}
              rowKey={(row) => `${row.player_id}-${row.order}`}
              caption={`${team.name} best XI`}
            />
          </>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="card overflow-hidden lg:col-span-2" aria-label="Bench">
          <div className="border-b border-slate-200 px-4 py-3 dark:border-slate-800">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">Bench & rotation</h2>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Remaining scored squad members, highest source score first. A WK or overseas player
              can move into the XI when it keeps the shape legal.
            </p>
          </div>
          <DataTable
            columns={BenchColumns()}
            rows={team.bench}
            rowKey={(row) => `bench-${row.player_id}`}
            caption={`${team.name} bench`}
          />
        </section>

        <section className="card p-5" aria-label="Notes">
          <h2 className="text-sm font-bold text-slate-900 dark:text-white">Selection notes</h2>
          <ul className="mt-3 space-y-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
            {team.notes.map((note) => (
              <li key={note} className="flex gap-2">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-rr-500" />
                <span>{note}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 border-t border-slate-100 pt-3 text-[11px] leading-relaxed text-slate-400 dark:border-slate-800 dark:text-slate-500">
            {team.meta.caveat}
          </p>
        </section>
      </div>

      <section className="card overflow-hidden" aria-label="Full roster">
        <button
          type="button"
          onClick={() => setRosterOpen((value) => !value)}
          aria-expanded={rosterOpen}
          className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
        >
          <span>
            <span className="block text-sm font-bold text-slate-900 dark:text-white">Full squad roster</span>
            <span className="block text-[11px] text-slate-500 dark:text-slate-400">
              {team.roster.length} players · sortable table
            </span>
          </span>
          <span className="text-xs font-semibold text-rr-700 dark:text-rr-300">
            {rosterOpen ? "Hide" : "Show"}
          </span>
        </button>
        {rosterOpen ? (
          <>
            <DataTable
              columns={rosterColumns}
              rows={sortedRoster}
              sort={rosterSort}
              onSort={onRosterSort}
              rowKey={(row) => `roster-${row.player_id}`}
              rowClassName={(row) => (team.xi.some((pick) => pick.player_id === row.player_id) ? "bg-rr-50/60 dark:bg-rr-500/[0.07]" : undefined)}
              caption={`${team.name} full roster`}
            />
          </>
        ) : null}
      </section>

      <p className="text-[11px] leading-relaxed text-slate-400 dark:text-slate-500">
        Without a saved XI, the XI is the data-driven best selection: highest source scores that
        satisfy one wicketkeeper, five batting and four bowling options, and four overseas players
        maximum. Signed-in scouts can replace any slot with its best fit, reorder the XI and save;
        Reset returns to the data-driven selection. Recent form is displayed for context only — it
        does not alter the supplied source score.
      </p>
    </div>
  );
}
