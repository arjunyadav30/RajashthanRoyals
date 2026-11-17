import rosterCsv from "./data/ipl2026_players_current_teams.csv?raw";
import inactiveCsv from "./data/players_last_match_before_17-11-2024.csv?raw";
import pakistanCsv from "./data/pakistan_players_from_ball_by_ball.csv?raw";
import { compactName } from "./utils";

function csvRows(csv) {
  return csv
    .replace(/^\uFEFF/, "")
    .trim()
    .split(/\r?\n/)
    .slice(1)
    .map((line) =>
      line
        .split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/)
        .map((value) => value.trim().replace(/^"|"$/g, "").replace(/""/g, '"')),
    );
}

const rosterRows = csvRows(rosterCsv);
const inactiveRows = csvRows(inactiveCsv);
const pakistanRows = csvRows(pakistanCsv);
const rosterTeamByName = new Map(
  rosterRows
    .map(([name, team]) => [compactName(name), team])
    .filter(([name, team]) => name && team),
);
const excludedNames = new Set();
const excludedIds = new Set();
const inactiveNames = new Set();
const inactiveIds = new Set();

for (const [name] of rosterRows) {
  if (name) excludedNames.add(compactName(name));
}

export function getIpl2026RosterTeam(name) {
  return rosterTeamByName.get(compactName(name)) ?? null;
}

for (const [playerId, name] of inactiveRows) {
  if (playerId) inactiveIds.add(String(playerId));
  if (name) inactiveNames.add(compactName(name));
}

for (const [playerId, name] of [
  ...inactiveRows,
  ...pakistanRows,
]) {
  if (playerId) excludedIds.add(String(playerId));
  if (name) excludedNames.add(compactName(name));
}

export function isInactiveForTwoYears(player) {
  const playerId = String(player.player_id ?? "");
  const name = compactName(player.name);
  return (
    (playerId && inactiveIds.has(playerId)) ||
    (name && inactiveNames.has(name))
  );
}

export function getPlayerDirectoryTotals(batters = [], bowlers = []) {
  const playersByName = new Map();
  const playerNameById = new Map();

  for (const player of [...batters, ...bowlers]) {
    const key = compactName(player.name);
    if (!key) continue;
    if (player.player_id) playerNameById.set(String(player.player_id), key);
    const current = playersByName.get(key);
    if (current) {
      if (!current.player_id && player.player_id) {
        current.player_id = player.player_id;
      }
    } else {
      playersByName.set(key, { name: player.name, player_id: player.player_id });
    }
  }

  const rosterNames = new Set();
  for (const [name, team] of rosterRows) {
    const key = compactName(name);
    if (!name || !team || !key) continue;
    rosterNames.add(key);
    if (!playersByName.has(key)) playersByName.set(key, { name, player_id: null });
  }

  const inactiveNamesInDirectory = new Set();
  for (const [playerId, name] of inactiveRows) {
    const key = compactName(name);
    if (!key) continue;
    const playerKey = playersByName.has(key)
      ? key
      : playerNameById.get(String(playerId)) ?? key;
    const current = playersByName.get(playerKey);
    if (current) {
      if (!current.player_id && playerId) current.player_id = playerId;
    } else {
      playersByName.set(playerKey, { name, player_id: playerId });
    }
    inactiveNamesInDirectory.add(playerKey);
  }

  const players = [...playersByName.entries()].map(([key, player]) => ({ ...player, key }));
  return {
    all: players.length,
    ipl2026: players.filter((player) => rosterNames.has(player.key)).length,
    notPlayedSinceTwoYears: inactiveNamesInDirectory.size,
    pakistan: pakistanRows.length,
    available: players.filter((player) => !isExcludedFromAvailable(player)).length,
    other: players.filter(
      (player) => !rosterNames.has(player.key) && !inactiveNamesInDirectory.has(player.key),
    ).length,
  };
}

export function filterInactivePlayers(players) {
  return players.filter((player) => !isInactiveForTwoYears(player));
}

export function isExcludedFromAvailable(player) {
  return (
    excludedIds.has(String(player.player_id)) ||
    excludedNames.has(compactName(player.name))
  );
}
