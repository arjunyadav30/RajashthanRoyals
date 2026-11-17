const JSON_HEADERS = { "Content-Type": "application/json" };

async function request(path, options = {}) {
  const init =
    options.method && options.method !== "GET"
      ? options
      : { cache: "no-store", ...options };
  let response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new Error(
      "Could not reach the API. Is the FastAPI backend running on port 8000?",
    );
  }

  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail = body && body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail
          ? JSON.stringify(detail)
          : `Request failed (${response.status})`;
    if (response.status === 401 && !path.startsWith("/api/auth/")) {
      window.dispatchEvent(new CustomEvent("rr:auth-required"));
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return body;
}

function playersQuery({
  role,
  availableOnly = true,
  team,
  phase,
  minIplBalls,
  currentTeamUnset,
} = {}) {
  const params = new URLSearchParams();
  if (role) params.set("role", role);
  params.set("available_only", availableOnly ? "true" : "false");
  if (team) params.set("team", team);
  if (phase) params.set("phase", phase);
  if (minIplBalls !== undefined && minIplBalls !== null && minIplBalls !== "") {
    params.set("min_ipl_balls", String(minIplBalls));
  }
  if (currentTeamUnset) params.set("current_team_unset", "true");
  return params.toString();
}

export const api = {
  summary: () => request("/api/summary"),
  authMe: () => request("/api/auth/me", { cache: "no-store" }),
  login: (password) =>
    request("/api/auth/login", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ password }),
    }),
  logout: () => request("/api/auth/logout", { method: "POST" }),
  players: (options) => request(`/api/players?${playersQuery(options)}`),
  player: (role, playerId) =>
    request(`/api/player/${encodeURIComponent(role)}/${encodeURIComponent(playerId)}`),
  shortlist: (role) => request(`/api/shortlist?role=${encodeURIComponent(role)}`),
  status: () => request("/api/status"),
  updateStatus: (payload) =>
    request("/api/status", {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }),
  bulkStatus: (payload) =>
    request("/api/status/bulk", {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }),
  history: (name) => request(`/api/status/history/${encodeURIComponent(name)}`),
  undo: (name) =>
    request(`/api/status/undo/${encodeURIComponent(name)}`, { method: "POST" }),
  undoBulk: (names) =>
    request("/api/status/undo-bulk", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ names }),
    }),
  importStatus: (payload) =>
    request("/api/status/import", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }),
  scoresMeta: () => request("/api/scores/meta"),
  stats: (playerId, { role, split } = {}) => {    const params = new URLSearchParams();
    if (role) params.set("role", role);
    if (split) params.set("split", split);
    return request(
      `/api/stats/${encodeURIComponent(playerId)}?${params.toString()}`,
    );
  },
  matchups: (playerId, { role } = {}) => {
    const params = new URLSearchParams();
    if (role) params.set("role", role);
    return request(
      `/api/matchups/${encodeURIComponent(playerId)}?${params.toString()}`,
    );
  },
  statsIndex: ({ role, minBalls, season, competition, team } = {}) => {
    const params = new URLSearchParams();
    if (role) params.set("role", role);
    if (minBalls !== undefined && minBalls !== null && minBalls !== "") {
      params.set("min_balls", String(minBalls));
    }
    if (season) params.set("season", season);
    if (competition) params.set("competition", competition);
    if (team) params.set("team", team);
    return request(`/api/stats-index?${params.toString()}`);
  },
  teams: () => request("/api/teams"),
  team: (slug) => request(`/api/teams/${encodeURIComponent(slug)}`),
  saveTeamXi: (slug, players) =>
    request(`/api/teams/${encodeURIComponent(slug)}/xi`, {
      method: "PUT",
      headers: JSON_HEADERS,
      body: JSON.stringify({ players }),
    }),
  resetTeamXi: (slug) =>
    request(`/api/teams/${encodeURIComponent(slug)}/xi`, { method: "DELETE" }),
  search: (query) => request(`/api/search?q=${encodeURIComponent(query)}`),
  recent: (playerId) => request(`/api/recent/${encodeURIComponent(playerId)}`),
};

export async function downloadStatusExport(format = "json") {
  let response;
  try {
    response = await fetch(`/api/status/export?format=${encodeURIComponent(format)}`, {
      cache: "no-store",
    });
  } catch {
    throw new Error("Could not reach the API. Is the FastAPI backend running on port 8000?");
  }
  if (!response.ok) {
    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent("rr:auth-required"));
    }
    let detail = `Export failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // keep the generic message
    }
    throw new Error(detail);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  anchor.href = url;
  anchor.download = match?.[1] || `rr-status.${format}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
