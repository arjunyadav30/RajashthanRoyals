import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { normaliseName } from "../utils";

const ROLE_LABELS = { batter: "Batter", bowler: "Bowler" };

function buildRoleRows(payload, role, explicitMap) {
  const rows = new Map();
  for (const player of payload.players ?? []) {
    const name = String(player.name ?? "").trim();
    if (!name || rows.has(name)) continue;
    rows.set(name, {
      name,
      role,
      team: player.team_label || player.latest_IPL_team || player.latest_team || "—",
      rank: player.rank,
      rr_fit: explicitMap[name]?.rr_fit ?? player.rr_fit ?? "",
    });
  }
  return [...rows.values()].sort(
    (a, b) => (a.rank ?? Number.MAX_SAFE_INTEGER) - (b.rank ?? Number.MAX_SAFE_INTEGER) ||
      a.name.localeCompare(b.name),
  );
}

export default function RRFitPage() {
  const { authenticated, openLogin } = useAuth();
  const [role, setRole] = useState("batter");
  const [state, setState] = useState({
    loading: true,
    error: null,
    batter: [],
    bowler: [],
  });
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const load = useCallback(async () => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const [statusData, batters, bowlers] = await Promise.all([
        api.status(),
        api.players({ role: "batter", availableOnly: false }),
        api.players({ role: "bowler", availableOnly: false }),
      ]);
      const explicitMap = statusData.players ?? {};
      setState({
        loading: false,
        error: null,
        batter: buildRoleRows(batters, "batter", explicitMap),
        bowler: buildRoleRows(bowlers, "bowler", explicitMap),
      });
    } catch (error) {
      setState((current) => ({ ...current, loading: false, error: error.message }));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const allRows = state[role];
  const visibleRows = allRows;
  const fitRows = useMemo(
    () => visibleRows.filter((player) => player.rr_fit.trim()),
    [visibleRows],
  );
  const searchResults = useMemo(() => {
    const normalizedQuery = normaliseName(query);
    if (normalizedQuery.length < 2) return [];
    return visibleRows
      .filter((player) => normaliseName(player.name).includes(normalizedQuery))
      .slice(0, 8);
  }, [visibleRows, query]);

  const choosePlayer = (player) => {
    setSelected(player);
    setQuery(player.name);
    setDraft(player.rr_fit);
    setMessage(null);
  };

  const save = async () => {
    if (!selected) return;
    if (!authenticated) {
      openLogin();
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const rrFit = draft.trim();
      await api.updateStatus({ name: selected.name, rr_fit: rrFit });
      await load();
      setSelected({ ...selected, rr_fit: rrFit });
      setDraft(rrFit);
      setMessage({
        type: "success",
        text: rrFit ? "RR fit saved." : "RR fit removed.",
      });
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-rr-700 dark:text-rr-300">
          Rajasthan Royals scouting
        </p>
        <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-950 dark:text-white">
          RR Fit
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
          Add and review player fit notes, separated by batting and bowling role.
        </p>
      </header>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Player role">
        {Object.entries(ROLE_LABELS).map(([key, label]) => {
          const count = state[key].filter((player) => player.rr_fit.trim()).length;
          return (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={role === key}
              className={role === key ? "btn-primary" : "btn-ghost"}
              onClick={() => {
                setRole(key);
                setQuery("");
                setSelected(null);
                setDraft("");
                setMessage(null);
              }}
            >
              {label}s <span className="ml-1 opacity-75">({count})</span>
            </button>
          );
        })}
      </div>

      {state.error ? (
        <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
          {state.error}
        </div>
      ) : null}

      {state.loading ? (
        <div className="card p-6 text-sm text-slate-500 dark:text-slate-400">
          Loading RR fit players…
        </div>
      ) : (
        <>
          <section className="card p-4 sm:p-5">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">
              Add or update a {ROLE_LABELS[role].toLowerCase()} fit
            </h2>
            <label htmlFor="rr-fit-search" className="label mt-4 block">
              Search player
            </label>
            <input
              id="rr-fit-search"
              className="input mt-1"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setSelected(null);
                setDraft("");
                setMessage(null);
              }}
              placeholder={`Search ${ROLE_LABELS[role].toLowerCase()}s by name`}
            />

            {searchResults.length ? (
              <div className="mt-2 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
                {searchResults.map((player) => (
                  <button
                    key={player.name}
                    type="button"
                    className="flex w-full items-center justify-between gap-3 border-b border-slate-100 px-3 py-2 text-left last:border-b-0 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/60"
                    onClick={() => choosePlayer(player)}
                  >
                    <span className="text-sm font-semibold text-slate-900 dark:text-white">
                      {player.name}
                    </span>
                    <span className="truncate text-xs text-slate-500 dark:text-slate-400">
                      {player.team}
                    </span>
                  </button>
                ))}
              </div>
            ) : query.trim().length >= 2 && !selected ? (
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                No {ROLE_LABELS[role].toLowerCase()} found for that search.
              </p>
            ) : null}

            {selected ? (
              <div className="mt-4 rounded-xl bg-slate-50 p-3 dark:bg-slate-800/60">
                <p className="text-sm font-bold text-slate-900 dark:text-white">
                  {selected.name}
                  <span className="ml-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                    {selected.team}
                  </span>
                </p>
                <label htmlFor="rr-fit-note" className="label mt-3 block">
                  RR fit note
                </label>
                <textarea
                  id="rr-fit-note"
                  rows={3}
                  className="input mt-1 resize-y"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder="e.g. Powerplay enforcer; fits RR top order"
                />
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <button type="button" className="btn-primary" onClick={save} disabled={saving}>
                    {saving ? "Saving…" : draft.trim() ? "Save RR fit" : "Remove RR fit"}
                  </button>
                  {message ? (
                    <p
                      role={message.type === "error" ? "alert" : "status"}
                      className={
                        message.type === "error"
                          ? "text-xs text-red-700 dark:text-red-300"
                          : "text-xs text-emerald-700 dark:text-emerald-300"
                      }
                    >
                      {message.text}
                    </p>
                  ) : null}
                </div>
              </div>
            ) : (
              <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                Choose a player, then add a note. Saving a blank note removes that player from the RR fit list.
              </p>
            )}
          </section>

          <section className="card p-4 sm:p-5">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                  {ROLE_LABELS[role]} RR fits
                </h2>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Dual-role players share one RR fit note and can appear in both tabs.
                </p>
              </div>
              <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                {fitRows.length} saved
              </span>
            </div>
            {fitRows.length ? (
              <div className="mt-4 divide-y divide-slate-100 dark:divide-slate-800">
                {fitRows.map((player) => (
                  <article
                    key={player.name}
                    className="flex flex-col gap-3 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-start sm:justify-between"
                  >
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-900 dark:text-white">{player.name}</p>
                      <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
                        {player.team}
                      </p>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                        {player.rr_fit}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn-ghost shrink-0 self-start"
                      onClick={() => choosePlayer(player)}
                    >
                      Edit
                    </button>
                  </article>
                ))}
              </div>
            ) : (
              <p className="mt-4 rounded-lg bg-slate-50 p-4 text-sm text-slate-500 dark:bg-slate-800/50 dark:text-slate-400">
                No {ROLE_LABELS[role].toLowerCase()} RR fits saved yet. Search for a player above to add one.
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
