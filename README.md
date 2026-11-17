# Reliability Under Pressure — RR IPL 2027 Auction Scouting

Presentation and exploration layer for the Rajasthan Royals *SupeRR Selector
Season 2* analysis. It uses the supplied RR 2027 master player-analysis CSV for
player scores and rankings, with an availability layer for the IPL 2027 auction pool.

## Build status

This repository currently contains:

- **Add-on 3 foundation (complete):** the offline precompute for every player in
  the data pack, `player_index.json`, plus `/api/search` and `/api/recent`.
- **Stage 1 backend (complete):** availability status persistence, clean
  re-ranking, players/shortlist/summary/player/derived endpoints, CORS, caching
  and tests.
- **Stage 1 frontend (complete):** the React/Vite/Tailwind/Recharts app in
  `frontend/` with Overview, Batters, Bowlers, Player and Availability pages.
  It reads the supplied master ranking CSV and talks to FastAPI through the Vite
  dev proxy (`/api` → `http://127.0.0.1:8000`).
- **Add-on 5 (complete):** current team per player, team-aware filters and an
  Auction Board print view, plus status history/undo, bulk edit and JSON/CSV
  import-export.
- **Persistent status store:** edits use SQLite locally by default, or managed
  PostgreSQL when `DATABASE_URL` is configured. The UI provides optimistic
  updates, a Saving/Saved/Error indicator and Export/Import backup buttons.
- **Stats layer (complete):** offline batting/bowling aggregates for every
  player in `data_derived/stats`, a Stats tab on player and recent-form pages,
  a sortable/searchable Stats Explorer and a Data & Methods page.
- **Scoring engine (complete):** an independent state-based win-probability,
  leverage, impact and empirical-Bayes composite in `engine/`, run with
  `python engine/run_all.py`. It scores every batter and bowler in the pack and
  writes compact tables to `data_derived/scores`.
- **IPL 2027 squads (complete):** the supplied ten-team rosters seed
  `current_team` (and now auto-derive availability), plus a Teams list and
  per-team profile with league ranks, a data-driven best XI, strengths,
  weaknesses and the bench.

Ranking-dependent endpoints return `ready: false` with a clear message instead
of crashing when the CSVs are absent; search and recent form still work.
Other Stage 2+ modules are not part of this drop.

## Confidentiality rule

`data_raw/` is the confidential competition pack. It is gitignored and is only
read by `precompute.py`. It must never be copied into the frontend, build output,
an API response, the deployed app or the git repo. Only aggregate files in
`data_derived/` are deployable, and no row-level delivery is ever written.

`python scripts/build_check.py` fails if:

- a `data_raw` path or a raw-pack filename appears in the deploy roots
  (`frontend/dist`, `data_derived`, `backend`), or
- any deployable file is larger than 5 MB, or
- `/data_raw/` is missing from `.gitignore`.

## Quick start

```bash
cd rr-pressure-dashboard
python -m venv .venv
source .venv/Scripts/activate      # Git Bash on Windows
pip install -r requirements.txt
python precompute.py
python engine/run_all.py
python scripts/build_rubric.py
python scripts/build_matchups.py
python -m uvicorn backend.main:app --reload --port 8000
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Frontend: http://localhost:5173
- Health: http://localhost:8000/api/health

### The exact commands

| Step | Command |
| --- | --- |
| Precompute stats (offline, run once, or after changing rules) | `python precompute.py` |
| Score engine (offline, after raw-data or model changes) | `python engine/run_all.py` |
| Build the 0–100 auction rating (offline, after the engine) | `python scripts/build_rubric.py` |
| Build head-to-head matchups (offline, after raw-data changes) | `python scripts/build_matchups.py` |
| Build the nationality/overseas map for team profiles (offline) | `python scripts/build_team_meta.py` |
| Seed the supplied IPL 2027 rosters into current team (backend running) | `python scripts/apply_2027_rosters.py` |
| Backend (FastAPI) | `python -m uvicorn backend.main:app --reload --port 8000` |
| Frontend (React/Vite) | `cd frontend && npm install && npm run dev` |

The offline steps cache intermediate parquet files under `engine/.cache/` or
`data_derived/`, so reruns are fast. `python engine/run_all.py --refresh` ignores
the engine cache; `python scripts/build_matchups.py` rebuilds all matchup tables.

### 0–100 auction rating

Rankings, the auction board and the XI fit use a 100-mark rubric layered on top
of the engine. `python scripts/build_rubric.py` reads the engine career tables
plus the derived player profiles and writes `data_derived/scores/rubric.json`
(career aggregates only — no delivery rows). It is deterministic and safe to
re-run; run it after the engine.

| Role | Criteria (marks) |
| --- | --- |
| Batter | Overall 15, Pressure 18, Consistency 13, Boundary 10, Dot control 8, Phase 10, Pace & spin 8, Form 5, Matches 7, Sample 6 |
| Bowler | Overall 15, Pressure 18, Wickets 13, Economy 10, Dot % 8, Consistency 10, Phase 8, Batting styles 5, Form 5, Matches 7, Sample 6 |

Criteria are percentile-based within the role; rate metrics are shrunk toward
the role median with reliability n/(n+prior) (career 150 balls, form 100 balls,
phase/style splits 15–30 balls) so one- and two-match cameos sit near the middle
instead of topping the table. Experience marks follow match counts (1–5→1,
6–10→2, 11–20→3, 21–30→4, 31–50→5, 51–75→6, 76+→7); sample marks out of 6
scale with innings, legal balls and matches. Clean ranks are sorted by the
rating, and each player page shows the per-criterion marks, strengths,
watch-outs and a Low/Medium/High risk badge.

Vite proxies `/api` to the backend, so the app works in dev with no CORS setup
or hard-coded API host. Override the target with `VITE_API_TARGET` if you run
the API on another port. A production build is `cd frontend && npm run build`.

## Access control (public preview vs signed-in)

Everyone can read the dashboard without an account, but every table is limited
to its first five rows and each list shows a "Preview mode" lock banner with a
Sign in button, except Availability and RR Fit: those pages expose the complete
status, team, note, and fit data to visitors. Sign-in is still required to edit,
import, or download.

The public Availability/RR Fit baseline is stored in
`backend/data/public_status_seed.json` and seeds an empty SQLite database at
startup. This restores the published baseline after an ephemeral Render restart;
edits made after startup still need a persistent disk/database to survive a
restart.

- The header shows a **Log in** button; after signing in it becomes
  **Scout / Sign out**.
- Password comes from `APP_PASSWORD` (default `royals2027`). Sessions are signed
  with `APP_SECRET` (default `rr-scout-dev-secret`; set both in deployment).
- Login sets an HttpOnly cookie `rr_session` valid for 12 hours.
- Write and download endpoints return `401` without a session, so the lock is
  enforced by the API, not only hidden in the UI. Any `401` from the frontend
  opens the sign-in dialog.
- Protected API routes: `PUT /api/status`, `PUT /api/status/{name}`,
  `PUT /api/status/bulk`, `GET /api/status/export`, `POST /api/status/import`,
  `POST /api/status/undo/{name}`.

## Frontend (Stage 1 + Add-on 5)

- **Start here (`/`):** scouting homepage with a live ranking snapshot, the six
  All Players directory totals, top-five active available batters and bowlers,
  and navigation to the key scouting tools. This is the default route; the KPI
  dashboard lives at `/overview`.
- **Overview (`/overview`):** KPI tiles, readiness and top 5 available batters/bowlers.
- **Batters / Bowlers:** sortable, searchable tables with available-only,
  current-team/country, dominant-phase, minimum-balls and "current team not
  set" filters; a source-criteria qualification toggle (off by default)
  and separate all-player and qualified ranks; clean top 10 highlighted, ranks
  11–20 shaded as reserves; flag badges; CSV export of the filtered view; inline
  current-team editor per row. The IPL 2026 roster filter reveals matching players
  across all availability states; the availability selector and current-team editor
  let scouts mark released players directly from these lists.
- **Player:** headline source score, pressure vs
  normal and component Recharts bars, sample/stability cards, 2026 form, an
  editable availability/`rr_fit` box, the current-team editor in the header, and
  a **Stats** tab (Batting/Bowling sub-tabs, split dropdown, ball counts,
  small-sample flags, percentile chips, mini bars, pressure-only toggle) and a
  **Matchups** sub-tab listing aggregate head-to-head records against every
  opponent with 6+ balls, a search box, a 6/12/24 minimum-balls filter and
  "small" tags under 12 balls.
- **Recent Form** (`/recent-form/:playerId`): match log plus the same **Stats**
  tab and last 5/10/20/career window summaries.
- **Stats Explorer:** sortable, searchable table of every qualified batter and
  bowler with column picker, role/team/competition/season/min-balls filters and
  CSV export.
- **All Players (`/players`):** full player directory with filters for the
  supplied IPL 2026 team list, Pakistan players, and players whose last match
  was before 17 November 2024, based on the supplied inactivity data. Its
  Available filter excludes those lists and groups remaining ranked players
  into batters, bowlers and all-rounders.
- **Teams:** every squad that has players with a current team, with XI average,
  batting/bowling/depth/pressure/experience values and league ranks, top
  strengths and weaknesses, and the likely XI. Each profile
  (`/teams/:slug`) shows the ordered best XI with score intervals and
  WK/C/OS flags, league-rank bars for eight dimensions, strengths/weaknesses,
  selection notes, the bench and the full sortable roster.
- **Availability:** status counts, inline status changes for all ranked players,
  current-team editor, multiselect bulk edit, progress counters, an edit dialog
  for notes/`rr_fit`, name search over the full derived index, JSON/CSV
  import-export with a dry-run preview, and JSON backup export/import buttons.
- **Data & Methods:** the active ranking package's score weights, qualification
  criteria, scope and limitations, plus separate supplemental engine diagnostics.
- **Auction Board:** the ten best available batters and bowlers, team exclusion
  using current team with a data fallback, a Removed players drawer showing
  which source decided each exclusion, and a print/PDF view.
- Navbar with light/dark mode (persisted to `localStorage`) and a responsive
  layout with a mobile menu.
- Error, loading and empty states cover a stopped backend or missing rankings.

## Inputs

```
data_rankings/RR_2027_All_838_Players_Master.csv # active supplied ranking source
data_rankings/All_Batter_Rankings.csv   # legacy fallback rankings
data_rankings/All_Bowler_Rankings.csv  # legacy fallback rankings
data_raw/                               # confidential pack, gitignored
data_derived/                           # generated aggregates, deployable
data_derived/scores/                    # engine player tables + metadata, deployable
data_derived/matchups/                   # per-player head-to-head aggregates, deployable
data_derived/teams/player_meta.json      # nationality/overseas map for team profiles, deployable
backend/data/app.db                     # live status store (SQLite, gitignored)
status.json                             # optional legacy seed, imported once
```

When present, `data_rankings/RR_2027_All_838_Players_Master.csv` is the source of
truth for role-specific scores, all-player ranks, qualified ranks and source
metrics. The backend reloads it when changed and does not recompute its rankings.
Without that file, the legacy engine score tables in `data_derived/scores` are used.
The source covers IPL 2022–2026 plus the T20I competitions in the supplied pack;
it does not verify IPL 2027 registration or auction availability.

## Precompute

```bash
python precompute.py
# optional:
python precompute.py --raw data_raw --derived data_derived --rankings data_rankings --data-end 2026-11-01
```

The run takes roughly 30 seconds on the supplied pack and writes:

```
data_derived/
  meta.json
  player_index.json
  recent/{player_id}.json      # one per player, no delivery rows
  stats/
    index.json                 # qualified players for the Stats Explorer
    meta.json                  # build timestamp and thresholds
    {player_id}.json           # per-split batting/bowling aggregates only
```

### Shared data rules

- Exclude super overs (innings 3 and 4).
- Exclude `Mens T20 Emerging Teams Asia Cup 2024` and `Asia Cup Rising Stars 2025`.
- Exclude DLS/shortened matches (non-null `revised_target`).
- Legal ball = `extras_type` not in `wide`, `Overstep`.
- Batter balls faced exclude wides and include no-balls. Bat runs are the pack's
  `runs` column.
- Bowler charged runs = bat runs + `extras1_runs` on `wide`, `Overstep`, `other`.
  Byes, leg-byes and penalties are not charged to the bowler.
- Bowlers are not credited with run-outs, retired-outs or obstruction; credited
  dismissals are caught, bowled, lbw, stumped and hit wicket.
- Pressure is **rule-based and descriptive**, different from the headline
  leverage model:
  1. second innings, overs 16–20, 0.8–2.0 runs needed per remaining ball;
  2. second innings, required rate above 10 with fewer than 5 wickets in hand;
  3. three or more wickets down inside overs 1–6.
- Per-player rates are rounded to one decimal; windows with fewer than 30 balls
  carry `small_sample: true`.

### Recent form payload

`data_derived/recent/{player_id}.json` contains:

- `profile`: name, role guess (`batter` / `bowler` / `both` / `unknown`), latest
  team from the most recent match, first/last match date, matches played, balls
  faced and bowled.
- `matches`: newest-first, at most 25 XI appearances. Each row has competition,
  format, opponent, venue country, innings, a `batting` block and/or a `bowling`
  block (null when the player did not bat/bowl), including pressure-only splits.
- `windows`: `last5`, `last10`, `last20`, `last12m` (cutoff 2025-11-01) and
  `career`, each with matches and batting/bowling aggregates plus pressure-only
  versions.
- `phase`: last 20 matches and career splits for powerplay / middle / death.
- `format_split`: last 20 matches and career splits for IPL / T20I.

`player_index.json` is the compact autocomplete list:
`player_id, name, role, latest_team, last_match_date, ranked_role, ranked_rank`.

## API

| Method | Endpoint | Notes |
| --- | --- | --- |
| GET | `/api/auth/me` | `{authenticated}` for the current session cookie; never cached. |
| POST | `/api/auth/login` | `{password}`; sets the HttpOnly `rr_session` cookie for 12 hours or returns 401. |
| POST | `/api/auth/logout` | Clears the session cookie. |
| GET | `/api/players?role=batter\|bowler&available_only=true&team=&phase=&min_ipl_balls=&current_team_unset=` | Clean ranks computed per role after the availability filter. `team` matches `effective_team` case-insensitively. Each row includes `current_team`, `current_team_type`, `data_team`, `team_source` and `effective_team`. |
| GET | `/api/player/{role}/{player_id}` | Ranking row + status + available derived modules. |
| GET | `/api/summary` | KPI counts, available pool, current-team progress, top 5 available per role, last updated. |
| GET | `/api/shortlist?role=batter\|bowler` | Clean top 10 + next 10 reserves after availability. |
| GET | `/api/derived/{module}/{player_id}` | Precomputed module JSON, path-safe. |
| GET | `/api/search?q=...` | Up to 10 accent-insensitive partial name matches. |
| GET | `/api/recent/{player_id}` | Recent-form JSON + ranking row (if ranked) + status + current team. |
| GET | `/api/stats/{player_id}?role=&split=` | Per-player batting/bowling aggregates for one split, with percentiles and available splits. |
| GET | `/api/stats-index?role=&min_balls=&season=&competition=` | Qualified batters/bowlers for the Stats Explorer; role `both` applies the 100/120-ball thresholds. |
| GET | `/api/matchups/{player_id}?role=batter\|bowler` | Aggregate head-to-head records (batting and bowling sides) for one player; 6+ ball pairs. |
| GET | `/api/teams` | All squads with a current team: XI average, dimension values and league ranks, strengths/weaknesses and the likely XI. 404 until teams are assigned. |
| GET | `/api/teams/{slug}` | One team profile: ordered XI, bench, metrics with ranks, notes and the full roster. |
| GET | `/api/status` | Status map plus allowed statuses, team options, data/typed team lists and team→status suggestions. |
| PUT | `/api/status` | `{name, status?, current_team?, current_team_type?, note?, rr_fit?}`; partial update. |
| PUT | `/api/status/{name}` | Same fields without `name`; returns a status suggestion when a team is set. |
| PUT | `/api/status/bulk` | `{names:[...], current_team?, status?}`; reports how many of the named rows changed. |
| GET | `/api/status/export?format=json\|csv` | Download all statuses; CSV columns are player, role, status, current_team, current_team_type, note, rr_fit. |
| POST | `/api/status/import` | Merge a JSON list/map or `{csv}`; `dry_run` defaults to `true`. |
| GET | `/api/status/history/{name}` | Last 100 change entries for a player. |
| POST | `/api/status/undo/{name}` | Undo the most recent change entry. |
| GET | `/api/scores/meta` | Engine metadata: model metrics, leverage cutoff, shrinkage, bootstrap, sensitivity, reliability and validation summary. |
| GET | `/api/health` | Readiness, missing score files, derived counts, status DB and stats file counts. |

CORS defaults to `http://localhost:5173` and `http://127.0.0.1:5173`; override with
`FRONTEND_ORIGINS` (comma-separated). GET responses are cacheable for 120 seconds;
status/health are `no-store`.

## Availability layer and current team

Edits use SQLite at `backend/data/app.db` by default (override the file path
with `RR_STATUS_DB`). Set `DATABASE_URL` to a managed PostgreSQL connection
string to use PostgreSQL instead; the required driver is installed from
`requirements.txt`. PostgreSQL tables are created at startup, and an empty
status table is seeded from `backend/data/public_status_seed.json` (or legacy
`status.json`) once. Configure `DATABASE_URL` in the hosting provider's
environment settings and redeploy; do not commit credentials. When migrating
existing edits, export a JSON backup from Availability before switching and
import it after the PostgreSQL service is connected.

The status store has three tables:

- `player_status(name PK, status, current_team, current_team_type, note, rr_fit, updated_at)`
- `status_history(id, name, field, old_value, new_value, changed_at)`
- `team_xi(slug PK, players, updated_at)`

Every edit in the UI calls the API and the workspace re-reads the API after
each save (optimistic update with rollback, plus a Saving/Saved/Error
indicator). Use **Export backup** / **Import backup** in Availability to move
the whole status store as JSON; `app.db*` and `status.json` are gitignored.
SQLite on an ephemeral host filesystem can still lose edits on restart; use a
persistent disk or managed PostgreSQL for deployed data.

Allowed statuses: `retained`, `rr_own`, `no_ipl`, `pool`, `unknown`.

- Default is `no_ipl` when `IPL_PLAYED` is `N`, otherwise `unknown`.
- Available means `pool` or `unknown`.
- With `available_only=true`, ineligible players are removed and the remaining
  players are re-ranked by score within their role; the source rank is kept as
  `raw_rank` and `rank`. `clean_rank` is separate.
- `rr_fit` and `note` are free text and are shown on the player page.

### Current team

- `current_team` is a string or `null`; `current_team_type` is `ipl`, `other`
  or `null`. The ten IPL franchises are canonicalised; special values are
  `Released / in auction pool` and `No team / not playing IPL`. Any other team
  is stored as free text (`current_team_type: "other"`).
- A type without a team is meaningless and is cleared. Clearing the team clears
  the type. Team names are limited to 80 characters.
- `effective_team` is `current_team` when set, otherwise the latest team from
  the supplied data; `team_source` is `manual` or `data`. Team filters use this
  fallback, and the Auction Board drawer labels which source decided each
  exclusion.
- Setting a team now applies the matching status automatically unless the same
  request also sends an explicit `status`: RR → `rr_own`, any other IPL franchise
  → `retained`, released → `pool`, no team → `no_ipl`. A free-text team leaves
  the status unchanged. The API also returns the same suggestion for the UI.
- Data teams are never saved automatically. The editor shows them as
  "from data (unverified)" until you press Confirm or choose a value.

### History, bulk and import/export

- Every accepted change appends a row to `status_history` in SQLite, grouped by
  a microsecond `changed_at` stamp; the API keeps the last 100 change entries
  per player. The editor shows the last five and offers "Undo last change".
- Bulk edit applies a current team and/or status to selected rows and reports
  how many changed; unchanged rows are not written.
- `GET /api/status/export` downloads JSON or CSV. Import accepts a JSON list,
  a `{players: ...}` map, a bare name→entry map, or `{csv: "..."}`; it merges
  records and defaults to a dry run so the UI can preview old → new values.
- `role` in exports comes from the supplied rankings where the player is ranked.

Example update:

```bash
curl -X PUT http://localhost:8000/api/status \
  -H "Content-Type: application/json" \
  -d '{"name":"Finn Allen","status":"pool","current_team":"Kolkata Knight Riders","current_team_type":"ipl"}'
```

## Player stats

`precompute.py` writes aggregate-only files to `data_derived/stats/`: one file
per player across 22 splits plus `index.json` (Search/Explorer qualification
counts) and `meta.json`. No delivery rows are written or served.

- **Splits:** career, IPL, T20I, seasons 2022–2026, powerplay/middle/death,
  innings 1/2, vs pace/spin, vs LHB/RHB, pressure/normal, last 5/10/20 matches.
- **Batting:** runs, balls, average, strike rate, dot %, boundary %, singles,
  twos, threes, fours, sixes, balls per boundary, not-outs, dismissals, ducks,
  highest score, start performance, off-side/on-side and dismissal/stroke
  breakdowns.
- **Bowling:** legal balls, overs, runs, wickets, economy, average, strike rate,
  dot %, fours/sixes conceded, wides, no-balls, other extras, byes/leg-byes,
  maidens, best figures, 3/4/5-wicket hauls, wickets by type, speed bands,
  first-over economy, delivery style and side/angle breakdowns.
- **Both:** matches, MOTM, team wins/win %, impact-sub appearances, captain and
  wicketkeeper appearances.
- Ball counts sit beside every cell; cells under 30 balls are marked
  `small_sample` ("small sample"). Percentiles compare against batters with
  ≥100 balls and bowlers with ≥120 legal balls (midrank percentile).
- **Pressure only** filters to the rule-based pressure deliveries described
  above. It is descriptive and does not change the headline composite model.
- No fielding stats are produced: the pack has no reliable fielder IDs.
- API: `/api/stats/{player_id}?role=batter|bowler&split=career` and
  `/api/stats-index?role=batter|bowler|both&min_balls=&season=&competition=`.
  The UI exposes the same data as the Player/Recent Form **Stats** tab and the
  **Stats Explorer** page; definitions and exclusions are duplicated on the
  Data & Methods page.

Verification in `tests/test_stats.py`: a synthetic, hand-verified innings for
legal-ball/extras rules, wicket attribution, maidens, not-outs, ducks, best
figures and hauls, plus a real-match reconciliation (batter runs + extras =
team total; bowler charged runs + byes + leg-byes = team total) that is skipped
when `data_raw/` is absent.

## Head-to-head matchups

`scripts/build_matchups.py` writes `data_derived/matchups/`: one compact file
per player (`{player_id}.json`) plus `index.json`. It reuses the engine's raw
loader, so it reads the same confidential pack and writes only aggregates.

- **Batting side:** balls faced against each bowler (wides excluded), runs,
  outs, strike rate, dot %, boundary %, pressure balls/runs/outs, IPL and T20I
  ball counts.
- **Bowling side:** legal balls to each batter, charged runs, wickets (run-outs
  and retirements excluded), economy, dot %, boundary %, pressure
  balls/runs/wickets, IPL and T20I ball counts.
- Pairs need 6+ balls to be stored; the UI marks pairs under 12 balls as
  "small" and can raise the minimum to 12 or 24. Pressure here is the
  descriptive rule-based split, not the engine leverage flag.
- No delivery rows, match IDs or dates are written. The full output is roughly
  7 MB across 881 players, well under the build-check size limit.
- API: `GET /api/matchups/{player_id}`. The player **Stats → Matchups** tab
  shows both sides with an "As batter" / "As bowler" switch when available.

## Team profiles and the best XI

`backend/teams.py` builds squads live from the status store: every player whose
`current_team` is one of the ten franchises joins that team's profile. Engine
scores, career role/keeper records and the overseas map are joined per player.
`scripts/build_team_meta.py` writes `data_derived/teams/player_meta.json`
(nationality from T20I appearances, with the latest non-IPL national team as a
fallback; 1057 players). Re-run it only if the raw pack changes.

- **XI rules:** source-qualified roles first. The XI needs one
  career wicketkeeper (5+ matches), at least five batting options, at least four
  bowling options and at most four overseas players. Greedy by source score with
  an explicit fill pass when the shape would otherwise break.
- **Order:** batters by career position, then all-rounders, then bowlers. The
  default XI is a data-driven best selection, not a coach's tactical pick.
- **XI editor:** signed-in scouts can replace any slot, reorder the XI and save
  it per team; held in the `team_xi` table. A custom XI
  can be reset to the data-driven selection. The editor warns live when the XI
  loses its keeper or drops below 5 batting / 4 bowling options.
- **Best fit:** for every slot the page suggests the best role replacements,
  drawn only from the team's own squad or the available auction pool. Players
  retained by another franchise, RR-owned players of other squads and no-IPL
  players are never offered. Pool targets are shown for scouting and are
  disabled in the editor until they join the squad.
- **Metrics:** batting = top-5 XI batting-score average; bowling = top-4 XI
  bowling-score average; depth = squad players scoring 50+ with 100+ pressure
  balls; pressure = mean pressure-vs-normal delta; experience = pressure balls
  across the XI; plus death options, powerplay batters and all-rounders. Each is
  ranked 1–10 across the squads; the two best ranks are the strengths and the
  two worst are the weaknesses.
- **API:** `GET /api/teams`, `GET /api/teams/{slug}`, plus
  `PUT /api/teams/{slug}/xi` and `DELETE /api/teams/{slug}/xi` (sign-in
  required). Pages: `/teams` and `/teams/:slug`. Recent form is displayed for
  context only and never changes a score or the XI.

## Tests and build checks

```bash
pytest -q
python scripts/build_check.py
```

The precompute and stats tests use a tiny synthetic pack, never the confidential
data. API tests use synthetic ranking CSVs and a temporary SQLite database, and
one test restarts the app to prove edits survive. The real-match reconciliation
test runs only when `data_raw/` is present locally.

## Method caveats

- Headline scores and ranks come from the supplied master CSV and are not
  recomputed by this repository. The master package does not provide score/rank
  intervals.
- Bowling ranks are not a stable skill hierarchy (low split-half reliability).
- Team labels from the supplied data are the latest observed team, not verified
  contracts. Current-team values set in the Availability workspace override them
  for filters and the Auction Board, but remain unverified scouting judgements.
- Availability comes from public news and is unverified until official IPL
  announcements.
- Recent-form pressure samples are frequently tiny; every recent number is shown
  with its ball count and small-sample marker.
