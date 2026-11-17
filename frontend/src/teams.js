export const IPL_TEAMS = [
  "Chennai Super Kings",
  "Delhi Capitals",
  "Gujarat Titans",
  "Kolkata Knight Riders",
  "Lucknow Super Giants",
  "Mumbai Indians",
  "Punjab Kings",
  "Rajasthan Royals",
  "Royal Challengers Bengaluru",
  "Sunrisers Hyderabad",
];

export const RELEASED_TEAM = "Released / in auction pool";
export const NO_TEAM = "No team / not playing IPL";
export const SPECIAL_CURRENT_TEAMS = [RELEASED_TEAM, NO_TEAM];

export function suggestedStatusForTeam(team) {
  if (!team) return null;
  if (team === "Rajasthan Royals") return "rr_own";
  if (IPL_TEAMS.includes(team)) return "retained";
  if (team === RELEASED_TEAM) return "pool";
  if (team === NO_TEAM) return "no_ipl";
  return null;
}

export function dataTeamFor(row) {
  return row?.latest_IPL_team || row?.latest_team || null;
}

export function effectiveTeamFor(row) {
  if (!row) return null;
  return row.current_team ?? row.effective_team ?? dataTeamFor(row);
}

export function teamSourceFor(row) {
  if (!row) return null;
  if (row.current_team) return "manual";
  return row.team_source ?? "data";
}

export function teamSourceLabel(source) {
  return source === "manual" ? "current team set by me" : "latest team from data";
}

export function teamTypeFor(team) {
  if (!team) return null;
  if (IPL_TEAMS.includes(team)) return "ipl";
  if (SPECIAL_CURRENT_TEAMS.includes(team)) return null;
  return "other";
}
