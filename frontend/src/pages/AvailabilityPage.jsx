import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, downloadStatusExport } from "../api";
import { useAuth } from "../auth";
import { PlayerAvatar, StatusPill } from "../components/Badges";
import CurrentTeamEditor from "../components/CurrentTeamEditor";
import DataTable from "../components/DataTable";
import Modal from "../components/Modal";
import SaveIndicator from "../components/SaveIndicator";
import { EmptyState, ErrorNote, LoadingBlock } from "../components/States";
import {
  IPL_TEAMS,
  NO_TEAM,
  RELEASED_TEAM,
  suggestedStatusForTeam,
  teamTypeFor,
} from "../teams";
import {
  compareValues,
  cx,
  fmtInt,
  isNumber,
  normaliseName,
  STATUS_META,
  STATUS_ORDER,
  statusMeta,
} from "../utils";

const KEEP = "__keep__";
const OTHER = "__other__";

function formatTeamValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function buildRankedRows(batterRows, bowlerRows, explicit) {
  const byName = new Map();
  for (const row of [...batterRows, ...bowlerRows]) {
    const name = String(row.name ?? "").trim();
    if (!name) continue;
    let entry = byName.get(name);
    if (!entry) {
      entry = {
        name,
        roles: [],
        teams: new Set(),
        dataTeam: row.latest_IPL_team || row.latest_team || null,
        rank: null,
        rankRole: null,
        refs: [],
        iplPlayed: row.IPL_PLAYED,
        played2026: row.PLAYED_2026_IPL,
        status: row.status,
        current_team: null,
        current_team_type: null,
        note: row.note ?? "",
        rr_fit: row.rr_fit ?? "",
      };
      byName.set(name, entry);
    }
    entry.roles.push(row.player_type);
    if (row.team_label) entry.teams.add(row.team_label);
    if (!entry.dataTeam) entry.dataTeam = row.latest_IPL_team || row.latest_team || null;
    if (isNumber(row.rank) && (entry.rank === null || row.rank < entry.rank)) {
      entry.rank = row.rank;
      entry.rankRole = row.player_type;
    }
    entry.refs.push({ role: row.player_type, id: row.player_id });
  }

  return [...byName.values()]
    .map((entry) => {
      const explicitEntry = explicit[entry.name];
      return {
        ...entry,
        team: [...entry.teams].join(" / ") || "—",
        dataTeam: entry.dataTeam,
        explicit: Boolean(explicitEntry),
        status: explicitEntry?.status ?? entry.status,
        current_team: explicitEntry?.current_team ?? null,
        current_team_type: explicitEntry?.current_team_type ?? null,
        note: explicitEntry?.note ?? entry.note ?? "",
        rr_fit: explicitEntry?.rr_fit ?? entry.rr_fit ?? "",
      };
    })
    .sort((a, b) => compareValues(a.rank, b.rank) || a.name.localeCompare(b.name));
}

function EditDialog({ target, allowedStatuses, onClose, onSaved }) {
  const [form, setForm] = useState({
    status: target?.status ?? "unknown",
    note: target?.note ?? "",
    rr_fit: target?.rr_fit ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [saveState, setSaveState] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setForm({
      status: target?.status ?? "unknown",
      note: target?.note ?? "",
      rr_fit: target?.rr_fit ?? "",
    });
    setError(null);
  }, [target]);

  const statuses = allowedStatuses?.length ? allowedStatuses : STATUS_ORDER;

  const save = async () => {
    setSaving(true);
    setSaveState("saving");
    setError(null);
    try {
      await api.updateStatus({
        name: target.name,
        status: form.status,
        note: form.note,
        rr_fit: form.rr_fit,
      });
      await onSaved?.(target.name);
      setSaveState("saved");
      onClose?.();
    } catch (err) {
      setSaveState("error");
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={Boolean(target)}
      title={target?.name ?? "Edit status"}
      subtitle={
        target?.roles?.length
          ? `${target.roles.map((role) => (role === "batter" ? "Batter" : "Bowler")).join(" + ")} · ${target.team ?? "—"}${isNumber(target.rank) ? ` · raw rank ${target.rank}` : ""}`
          : "Not in the ranked player data — stored by name"
      }
      onClose={onClose}
      footer={
        <>
          <SaveIndicator state={saveState} className="mr-auto" />
          <button type="button" className="btn-ghost" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="button" className="btn-primary" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save status"}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div>
          <label htmlFor="availability-status" className="label">
            Availability status
          </label>
          <select
            id="availability-status"
            className="select mt-1"
            value={form.status}
            onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))}
          >
            {statuses.map((status) => (
              <option key={status} value={status}>
                {statusMeta(status).label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
            {statusMeta(form.status).description}
          </p>
        </div>

        <div>
          <label htmlFor="availability-note" className="label">
            Availability note
          </label>
          <textarea
            id="availability-note"
            rows={2}
            className="input mt-1 resize-y"
            value={form.note}
            onChange={(event) => setForm((current) => ({ ...current, note: event.target.value }))}
            placeholder="e.g. Reported auction entry; unverified"
          />
        </div>

        <div>
          <label htmlFor="availability-fit" className="label">
            RR fit note
          </label>
          <textarea
            id="availability-fit"
            rows={3}
            className="input mt-1 resize-y"
            value={form.rr_fit}
            onChange={(event) => setForm((current) => ({ ...current, rr_fit: event.target.value }))}
            placeholder="e.g. Powerplay enforcer; fits RR top order"
          />
        </div>

        {error ? (
          <p role="alert" className="rounded-lg bg-red-50 p-2 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
            {error}
          </p>
        ) : null}

        <p className="text-[10px] leading-relaxed text-slate-400 dark:text-slate-500">
          Saves to the backend SQLite database. The API is the single source of truth and the
          availability workspace re-reads it after each save.
        </p>
      </div>
    </Modal>
  );
}

export default function AvailabilityPage() {
  const { authenticated, openLogin } = useAuth();
  const [state, setState] = useState({
    loading: true,
    error: null,
    rows: [],
    manual: [],
    allowed: STATUS_ORDER,
    explicitMap: {},
    dataTeams: [],
    typedTeams: [],
  });
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [currentTeamUnset, setCurrentTeamUnset] = useState(false);
  const [savingNames, setSavingNames] = useState(() => new Set());
  const [saveFeedback, setSaveFeedback] = useState({});
  const [selected, setSelected] = useState(() => new Set());
  const [editing, setEditing] = useState(null);
  const [toast, setToast] = useState(null);

  const [addQuery, setAddQuery] = useState("");
  const [addResults, setAddResults] = useState([]);
  const [addBusy, setAddBusy] = useState(false);

  const [bulkTeam, setBulkTeam] = useState(KEEP);
  const [bulkOther, setBulkOther] = useState("");
  const [bulkStatus, setBulkStatus] = useState(KEEP);
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const [bulkSaving, setBulkSaving] = useState(false);
  const [bulkError, setBulkError] = useState(null);
  const [undoConfirmOpen, setUndoConfirmOpen] = useState(false);
  const [undoSaving, setUndoSaving] = useState(false);
  const [undoError, setUndoError] = useState(null);

  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const [importFileName, setImportFileName] = useState("");
  const [importPreview, setImportPreview] = useState(null);
  const [importBusy, setImportBusy] = useState(false);
  const [importError, setImportError] = useState(null);
  const fileInputRef = useRef(null);

  const load = useCallback(({ silent = false } = {}) => {
    if (!silent) {
      setState((current) => ({ ...current, loading: true, error: null }));
    }
    return Promise.all([
      api.status(),
      api.players({ role: "batter", availableOnly: false }),
      api.players({ role: "bowler", availableOnly: false }),
    ])
      .then(([statusData, batters, bowlers]) => {
        const explicitMap = statusData.players ?? {};
        const rows = buildRankedRows(batters.players, bowlers.players, explicitMap);
        const rankedNames = new Set(rows.map((row) => row.name));
        const manual = Object.entries(explicitMap)
          .filter(([name]) => !rankedNames.has(name))
          .map(([name, entry]) => ({
            name,
            roles: [],
            team: "—",
            dataTeam: null,
            rank: null,
            explicit: true,
            status: entry.status,
            current_team: entry.current_team ?? null,
            current_team_type: entry.current_team_type ?? null,
            note: entry.note ?? "",
            rr_fit: entry.rr_fit ?? "",
          }))
          .sort((a, b) => a.name.localeCompare(b.name));
        setState({
          loading: false,
          error: null,
          rows,
          manual,
          allowed: statusData.allowed_statuses ?? STATUS_ORDER,
          explicitMap,
          dataTeams: statusData.data_teams ?? [],
          typedTeams: statusData.typed_teams ?? [],
        });
      })
      .catch((error) => {
        setState((current) => ({ ...current, loading: false, error: error.message }));
      });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    const query = addQuery.trim();
    if (query.length < 2) {
      setAddResults([]);
      setAddBusy(false);
      return undefined;
    }
    let cancelled = false;
    setAddBusy(true);
    const timer = window.setTimeout(() => {
      api
        .search(query)
        .then((payload) => {
          if (!cancelled) setAddResults(payload.results ?? []);
        })
        .catch(() => {
          if (!cancelled) setAddResults([]);
        })
        .finally(() => {
          if (!cancelled) setAddBusy(false);
        });
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [addQuery]);

  const counts = useMemo(() => {
    const base = { retained: 0, rr_own: 0, pool: 0, unknown: 0, no_ipl: 0 };
    for (const row of state.rows) {
      base[row.status] = (base[row.status] ?? 0) + 1;
    }
    return base;
  }, [state.rows]);

  const filtered = useMemo(() => {
    const query = normaliseName(search);
    return state.rows.filter((row) => {
      if (statusFilter && row.status !== statusFilter) return false;
      if (currentTeamUnset && row.current_team) return false;
      if (query) {
        const haystack = `${normaliseName(row.name)} ${normaliseName(row.team)} ${normaliseName(row.current_team ?? "")} ${row.roles.join(" ")}`;
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
  }, [state.rows, search, statusFilter, currentTeamUnset]);

  const selectedRows = useMemo(
    () => state.rows.filter((row) => selected.has(row.name)),
    [state.rows, selected],
  );
  const visibleKeys = useMemo(() => filtered.map((row) => row.name), [filtered]);
  const allSelected =
    visibleKeys.length > 0 && visibleKeys.every((name) => selected.has(name));
  const someSelected = visibleKeys.some((name) => selected.has(name));

  const progress = useMemo(() => {
    const total = state.rows.length;
    const set = state.rows.filter((row) => row.current_team).length;
    const shortlistNames = new Set();
    for (const role of ["batter", "bowler"]) {
      state.rows
        .filter(
          (row) =>
            row.roles.includes(role) &&
            ["pool", "unknown"].includes(row.status) &&
            isNumber(row.rank),
        )
        .sort((a, b) => a.rank - b.rank)
        .slice(0, 10)
        .forEach((row) => shortlistNames.add(row.name));
    }
    const shortlistSet = state.rows.filter(
      (row) => shortlistNames.has(row.name) && row.current_team,
    ).length;
    return {
      total,
      set,
      shortlist: shortlistNames.size,
      shortlistSet,
    };
  }, [state.rows]);

  const bulkTeamValue =
    bulkTeam === OTHER ? bulkOther.trim() : bulkTeam === KEEP ? KEEP : bulkTeam;
  const bulkTeamChanging = bulkTeam !== KEEP;
  const bulkStatusChanging = bulkStatus !== KEEP;
  const bulkSuggestion =
    bulkTeamChanging && bulkTeamValue && bulkTeamValue !== KEEP
      ? suggestedStatusForTeam(bulkTeamValue)
      : null;

  const bulkChangeCount = useMemo(() => {
    if (selectedRows.length === 0) return 0;
    const desiredTeam = bulkTeamChanging ? bulkTeamValue || null : undefined;
    return selectedRows.filter((row) => {
      const teamDiff =
        bulkTeamChanging && (row.current_team ?? null) !== desiredTeam;
      const statusDiff = bulkStatusChanging && row.status !== bulkStatus;
      return teamDiff || statusDiff;
    }).length;
  }, [selectedRows, bulkTeamChanging, bulkTeamValue, bulkStatusChanging, bulkStatus]);

  const patchRow = (name, patch) => {
    setState((current) => ({
      ...current,
      rows: current.rows.map((row) => (row.name === name ? { ...row, ...patch } : row)),
    }));
  };

  const changeStatus = async (row, nextStatus) => {
    if (nextStatus === row.status) return;
    const previous = row.status;
    patchRow(row.name, { status: nextStatus, explicit: true });
    setSavingNames((current) => new Set(current).add(row.name));
    setSaveFeedback((current) => ({ ...current, [row.name]: "saving" }));
    try {
      await api.updateStatus({ name: row.name, status: nextStatus });
      await load({ silent: true });
      setSaveFeedback((current) => ({ ...current, [row.name]: "saved" }));
      setToast({ type: "ok", text: `${row.name} → ${statusMeta(nextStatus).label}. Clean ranks update on the next request.` });
    } catch (error) {
      patchRow(row.name, { status: previous });
      setSaveFeedback((current) => ({ ...current, [row.name]: "error" }));
      setToast({ type: "error", text: error.message });
    } finally {
      setSavingNames((current) => {
        const next = new Set(current);
        next.delete(row.name);
        return next;
      });
    }
  };

  const openEditorForResult = (result) => {
    const existing = state.rows.find((row) => row.name === result.name);
    if (existing) {
      setEditing(existing);
    } else {
      const explicitEntry = state.explicitMap[result.name];
      setEditing({
        name: result.name,
        roles: result.ranked_role ? [result.ranked_role] : result.role ? [result.role] : [],
        team: result.latest_team ?? "—",
        dataTeam: result.latest_team ?? null,
        rank: result.ranked_rank,
        status: explicitEntry?.status ?? "unknown",
        current_team: explicitEntry?.current_team ?? null,
        current_team_type: explicitEntry?.current_team_type ?? null,
        note: explicitEntry?.note ?? "",
        rr_fit: explicitEntry?.rr_fit ?? "",
      });
    }
    setAddQuery("");
    setAddResults([]);
  };

  const toggleSelected = (name, checked) => {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(name);
      else next.delete(name);
      return next;
    });
  };

  const toggleAllSelected = (checked) => {
    setSelected((current) => {
      const next = new Set(current);
      for (const name of visibleKeys) {
        if (checked) next.add(name);
        else next.delete(name);
      }
      return next;
    });
  };

  const resetBulk = () => {
    setBulkTeam(KEEP);
    setBulkOther("");
    setBulkStatus(KEEP);
    setBulkError(null);
  };

  const applyBulk = async () => {
    if (!bulkTeamChanging && !bulkStatusChanging) return;
    if (bulkTeam === OTHER && !bulkOther.trim()) {
      setBulkError("Enter the other team name.");
      return;
    }
    setBulkSaving(true);
    setBulkError(null);
    const payload = { names: [...selected] };
    if (bulkTeamChanging) {
      payload.current_team = bulkTeamValue || null;
      payload.current_team_type = teamTypeFor(payload.current_team);
    }
    if (bulkStatusChanging) payload.status = bulkStatus;
    try {
      const result = await api.bulkStatus(payload);
      await load({ silent: true });
      setToast({
        type: "ok",
        text: `${result.summary}. Clean ranks update on the next request.`,
      });
      setSelected(new Set());
      setBulkConfirmOpen(false);
      resetBulk();
    } catch (error) {
      setBulkError(error.message);
    } finally {
      setBulkSaving(false);
    }
  };

  const undoSelected = async () => {
    if (!authenticated) {
      openLogin();
      return;
    }
    setUndoSaving(true);
    setUndoError(null);
    try {
      const result = await api.undoBulk([...selected]);
      await load({ silent: true });
      const skipped = result.skipped ?? [];
      const skippedNames = skipped.length
        ? ` No history for: ${skipped.slice(0, 3).join(", ")}${skipped.length > 3 ? ", …" : ""}.`
        : "";
      setToast({
        type: skipped.length ? "error" : "ok",
        text: `${result.summary}.${skippedNames}`,
      });
      setSelected(new Set());
      setUndoConfirmOpen(false);
      resetBulk();
    } catch (error) {
      setUndoError(error.message);
    } finally {
      setUndoSaving(false);
    }
  };

  const exportStatus = async (format) => {
    if (!authenticated) {
      openLogin();
      return;
    }
    try {
      await downloadStatusExport(format);
    } catch (error) {
      setToast({ type: "error", text: error.message });
    }
  };

  const openImport = () => {
    if (!authenticated) {
      openLogin();
      return;
    }
    setImportOpen(true);
    setImportText("");
    setImportFileName("");
    setImportPreview(null);
    setImportError(null);
  };

  const onImportFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setImportFileName(file.name);
    setImportPreview(null);
    setImportError(null);
    try {
      setImportText(await file.text());
    } catch {
      setImportError("Could not read that file.");
    }
  };

  const importPayload = (dryRun) => {
    const text = importText.trim();
    if (!text) throw new Error("Choose a JSON or CSV file, or paste its contents.");
    if (text.startsWith("{") || text.startsWith("[")) {
      let parsed;
      try {
        parsed = JSON.parse(text);
      } catch {
        throw new Error("That file is not valid JSON.");
      }
      const players = Array.isArray(parsed) ? parsed : parsed.players ?? parsed;
      return { players, dry_run: dryRun };
    }
    return { csv: text, dry_run: dryRun };
  };

  const previewImport = async () => {
    setImportBusy(true);
    setImportError(null);
    try {
      const result = await api.importStatus(importPayload(true));
      setImportPreview(result);
    } catch (error) {
      setImportError(error.message);
      setImportPreview(null);
    } finally {
      setImportBusy(false);
    }
  };

  const applyImport = async () => {
    setImportBusy(true);
    setImportError(null);
    try {
      const result = await api.importStatus(importPayload(false));
      await load({ silent: true });
      setImportOpen(false);
      setImportPreview(null);
      setToast({ type: "ok", text: `${result.summary}.` });
    } catch (error) {
      setImportError(error.message);
    } finally {
      setImportBusy(false);
    }
  };

  const columns = [
    {
      key: "player",
      label: "Player",
      sortable: false,
      cell: (row) => (
        <div className="flex items-center gap-2.5">
          <PlayerAvatar name={row.name} role={row.roles[0] ?? "batter"} size="sm" />
          <div className="min-w-0">
            <p className="truncate font-semibold text-slate-900 dark:text-white">{row.name}</p>
            <p className="flex items-center gap-1 truncate text-[10px] text-slate-500 dark:text-slate-400">
              {row.roles.length
                ? row.roles.map((role) => (role === "batter" ? "Batter" : "Bowler")).join(" + ")
                : "Unranked"}
              {!row.explicit ? " · default status" : ""}
            </p>
          </div>
        </div>
      ),
    },
    {
      key: "team",
      label: "Team (data)",
      sortable: false,
      cell: (row) => (
        <span className="text-xs text-slate-600 dark:text-slate-300">{row.team}</span>
      ),
      headerClassName: "hidden md:table-cell",
      cellClassName: "hidden md:table-cell",
    },
    {
      key: "rank",
      label: "Raw rank",
      sortable: false,
      align: "center",
      cell: (row) => (
        <span className="num text-xs font-semibold">{isNumber(row.rank) ? fmtInt(row.rank) : "—"}</span>
      ),
      headerClassName: "hidden sm:table-cell",
      cellClassName: "hidden sm:table-cell",
    },
    {
      key: "ipl",
      label: "IPL",
      sortable: false,
      align: "center",
      cell: (row) => (
        <span
          className={cx(
            "text-[11px] font-semibold",
            String(row.iplPlayed).toUpperCase() === "Y"
              ? "text-emerald-700 dark:text-emerald-400"
              : "text-slate-500 dark:text-slate-400",
          )}
        >
          {String(row.iplPlayed ?? "—").toUpperCase()}
        </span>
      ),
      headerClassName: "hidden lg:table-cell",
      cellClassName: "hidden lg:table-cell",
    },
    {
      key: "currentTeam",
      label: "Current team",
      sortable: false,
      cell: (row) => (
        <CurrentTeamEditor
          name={row.name}
          currentTeam={row.current_team}
          currentTeamType={row.current_team_type}
          dataTeam={row.dataTeam}
          dataTeams={state.dataTeams}
          typedTeams={state.typedTeams}
          status={row.status}
          onChanged={() => load({ silent: true })}
        />
      ),
    },
    {
      key: "status",
      label: "Status",
      sortable: false,
      cell: (row) => {
        const saving = savingNames.has(row.name);
        return (
          <div className="flex items-center gap-2">
            <select
              aria-label={`Availability status for ${row.name}`}
              className="select h-8 w-[9.5rem] py-1 text-xs"
              value={row.status}
              disabled={saving}
              onChange={(event) => changeStatus(row, event.target.value)}
            >
              {state.allowed.map((status) => (
                <option key={status} value={status}>
                  {statusMeta(status).label}
                </option>
              ))}
            </select>
            {saving ? (
              <span
                className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-rr-500 border-t-transparent"
                aria-label="Saving"
              />
            ) : (
              <StatusPill status={row.status} className="hidden xl:inline-flex" />
            )}
            <SaveIndicator state={saveFeedback[row.name]} className="hidden 2xl:inline-flex" />
          </div>
        );
      },
    },
    {
      key: "note",
      label: "Note",
      sortable: false,
      cell: (row) => (
        <span
          className="block max-w-[14rem] truncate text-[11px] text-slate-500 dark:text-slate-400"
          title={row.note || undefined}
        >
          {row.note || "—"}
        </span>
      ),
      headerClassName: "hidden xl:table-cell",
      cellClassName: "hidden xl:table-cell",
    },
    {
      key: "actions",
      label: "",
      sortable: false,
      align: "right",
      cell: (row) => (
        <div className="flex items-center justify-end gap-2">
          {row.refs?.[0] ? (
            <Link
              to={`/player/${row.refs[0].role}/${row.refs[0].id}`}
              className="text-[11px] font-medium text-slate-500 hover:text-rr-700 dark:text-slate-400 dark:hover:text-rr-300"
            >
              Profile
            </Link>
          ) : null}
          <button
            type="button"
            className="btn-ghost h-8 px-2.5 py-1 text-xs"
            onClick={() => setEditing(row)}
          >
            Edit
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="label">Working file</p>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-900 sm:text-3xl dark:text-white">
            Availability workspace
          </h1>
          <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">
            Every status is stored in the backend SQLite database, keyed by player name. Pool and
            unknown count as available; retained, RR-owned and no-IPL are removed before clean
            ranking. Changes save through the API immediately and the page re-reads them.
          </p>
        </div>
        <div className="flex flex-wrap items-start gap-2">
          <button type="button" className="btn-ghost" onClick={() => exportStatus("json")}>
            Export backup
          </button>
          <button type="button" className="btn-ghost" onClick={() => exportStatus("csv")}>
            Export CSV
          </button>
          <button type="button" className="btn-ghost" onClick={openImport}>
            Import backup
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {STATUS_ORDER.map((status) => (
            <span
              key={status}
              className={cx(
                "flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs dark:border-slate-800 dark:bg-slate-900",
                statusFilter === status && "ring-2 ring-rr-500/40",
              )}
            >
              <button
                type="button"
                onClick={() => setStatusFilter(statusFilter === status ? "" : status)}
                className="flex items-center gap-1.5"
                title={`Filter by ${statusMeta(status).label}`}
              >
                <span className={cx("h-2 w-2 rounded-full", statusMeta(status).dot)} />
                <span className="font-medium text-slate-600 dark:text-slate-300">
                  {statusMeta(status).short}
                </span>
              </button>
              <span className="num font-bold text-slate-900 dark:text-white">{counts[status] ?? 0}</span>
            </span>
          ))}
        </div>
      </header>

      {toast ? (
        <div
          role="status"
          className={cx(
            "card flex items-center justify-between gap-3 p-3 text-sm",
            toast.type === "ok"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-200"
              : "border-red-200 bg-red-50 text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200",
          )}
        >
          <span>{toast.text}</span>
          <button type="button" onClick={() => setToast(null)} className="text-xs font-semibold underline">
            Dismiss
          </button>
        </div>
      ) : null}

      {state.error ? <ErrorNote message={state.error} onRetry={load} /> : null}

      <section className="card p-4" aria-label="Availability filters and search">
        <div className="grid gap-3 lg:grid-cols-12">
          <div className="lg:col-span-3">
            <label htmlFor="availability-search" className="label">
              Filter ranked players
            </label>
            <input
              id="availability-search"
              type="search"
              className="input mt-1"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Name, team or role"
            />
          </div>
          <div className="lg:col-span-2">
            <label htmlFor="availability-status-filter" className="label">
              Status
            </label>
            <select
              id="availability-status-filter"
              className="select mt-1"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="">All statuses</option>
              {STATUS_ORDER.map((status) => (
                <option key={status} value={status}>
                  {statusMeta(status).label}
                </option>
              ))}
            </select>
          </div>
          <div className="lg:col-span-3">
            <label htmlFor="availability-add" className="label">
              Set status by name (all indexed players)
            </label>
            <div className="relative mt-1">
              <input
                id="availability-add"
                type="search"
                className="input"
                value={addQuery}
                onChange={(event) => setAddQuery(event.target.value)}
                placeholder="Search any player, e.g. Finn Allen"
                autoComplete="off"
              />
              {addBusy ? (
                <span
                  className="absolute inset-y-0 right-3 my-auto h-4 w-4 animate-spin rounded-full border-2 border-rr-500 border-t-transparent"
                  aria-label="Searching"
                />
              ) : null}
              {addQuery.trim().length >= 2 && addResults.length > 0 ? (
                <ul className="absolute z-30 mt-1 max-h-72 w-full overflow-y-auto rounded-xl border border-slate-200 bg-white p-1 shadow-lg dark:border-slate-700 dark:bg-slate-900">
                  {addResults.map((result) => (
                    <li key={`${result.role}-${result.player_id}`}>
                      <button
                        type="button"
                        onClick={() => openEditorForResult(result)}
                        className="flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        <span className="min-w-0">
                          <span className="block truncate font-medium text-slate-900 dark:text-white">
                            {result.name}
                          </span>
                          <span className="block truncate text-[10px] text-slate-500 dark:text-slate-400">
                            {(result.role || "unknown").toString()} · {result.latest_team || "team unknown"}
                          </span>
                        </span>
                        <span className="num shrink-0 text-[10px] text-slate-400">
                          {result.ranked ? `rank ${result.ranked_rank}` : "unranked"}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
            <p className="mt-1 text-[10px] text-slate-400 dark:text-slate-500">
              Search covers every player in the derived index, ranked or not.
            </p>
          </div>
          <div className="flex items-end lg:col-span-4">
            <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 dark:border-slate-800 dark:text-slate-300">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 text-rr-600 focus:ring-rr-500 dark:border-slate-600 dark:bg-slate-800"
                checked={currentTeamUnset}
                onChange={(event) => setCurrentTeamUnset(event.target.checked)}
              />
              Current team not set
              <span className="num text-[10px] text-slate-400">
                {progress.total - progress.set}
              </span>
            </label>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3 text-[11px] text-slate-500 dark:border-slate-800 dark:text-slate-400">
          <span>
            Showing <strong className="num text-slate-700 dark:text-slate-200">{filtered.length}</strong> of{" "}
            <span className="num">{state.rows.length}</span> ranked players
            {state.manual.length ? ` · ${state.manual.length} manual entries` : ""}
          </span>
          <span>
            Current team set:{" "}
            <strong className="num text-slate-700 dark:text-slate-200">
              {progress.shortlistSet}
            </strong>{" "}
            of <span className="num">{progress.shortlist}</span> shortlist players ·{" "}
            <strong className="num text-slate-700 dark:text-slate-200">{progress.set}</strong> of{" "}
            <span className="num">{progress.total}</span> ranked players
          </span>
          <button
            type="button"
            className="font-semibold text-rr-700 hover:underline dark:text-rr-300"
            onClick={() => load({ silent: true })}
          >
            Refresh from disk
          </button>
        </div>
      </section>

      {selected.size > 0 ? (
        <section
          className="card sticky top-2 z-20 p-3"
          aria-label="Bulk current team and status edit"
        >
          <div className="flex flex-wrap items-end gap-2">
            <div>
              <p className="text-xs font-bold text-slate-900 dark:text-white">
                {selected.size} selected
              </p>
              <p className="text-[10px] text-slate-500 dark:text-slate-400">
                {bulkChangeCount} of {selectedRows.length} rows would change
              </p>
            </div>
            <div className="min-w-[12rem]">
              <label htmlFor="bulk-current-team" className="label">
                Current team
              </label>
              <select
                id="bulk-current-team"
                className="select mt-1 h-9 py-1 text-xs"
                value={bulkTeam}
                onChange={(event) => {
                  setBulkTeam(event.target.value);
                  setBulkError(null);
                }}
              >
                <option value={KEEP}>Keep current team</option>
                <option value="">Clear current team</option>
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
                <option value={OTHER}>Other team…</option>
              </select>
            </div>
            {bulkTeam === OTHER ? (
              <div className="min-w-[12rem]">
                <label htmlFor="bulk-other-team" className="label">
                  Other team name
                </label>
                <input
                  id="bulk-other-team"
                  className="input mt-1 h-9 py-1 text-xs"
                  value={bulkOther}
                  list="bulk-team-suggestions"
                  onChange={(event) => setBulkOther(event.target.value)}
                  placeholder="e.g. Surrey"
                />
                <datalist id="bulk-team-suggestions">
                  {[...state.dataTeams, ...state.typedTeams].map((team) => (
                    <option key={team} value={team} />
                  ))}
                </datalist>
              </div>
            ) : null}
            <div className="min-w-[11rem]">
              <label htmlFor="bulk-status" className="label">
                Availability status
              </label>
              <select
                id="bulk-status"
                className="select mt-1 h-9 py-1 text-xs"
                value={bulkStatus}
                onChange={(event) => setBulkStatus(event.target.value)}
              >
                <option value={KEEP}>Keep current status</option>
                {STATUS_ORDER.map((status) => (
                  <option key={status} value={status}>
                    {statusMeta(status).label}
                  </option>
                ))}
              </select>
            </div>
            {bulkSuggestion && bulkStatus === KEEP ? (
              <button
                type="button"
                className="btn-ghost h-9 text-[11px]"
                onClick={() => setBulkStatus(bulkSuggestion)}
              >
                Suggest: {statusMeta(bulkSuggestion).label}
              </button>
            ) : null}
            <div className="ml-auto flex items-center gap-2">
              <button type="button" className="btn-ghost" onClick={() => setSelected(new Set())}>
                Clear selection
              </button>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  if (!authenticated) {
                    openLogin();
                    return;
                  }
                  setUndoError(null);
                  setUndoConfirmOpen(true);
                }}
              >
                Undo last change
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={!bulkTeamChanging && !bulkStatusChanging}
                onClick={() => {
                  setBulkError(null);
                  setBulkConfirmOpen(true);
                }}
              >
                Apply to {selected.size} selected
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
        <section className="card overflow-hidden" aria-label="Availability editor">
          <DataTable
            columns={columns}
            rows={filtered}
            rowKey={(row) => row.name}
            rowClassName={(row) =>
              !["pool", "unknown"].includes(row.status) ? "opacity-75" : undefined
            }
            selection={{
              selected,
              allSelected,
              someSelected,
              onToggle: toggleSelected,
              onToggleAll: toggleAllSelected,
            }}
            empty={
              <EmptyState
                className="border-0"
                title="No ranked players match"
                hint="Clear the filter or search for a name above to set a manual status."
              />
            }
            caption="Ranked players with editable availability status"
          />
        </section>
      )}

      {state.manual.length > 0 ? (
        <section className="card p-5">
          <h2 className="text-sm font-bold text-slate-900 dark:text-white">
            Manual entries outside the rankings
          </h2>
          <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
            These names have an explicit status but no row in the ranked player data. They persist
            by name and become active if the player is later ranked.
          </p>
          <ul className="mt-3 divide-y divide-slate-100 dark:divide-slate-800/70">
            {state.manual.map((row) => (
              <li key={row.name} className="flex flex-wrap items-center gap-3 py-2.5">
                <span className="flex-1 text-sm font-medium text-slate-900 dark:text-white">
                  {row.name}
                </span>
                <StatusPill status={row.status} />
                <CurrentTeamEditor
                  name={row.name}
                  currentTeam={row.current_team}
                  currentTeamType={row.current_team_type}
                  dataTeam={row.dataTeam}
                  dataTeams={state.dataTeams}
                  typedTeams={state.typedTeams}
                  status={row.status}
                  onChanged={() => load({ silent: true })}
                />
                <span className="max-w-[16rem] truncate text-[11px] text-slate-500 dark:text-slate-400">
                  {row.note || row.rr_fit || "—"}
                </span>
                <button
                  type="button"
                  className="btn-ghost h-8 px-2.5 py-1 text-xs"
                  onClick={() => setEditing(row)}
                >
                  Edit
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="card p-5">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">Status reference</h2>
        <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
          Without an explicit entry the default is <code>no_ipl</code> when{" "}
          <code>IPL_PLAYED = N</code>, otherwise <code>unknown</code>.
        </p>
        <dl className="mt-3 grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
          {STATUS_ORDER.map((status) => (
            <div
              key={status}
              className="rounded-xl border border-slate-200 p-3 dark:border-slate-800"
            >
              <dt className="flex items-center gap-2">
                <StatusPill status={status} />
                <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                  {status}
                </span>
              </dt>
              <dd className="mt-1.5 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
                {STATUS_META[status].description}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <Modal
        open={bulkConfirmOpen}
        title="Apply bulk edit"
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
              onClick={applyBulk}
            >
              {bulkSaving ? "Applying…" : `Change ${bulkChangeCount} players`}
            </button>
          </>
        }
      >
        <div className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
          <p>
            This writes to <code>status.json</code> and records a history entry per changed
            player. Nothing changes for rows that already match.
          </p>
          <dl className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
              <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                Current team
              </dt>
              <dd className="mt-1 text-xs font-medium text-slate-800 dark:text-slate-100">
                {bulkTeamChanging
                  ? bulkTeamValue || "Clear current team"
                  : "Keep current team"}
              </dd>
            </div>
            <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
              <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                Availability status
              </dt>
              <dd className="mt-1 text-xs font-medium text-slate-800 dark:text-slate-100">
                {bulkStatusChanging ? statusMeta(bulkStatus).label : "Keep current status"}
              </dd>
            </div>
          </dl>
          {bulkChangeCount === 0 ? (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Every selected row already matches. Pick another team or status to make a change.
            </p>
          ) : null}
          {bulkError ? (
            <p role="alert" className="text-xs text-red-700 dark:text-red-300">
              {bulkError}
            </p>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={undoConfirmOpen}
        title="Undo last change"
        subtitle={`${selected.size} selected players`}
        onClose={() => {
          if (!undoSaving) {
            setUndoConfirmOpen(false);
            setUndoError(null);
          }
        }}
        footer={
          <>
            <button
              type="button"
              className="btn-ghost"
              disabled={undoSaving}
              onClick={() => setUndoConfirmOpen(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={undoSaving || selected.size === 0}
              onClick={undoSelected}
            >
              {undoSaving ? "Undoing…" : `Undo for ${selected.size} selected`}
            </button>
          </>
        }
      >
        <div className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
          <p>
            This reverts each selected player’s most recent saved status, current-team, note, or
            RR-fit change. Players with no change history are skipped. The undone history entry
            is removed.
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {selectedRows
              .slice(0, 6)
              .map((row) => row.name)
              .join(", ")}
            {selected.size > 6 ? ` and ${selected.size - 6} more` : ""}
          </p>
          {undoError ? (
            <p role="alert" className="text-xs text-red-700 dark:text-red-300">
              {undoError}
            </p>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={importOpen}
        title="Import backup"
        subtitle="Merge players into status.json — preview first, nothing is written until you apply"
        onClose={() => {
          if (!importBusy) setImportOpen(false);
        }}
        footer={
          <>
            <button
              type="button"
              className="btn-ghost"
              disabled={importBusy}
              onClick={() => setImportOpen(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn-ghost"
              disabled={importBusy || !importText.trim()}
              onClick={previewImport}
            >
              {importBusy && !importPreview ? "Checking…" : "Preview changes"}
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={importBusy || !importPreview || importPreview.changed === 0}
              onClick={applyImport}
            >
              {importBusy && importPreview
                ? "Applying…"
                : `Apply ${importPreview?.changed ?? 0} changes`}
            </button>
          </>
        }
      >
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,.csv,text/csv,application/json"
              className="sr-only"
              onChange={onImportFile}
            />
            <button
              type="button"
              className="btn-ghost"
              onClick={() => fileInputRef.current?.click()}
            >
              Choose JSON or CSV file
            </button>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              {importFileName || "or paste below"}
            </span>
          </div>
          <div>
            <label htmlFor="import-text" className="label">
              File contents
            </label>
            <textarea
              id="import-text"
              rows={7}
              className="input mt-1 resize-y font-mono text-[11px]"
              value={importText}
              onChange={(event) => {
                setImportText(event.target.value);
                setImportPreview(null);
                setImportError(null);
              }}
              placeholder={'{"players": [{"player": "Finn Allen", "status": "pool"}]}\nor CSV: player,status,current_team,...'}
            />
          </div>
          {importError ? (
            <p
              role="alert"
              className="rounded-lg bg-red-50 p-2 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300"
            >
              {importError}
            </p>
          ) : null}
          {importPreview ? (
            <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
              <p className="text-xs font-semibold text-slate-800 dark:text-slate-100">
                {importPreview.summary}
              </p>
              {importPreview.changes.length ? (
                <ul className="mt-2 max-h-56 space-y-1.5 overflow-y-auto text-[11px]">
                  {importPreview.changes.map((entry) => (
                    <li
                      key={entry.player}
                      className="rounded-lg bg-slate-50 px-2 py-1.5 dark:bg-slate-800/60"
                    >
                      <span className="font-semibold text-slate-800 dark:text-slate-100">
                        {entry.player}
                      </span>
                      {entry.changed.map((change) => (
                        <span key={change.field} className="ml-2 text-slate-500 dark:text-slate-400">
                          {change.field}: {formatTeamValue(change.old)} →{" "}
                          <strong className="text-slate-700 dark:text-slate-200">
                            {formatTeamValue(change.new)}
                          </strong>
                        </span>
                      ))}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                  No differences from the current file.
                </p>
              )}
            </div>
          ) : null}
        </div>
      </Modal>

      <EditDialog
        target={editing}
        allowedStatuses={state.allowed}
        onClose={() => setEditing(null)}
        onSaved={async (name) => {
          await load({ silent: true });
          setToast({ type: "ok", text: `Saved availability for ${name}.` });
        }}
      />
    </div>
  );
}
