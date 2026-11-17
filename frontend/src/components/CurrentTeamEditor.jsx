import { useEffect, useId, useMemo, useState } from "react";
import { api } from "../api";
import {
  IPL_TEAMS,
  NO_TEAM,
  RELEASED_TEAM,
  SPECIAL_CURRENT_TEAMS,
  suggestedStatusForTeam,
  teamTypeFor,
} from "../teams";
import { cx, statusMeta } from "../utils";
import Modal from "./Modal";
import SaveIndicator from "./SaveIndicator";

const OTHER = "__other__";

function entryValue(value) {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function ChangeList({ entries }) {
  const last = entries.slice(-5).reverse();
  if (last.length === 0) {
    return (
      <p className="text-[11px] text-slate-400 dark:text-slate-500">
        No recorded changes yet.
      </p>
    );
  }
  return (
    <ol className="space-y-2">
      {last.map((entry, index) => (
        <li
          key={`${entry.timestamp}-${index}`}
          className="rounded-lg border border-slate-200 p-2 text-[10px] leading-relaxed dark:border-slate-800"
        >
          <p className="font-semibold text-slate-500 dark:text-slate-400">
            {entry.timestamp || "unknown time"}
          </p>
          {entry.changes.map((change, changeIndex) => (
            <p key={`${change.field}-${changeIndex}`} className="text-slate-600 dark:text-slate-300">
              <span className="font-semibold">{change.field.replaceAll("_", " ")}</span>:{" "}
              <span className="text-slate-400 dark:text-slate-500">{entryValue(change.old)}</span>
              {" → "}
              <span>{entryValue(change.new)}</span>
            </p>
          ))}
        </li>
      ))}
    </ol>
  );
}

export function CurrentTeamChip({
  currentTeam,
  currentTeamType,
  dataTeam,
  onClick,
  className,
}) {
  const manual = currentTeam !== null && currentTeam !== undefined;
  const label = manual ? currentTeam : dataTeam || "Set current team";
  const special = SPECIAL_CURRENT_TEAMS.includes(label);
  return (
    <button
      type="button"
      onClick={onClick}
      title={
        manual
          ? `Current team set manually: ${currentTeam}. Click to edit.`
          : dataTeam
            ? `Latest team from data (unverified): ${dataTeam}. Click to confirm or change.`
            : "Set a current team"
      }
      className={cx(
        "inline-flex max-w-[13rem] items-center gap-1.5 rounded-full px-2 py-0.5 text-left text-[11px] font-semibold ring-1 ring-inset transition-colors",
        manual
          ? special
            ? "bg-slate-100 text-slate-700 ring-slate-400/30 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-600/40"
            : currentTeamType === "other"
              ? "bg-sky-50 text-sky-800 ring-sky-500/30 hover:bg-sky-100 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-400/30"
              : "bg-rr-50 text-rr-800 ring-rr-500/30 hover:bg-rr-100 dark:bg-rr-500/10 dark:text-rr-300 dark:ring-rr-400/30"
          : "border border-dashed border-slate-300 bg-transparent text-slate-500 hover:border-rr-400 hover:text-rr-700 dark:border-slate-600 dark:text-slate-400 dark:hover:border-rr-500 dark:hover:text-rr-300",
        className,
      )}
    >
      <span className="truncate">{label}</span>
      {manual ? null : dataTeam ? (
        <span className="shrink-0 rounded bg-slate-200/80 px-1 text-[9px] font-bold uppercase tracking-wide text-slate-500 dark:bg-slate-800 dark:text-slate-400">
          data
        </span>
      ) : (
        <span className="shrink-0 text-[10px] font-bold uppercase tracking-wide">set</span>
      )}
    </button>
  );
}

export default function CurrentTeamEditor({
  name,
  currentTeam = null,
  currentTeamType = null,
  dataTeam = null,
  dataTeams = [],
  typedTeams = [],
  status,
  onChanged,
  className,
  subtle = false,
}) {
  const [open, setOpen] = useState(false);
  const [teamValue, setTeamValue] = useState("");
  const [otherText, setOtherText] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveState, setSaveState] = useState(null);
  const [error, setError] = useState(null);
  const [suggestion, setSuggestion] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyError, setHistoryError] = useState(null);
  const [undoing, setUndoing] = useState(false);
  const listId = useId();

  const isOther =
    currentTeamType === "other" &&
    currentTeam &&
    !IPL_TEAMS.includes(currentTeam) &&
    !SPECIAL_CURRENT_TEAMS.includes(currentTeam);

  useEffect(() => {
    if (!open) return;
    setTeamValue(isOther ? OTHER : currentTeam ?? "");
    setOtherText(isOther ? currentTeam : "");
    setError(null);
    setSuggestion(null);
    setHistory([]);
    setHistoryError(null);
    let cancelled = false;
    api
      .history(name)
      .then((payload) => {
        if (!cancelled) setHistory(payload.entries ?? []);
      })
      .catch((err) => {
        if (!cancelled) setHistoryError(err.message);
      });
    return () => {
      cancelled = true;
    };
    // Reset only when the dialog opens; a parent refresh after saving must not
    // erase the pending status suggestion.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, name]);

  const autocomplete = useMemo(() => {
    const values = new Set([
      ...dataTeams,
      ...typedTeams,
      ...IPL_TEAMS,
      ...SPECIAL_CURRENT_TEAMS,
    ]);
    if (currentTeam) values.add(currentTeam);
    return [...values].filter(Boolean).sort((a, b) => a.localeCompare(b));
  }, [dataTeams, typedTeams, currentTeam]);

  const desiredTeam = teamValue === OTHER ? otherText.trim() : teamValue || null;
  const desiredType = teamTypeFor(desiredTeam);
  const unchanged =
    desiredTeam === (currentTeam ?? null) && desiredType === (currentTeamType ?? null);

  const saveTeam = async (override) => {
    const team = override !== undefined ? override : desiredTeam;
    const type = teamTypeFor(team);
    if (team && team.length > 80) {
      setError("Team name must be 80 characters or fewer.");
      return;
    }
    if (teamValue === OTHER && !team) {
      setError("Enter the team name.");
      return;
    }
    setSaving(true);
    setSaveState("saving");
    setError(null);
    setSuggestion(null);
    try {
      const response = await api.updateStatus({
        name,
        current_team: team,
        current_team_type: type,
      });
      const saved = response.players?.[name] ?? {};
      setTeamValue(
        saved.current_team && !IPL_TEAMS.includes(saved.current_team) && !SPECIAL_CURRENT_TEAMS.includes(saved.current_team)
          ? OTHER
          : saved.current_team ?? "",
      );
      setOtherText(
        saved.current_team && !IPL_TEAMS.includes(saved.current_team) && !SPECIAL_CURRENT_TEAMS.includes(saved.current_team)
          ? saved.current_team
          : "",
      );
      await onChanged?.();
      setSaveState("saved");
      api
        .history(name)
        .then((payload) => setHistory(payload.entries ?? []))
        .catch(() => {});
      const next = response.suggestion ?? null;
      const suggested = next?.status ?? suggestedStatusForTeam(saved.current_team);
      const liveStatus = saved.status ?? status;
      if (suggested && suggested !== liveStatus) {
        setSuggestion({ status: suggested, prompt: `Set status to ${statusMeta(suggested).label}?` });
      } else {
        setOpen(false);
      }
    } catch (err) {
      setSaveState("error");
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const applySuggestedStatus = async () => {
    if (!suggestion) return;
    setSaving(true);
    setSaveState("saving");
    setError(null);
    try {
      await api.updateStatus({ name, status: suggestion.status });
      await onChanged?.();
      setSaveState("saved");
      setSuggestion(null);
      setOpen(false);
    } catch (err) {
      setSaveState("error");
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const undo = async () => {
    setUndoing(true);
    setError(null);
    try {
      await api.undo(name);
      await onChanged?.();
      setOpen(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setUndoing(false);
    }
  };

  const historyTitle = history.length
    ? history
        .slice(-5)
        .reverse()
        .map((entry) =>
          entry.changes
            .map((change) => `${change.field}: ${entryValue(change.old)} → ${entryValue(change.new)}`)
            .join("; "),
        )
        .join("\n")
    : undefined;

  return (
    <>
      <span title={historyTitle}>
        <CurrentTeamChip
          currentTeam={currentTeam}
          currentTeamType={currentTeamType}
          dataTeam={dataTeam}
          onClick={() => setOpen(true)}
          className={cx(subtle && "opacity-90", className)}
        />
      </span>

      <Modal
        open={open}
        title={`Current team — ${name}`}
        subtitle={
          dataTeam
            ? `Latest team in the data: ${dataTeam} (unverified)`
            : "No latest team in the supplied data"
        }
        onClose={() => {
          if (!saving) setOpen(false);
        }}
        footer={
          <>
            <SaveIndicator state={saveState} className="mr-auto" />
            <button
              type="button"
              className="btn-ghost"
              onClick={() => setOpen(false)}
              disabled={saving}
            >
              Close
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => saveTeam()}
              disabled={saving || unchanged || (teamValue === OTHER && !otherText.trim())}
            >
              {saving ? "Saving…" : "Save team"}
            </button>
          </>
        }
      >
        <div className="space-y-3">
          {!currentTeam && dataTeam ? (
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-dashed border-slate-300 bg-slate-50/60 p-2.5 text-xs dark:border-slate-700 dark:bg-slate-950/40">
              <span className="text-slate-500 dark:text-slate-400">Suggested from data:</span>
              <span className="font-semibold text-slate-500 opacity-70 dark:text-slate-400">
                {dataTeam}
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">
                unverified
              </span>
              <button
                type="button"
                className="ml-auto btn-ghost h-7 px-2 py-1 text-[11px]"
                onClick={() => saveTeam(dataTeam)}
                disabled={saving}
              >
                Confirm
              </button>
            </div>
          ) : null}

          <div>
            <label htmlFor={`${listId}-team`} className="label">
              Current team
            </label>
            <select
              id={`${listId}-team`}
              className="select mt-1"
              value={teamValue}
              onChange={(event) => setTeamValue(event.target.value)}
              disabled={saving}
            >
              <option value="">Not set</option>
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
            <p className="mt-1 text-[10px] leading-relaxed text-slate-400 dark:text-slate-500">
              The data suggestion is never saved until you confirm it or choose a value.
            </p>
          </div>

          {teamValue === OTHER ? (
            <div>
              <label htmlFor={`${listId}-other`} className="label">
                Other team name
              </label>
              <input
                id={`${listId}-other`}
                className="input mt-1"
                value={otherText}
                onChange={(event) => setOtherText(event.target.value)}
                list={listId}
                placeholder="e.g. Surrey, Afghanistan"
                autoComplete="off"
                disabled={saving}
              />
              <datalist id={listId}>
                {autocomplete.map((value) => (
                  <option key={value} value={value} />
                ))}
              </datalist>
            </div>
          ) : null}

          {error ? (
            <p className="rounded-lg bg-red-50 p-2 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
              {error}
            </p>
          ) : null}

          {suggestion ? (
            <div
              role="alert"
              className="flex flex-wrap items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 p-2.5 text-xs text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/30 dark:text-amber-200"
            >
              <span>{suggestion.prompt} This is only a suggestion.</span>
              <div className="ml-auto flex gap-2">
                <button
                  type="button"
                  className="btn-primary h-7 px-2 py-1 text-[11px]"
                  onClick={applySuggestedStatus}
                  disabled={saving}
                >
                  Yes
                </button>
                <button
                  type="button"
                  className="btn-ghost h-7 px-2 py-1 text-[11px]"
                  onClick={() => {
                    setSuggestion(null);
                    setOpen(false);
                  }}
                  disabled={saving}
                >
                  No
                </button>
              </div>
            </div>
          ) : null}

          <div className="border-t border-slate-200 pt-3 dark:border-slate-800">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Last 5 changes
              </p>
              <button
                type="button"
                className="btn-ghost h-7 px-2 py-1 text-[11px]"
                onClick={undo}
                disabled={undoing || history.length === 0}
                title={historyTitle || "No recorded changes"}
              >
                {undoing ? "Undoing…" : "Undo last change"}
              </button>
            </div>
            <div className="mt-2">
              {historyError ? (
                <p className="text-[11px] text-red-600 dark:text-red-400">{historyError}</p>
              ) : (
                <ChangeList entries={history} />
              )}
            </div>
          </div>
        </div>
      </Modal>
    </>
  );
}
