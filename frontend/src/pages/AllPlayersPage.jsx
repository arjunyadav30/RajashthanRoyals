import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import rosterCsv from "../data/ipl2026_players_current_teams.csv?raw";
import inactiveCsv from "../data/players_last_match_before_17-11-2024.csv?raw";
import pakistanCsv from "../data/pakistan_players_from_ball_by_ball.csv?raw";
import { PlayerAvatar } from "../components/Badges";
import DataTable from "../components/DataTable";
import { EmptyState, ErrorNote, LoadingBlock } from "../components/States";
import { isExcludedFromAvailable } from "../availablePlayers";
import { compactName, fmtInt, fmtNum } from "../utils";

function parseCsv(csv) {
  const lines = csv.replace(/^\uFEFF/, "").trim().split(/\r?\n/);
  return lines.slice(1).map((line) =>
    line
      .split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/)
      .map((value) => value.trim().replace(/^"|"$/g, "").replace(/""/g, '"')),
  );
}

function parseRoster(csv) {
  const roster = new Map();
  for (const [name = "", team = ""] of parseCsv(csv)) {
    if (name && team) roster.set(compactName(name), { name, team });
  }
  return roster;
}

function parseInactivePlayers(csv) {
  const inactive = new Map();
  for (const [playerId, name, lastMatchDate, roleSeen = ""] of parseCsv(csv)) {
    if (name) {
      inactive.set(compactName(name), { playerId, name, lastMatchDate, roleSeen });
    }
  }
  return inactive;
}

function parsePakistanPlayers(csv) {
  return parseCsv(csv).map(([playerId, name, matches, firstMatch, lastMatch, roles]) => ({
    playerId,
    name,
    matches,
    firstMatch,
    lastMatch,
    roles,
  }));
}

function rolesFromLabel(label) {
  const roles = new Set();
  if (/batter/i.test(label)) roles.add("batter");
  if (/bowler/i.test(label)) roles.add("bowler");
  return roles;
}

function rankedRole(player) {
  const isAllRounder =
    (player.roles.has("batter") && player.roles.has("bowler")) ||
    /all[\s-]*rounder/i.test(player.rankingRole ?? "");
  if (isAllRounder) return "allrounder";
  if (player.roles.has("batter")) return "batter";
  if (player.roles.has("bowler")) return "bowler";
  return null;
}

function roleRank(player) {
  return {
    rank: player.all_rank ?? player.rank ?? null,
    qualifiedRank: player.qualified_rank ?? null,
    rating: player.rating100 ?? player.score ?? null,
  };
}

function mergePlayers(batters, bowlers, roster, inactive, pakistan) {
  const byName = new Map();
  const playerNameById = new Map();
  for (const [players, playerRole] of [[batters, "batter"], [bowlers, "bowler"]]) {
    for (const player of players) {
      const key = compactName(player.name);
      if (!key) continue;
      if (player.player_id) playerNameById.set(String(player.player_id), key);
      const current = byName.get(key);
      const inactiveRecord = inactive.get(key);
      if (current) {
        current.roles.add(playerRole);
        current.roleRanks[playerRole] = roleRank(player);
        if (/all[\s-]*rounder/i.test(player.role ?? "")) current.rankingRole = player.role;
        if (inactiveRecord) {
          current.notPlayedSinceTwoYears = true;
          current.lastMatchDate = inactiveRecord.lastMatchDate;
        }
        if (!current.player_id && player.player_id) {
          current.player_id = player.player_id;
          current.profileRole = playerRole;
        }
        continue;
      }
      byName.set(key, {
        ...player,
        roles: new Set([playerRole]),
        roleRanks: { [playerRole]: roleRank(player) },
        rankingRole: player.role ?? "",
        profileRole: playerRole,
        notPlayedSinceTwoYears: Boolean(inactiveRecord),
        lastMatchDate: inactiveRecord?.lastMatchDate ?? "",
      });
    }
  }

  for (const [key, entry] of roster) {
    if (!byName.has(key)) {
      byName.set(key, {
        name: entry.name,
        roles: new Set(),
        roleRanks: {},
        rankingRole: "",
        profileRole: undefined,
        notPlayedSinceTwoYears: false,
        lastMatchDate: "",
      });
    }
  }

  for (const [key, entry] of inactive) {
    const playerKey = byName.has(key)
      ? key
      : playerNameById.get(String(entry.playerId));
    const current = playerKey ? byName.get(playerKey) : undefined;
    if (current) {
      current.notPlayedSinceTwoYears = true;
      current.lastMatchDate = entry.lastMatchDate;
      if (current.roles.size === 0) current.roles = rolesFromLabel(entry.roleSeen);
      if (!current.player_id) current.player_id = entry.playerId;
    } else {
      byName.set(key, {
        name: entry.name,
        player_id: entry.playerId,
        roles: rolesFromLabel(entry.roleSeen),
        roleRanks: {},
        rankingRole: entry.roleSeen,
        profileRole: undefined,
        notPlayedSinceTwoYears: true,
        lastMatchDate: entry.lastMatchDate,
      });
    }
  }

  return [...byName.entries()].map(([key, player]) => ({
    ...player,
    rankingCategory: rankedRole(player),
    inIpl2026List: roster.has(key),
    isPakistanPlayer:
      pakistan.some(
        (entry) =>
          String(entry.playerId) === String(player.player_id) ||
          compactName(entry.name) === key,
      ),
    currentTeam2026: roster.get(key)?.team ?? "",
    roleLabel: [...player.roles].filter(Boolean).join(" / ") || "—",
  }));
}

function buildPakistanRows(pakistan, rankedPlayers, roster, inactive) {
  const rankedById = new Map();
  for (const player of rankedPlayers) {
    if (!player.player_id) continue;
    const key = String(player.player_id);
    const current = rankedById.get(key);
    if (current) {
      current.roles.add(player.player_type);
    } else {
      rankedById.set(key, {
        ...player,
        roles: new Set([player.player_type]),
      });
    }
  }

  return pakistan.map((entry) => {
    const player = rankedById.get(String(entry.playerId));
    const roles = player?.roles ?? rolesFromLabel(entry.roles);
    const inactiveRecord =
      inactive.get(compactName(entry.name))?.playerId === String(entry.playerId)
        ? inactive.get(compactName(entry.name))
        : undefined;
    return {
      ...player,
      identityKey: `pakistan:${entry.playerId}`,
      name: entry.name,
      player_id: entry.playerId,
      profileRole: player?.player_type,
      roles,
      roleLabel: [...roles].filter(Boolean).join(" / ") || "—",
      isPakistanPlayer: true,
      inIpl2026List: roster.has(compactName(entry.name)),
      currentTeam2026: roster.get(compactName(entry.name))?.team ?? "",
      notPlayedSinceTwoYears: Boolean(inactiveRecord),
      lastMatchDate: inactiveRecord?.lastMatchDate ?? "",
      pakistanMatches: Number(entry.matches) || null,
      pakistanFirstMatch: entry.firstMatch,
      pakistanLastMatch: entry.lastMatch,
    };
  });
}

export default function AllPlayersPage() {
  const [state, setState] = useState({
    loading: true,
    error: null,
    players: [],
    pakistanPlayers: [],
  });
  const [role, setRole] = useState("all");
  const [segment, setSegment] = useState("all");
  const [availableRole, setAvailableRole] = useState("allrounder");
  const [query, setQuery] = useState("");
  const roster = useMemo(() => parseRoster(rosterCsv), []);
  const inactive = useMemo(() => parseInactivePlayers(inactiveCsv), []);
  const pakistan = useMemo(() => parsePakistanPlayers(pakistanCsv), []);

  const loadPlayers = () => {
    setState((current) => ({ ...current, loading: true, error: null }));
    Promise.all([
      api.players({ role: "batter", availableOnly: false }),
      api.players({ role: "bowler", availableOnly: false }),
    ])
      .then(([batters, bowlers]) => {
        setState({
          loading: false,
          error: null,
          players: mergePlayers(
            batters.players ?? [],
            bowlers.players ?? [],
            roster,
            inactive,
            pakistan,
          ),
          pakistanPlayers: buildPakistanRows(
            pakistan,
            [...(batters.players ?? []), ...(bowlers.players ?? [])],
            roster,
            inactive,
          ),
        });
      })
      .catch((error) =>
        setState({ loading: false, error: error.message, players: [], pakistanPlayers: [] }),
      );
  };

  useEffect(() => {
    loadPlayers();
  }, []);

  const players = useMemo(() => {
    const needle = compactName(query);
    const sourcePlayers = segment === "pakistan" ? state.pakistanPlayers : state.players;
    return sourcePlayers
      .filter((player) => {
        if (segment === "available") {
          return (
            !isExcludedFromAvailable(player) &&
            player.rankingCategory === availableRole
          );
        }
        if (role !== "all" && !player.roles.has(role)) return false;
        if (segment === "ipl2026") return player.inIpl2026List;
        if (segment === "inactive") return player.notPlayedSinceTwoYears;
        return true;
      })
      .filter(
        (player) =>
          !needle ||
          compactName(player.name).includes(needle) ||
          compactName(player.currentTeam2026).includes(needle),
      )
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [state.players, state.pakistanPlayers, role, segment, availableRole, query]);

  const totals = useMemo(
    () => {
      const availablePlayers = state.players.filter(
        (player) => !isExcludedFromAvailable(player),
      );
      return {
        all: state.players.length,
        ipl2026: state.players.filter((player) => player.inIpl2026List).length,
        notPlayedSinceTwoYears: state.players.filter((player) => player.notPlayedSinceTwoYears).length,
        other: state.players.filter((player) => !player.inIpl2026List && !player.notPlayedSinceTwoYears).length,
        pakistan: state.pakistanPlayers.length,
        available: availablePlayers.length,
        availableBatters: availablePlayers.filter((player) => player.rankingCategory === "batter").length,
        availableBowlers: availablePlayers.filter((player) => player.rankingCategory === "bowler").length,
        availableAllRounders: availablePlayers.filter((player) => player.rankingCategory === "allrounder").length,
      };
    },
    [state.players, state.pakistanPlayers],
  );

  const playerNameColumn = {
    key: "name",
    label: "Player",
    cell: (player) => (
        <div className="flex items-center gap-2.5">
          <PlayerAvatar name={player.name} role={player.profileRole} size="sm" />
          {player.player_id && player.profileRole ? (
            <Link
              to={`/player/${player.profileRole}/${player.player_id}`}
              className="font-semibold text-slate-900 hover:text-rr-700 dark:text-white dark:hover:text-rr-300"
            >
              {player.name}
            </Link>
          ) : (
            <span className="font-semibold text-slate-900 dark:text-white">{player.name}</span>
          )}
        </div>
    ),
  };

  const columns = [
    playerNameColumn,
    {
      key: "roleLabel",
      label: "Role",
      cell: (player) => player.roleLabel,
    },
    {
      key: "isPakistanPlayer",
      label: "Country",
      cell: (player) =>
        player.isPakistanPlayer ? (
          <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300">
            Pakistan
          </span>
        ) : (
          "—"
        ),
    },
    {
      key: "currentTeam2026",
      label: "IPL 2026 team",
      cell: (player) => player.currentTeam2026 || "—",
    },
    {
      key: "inIpl2026List",
      label: "IPL 2026",
      cell: (player) => {
        const style = player.inIpl2026List
          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300"
          : "bg-slate-200 text-slate-700 dark:bg-slate-700/50 dark:text-slate-300";
        return (
          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${style}`}>
            {player.inIpl2026List ? "IPL 2026" : "—"}
          </span>
        );
      },
    },
    {
      key: "notPlayedSinceTwoYears",
      label: "Last match",
      cell: (player) =>
        player.notPlayedSinceTwoYears ? (
          <span>
            <span className="block text-xs font-semibold text-amber-800 dark:text-amber-300">
              Not played since 2 years
            </span>
            <span className="num text-[10px] text-slate-500 dark:text-slate-400">
              Last match: {player.lastMatchDate}
            </span>
          </span>
        ) : (
          "—"
        ),
    },
  ];

  const availableColumns =
    availableRole === "allrounder"
      ? [
          playerNameColumn,
          {
            key: "batter_rank",
            label: "Batter rank",
            align: "center",
            cell: (player) => (
              <span className="num">{fmtInt(player.roleRanks?.batter?.rank)}</span>
            ),
          },
          {
            key: "batter_score",
            label: "Batter score",
            align: "center",
            cell: (player) => (
              <span className="num">{fmtNum(player.roleRanks?.batter?.rating)}</span>
            ),
          },
          {
            key: "bowler_rank",
            label: "Bowler rank",
            align: "center",
            cell: (player) => (
              <span className="num">{fmtInt(player.roleRanks?.bowler?.rank)}</span>
            ),
          },
          {
            key: "bowler_score",
            label: "Bowler score",
            align: "center",
            cell: (player) => (
              <span className="num">{fmtNum(player.roleRanks?.bowler?.rating)}</span>
            ),
          },
        ]
      : [
          playerNameColumn,
          {
            key: "rank",
            label: "Rank",
            align: "center",
            cell: (player) => (
              <span className="num font-semibold">
                {fmtInt(player.roleRanks?.[availableRole]?.rank)}
              </span>
            ),
          },
          {
            key: "qualified_rank",
            label: "Qualified rank",
            align: "center",
            cell: (player) => (
              <span className="num">
                {fmtInt(player.roleRanks?.[availableRole]?.qualifiedRank)}
              </span>
            ),
          },
          {
            key: "rating",
            label: "Score",
            align: "center",
            cell: (player) => (
              <span className="num font-semibold">
                {fmtNum(player.roleRanks?.[availableRole]?.rating)}
              </span>
            ),
          },
        ];

  const visiblePlayers = players;

  return (
    <div className="space-y-6">
      <header>
        <p className="label">Player directory</p>
        <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-900 dark:text-white sm:text-3xl">
          All Players
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600 dark:text-slate-400">
          Available excludes the supplied IPL 2026, two-year inactivity and Pakistan lists.
          Players ranked in both batting and bowling are grouped as all-rounders.
        </p>
      </header>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6" aria-label="Player totals">
        {[
          ["Players", totals.all],
          ["IPL 2026 list", totals.ipl2026],
          ["Not played since 2 years", totals.notPlayedSinceTwoYears],
          ["Pakistan players", totals.pakistan],
          ["Available", totals.available],
          ["Other players", totals.other],
        ].map(([label, count]) => (
          <div className="card p-4" key={label}>
            <p className="label">{label}</p>
            <p className="num mt-1 text-2xl font-black text-slate-900 dark:text-white">
              {state.loading ? "—" : fmtInt(count)}
            </p>
          </div>
        ))}
      </section>

      <section className="card space-y-4 p-4 sm:p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-semibold text-slate-600 dark:text-slate-300">
            Search player or team
            <input
              className="input mt-1.5"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search…"
            />
          </label>
          {segment !== "available" ? (
            <label className="text-xs font-semibold text-slate-600 dark:text-slate-300">
              Role
              <select className="select mt-1.5" value={role} onChange={(event) => setRole(event.target.value)}>
                <option value="all">All roles</option>
                <option value="batter">Batters</option>
                <option value="bowler">Bowlers</option>
              </select>
            </label>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2" role="group" aria-label="Player list filters">
          {[
            ["all", "All players", totals.all],
            ["ipl2026", "IPL 2026", totals.ipl2026],
            ["inactive", "Not played since 2 years", totals.notPlayedSinceTwoYears],
            ["pakistan", "Pakistan players", totals.pakistan],
            ["available", "Available", totals.available],
          ].map(([value, label, count]) => (
            <button
              key={value}
              type="button"
              onClick={() => setSegment(value)}
              aria-pressed={segment === value}
              className={`rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
                segment === value
                  ? "bg-rr-600 text-white"
                  : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              }`}
            >
              {label} <span className="num ml-1 opacity-75">{state.loading ? "…" : count}</span>
            </button>
          ))}
        </div>

        {segment === "available" ? (
          <div className="flex flex-wrap gap-2" role="group" aria-label="Available player rankings">
            {[
              ["batter", "Batters", totals.availableBatters],
              ["bowler", "Bowlers", totals.availableBowlers],
              ["allrounder", "All-rounders", totals.availableAllRounders],
            ].map(([value, label, count]) => (
              <button
                key={value}
                type="button"
                onClick={() => setAvailableRole(value)}
                aria-pressed={availableRole === value}
                className={`rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
                  availableRole === value
                    ? "bg-sky-600 text-white"
                    : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                }`}
              >
                {label} <span className="num ml-1 opacity-75">{state.loading ? "…" : count}</span>
              </button>
            ))}
          </div>
        ) : null}

        {state.error ? <ErrorNote message={state.error} onRetry={loadPlayers} /> : null}
        {state.loading ? (
          <LoadingBlock rows={7} />
        ) : (
          <>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Showing {fmtInt(visiblePlayers.length)} of {fmtInt(players.length)} matching players
            </p>
            <DataTable
              columns={segment === "available" ? availableColumns : columns}
              rows={visiblePlayers}
              rowKey={(player) => player.identityKey ?? compactName(player.name)}
              caption={
                segment === "available"
                  ? `Available ${availableRole} rankings`
                  : "Player directory with IPL 2026 and two-year inactivity filters"
              }
              empty={<EmptyState title="No players match" hint="Try changing the search or filters." />}
            />
          </>
        )}
      </section>
    </div>
  );
}
