"""Team profiles and best-XI selection from engine scores and derived stats."""

from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import mean

from .store import IPL_TEAMS, Store

OVERSEAS_CAP = 4
MIN_ROLE_BALLS = 50
DIMENSIONS = (
    ("batting", "Batting"),
    ("bowling", "Bowling"),
    ("depth", "Squad depth"),
    ("pressure", "Pressure edge"),
    ("experience", "Experience"),
    ("death_options", "Death bowling"),
    ("powerplay_batters", "Powerplay batting"),
    ("all_rounders", "All-round balance"),
)
SPIN_STYLES = {
    "Arm ball",
    "Off Break",
    "Leg Break",
    "Googly",
    "Flipper",
    "Carrom",
    "Slider",
    "Chinaman",
    "Orthodox",
}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _round(value, digits=1):
    return None if value is None else round(float(value), digits)


def _mean(values):
    cleaned = [float(v) for v in values if v is not None]
    return mean(cleaned) if cleaned else None


class TeamService:
    def __init__(self, store: Store):
        self.store = store
        self._career_cache: dict[str, tuple[int, dict]] = {}
        self._meta_cache: tuple[int, dict] | None = None
        self._index_cache: tuple[int, dict] | None = None

    # ------------------------------------------------------------------
    # Derived inputs
    # ------------------------------------------------------------------

    @property
    def meta_path(self) -> Path:
        return self.store.derived_dir / "teams" / "player_meta.json"

    def _meta(self) -> dict:
        path = self.meta_path
        if not path.exists():
            return {}
        stamp = path.stat().st_mtime_ns
        if self._meta_cache and self._meta_cache[0] == stamp:
            return self._meta_cache[1]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        players = payload.get("players") if isinstance(payload, dict) else None
        players = players if isinstance(players, dict) else {}
        self._meta_cache = (stamp, players)
        return players

    def _index_names(self) -> dict[str, str]:
        path = self.store.derived_dir / "player_index.json"
        if not path.exists():
            return {}
        stamp = path.stat().st_mtime_ns
        if self._index_cache and self._index_cache[0] == stamp:
            return self._index_cache[1]
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        names: dict[str, str] = {}
        for entry in entries if isinstance(entries, list) else []:
            name = str(entry.get("name") or "").strip()
            pid = entry.get("player_id")
            if name and pid is not None:
                names.setdefault(name, str(pid))
        self._index_cache = (stamp, names)
        return names

    def _career(self, player_id: str | None) -> dict:
        if not player_id or not str(player_id).isdigit():
            return {}
        pid = str(player_id)
        path = self.store.stats_dir / f"{pid}.json"
        if not path.exists():
            return {}
        stamp = path.stat().st_mtime_ns
        cached = self._career_cache.get(pid)
        if cached and cached[0] == stamp:
            return cached[1]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        split = (payload.get("splits") or {}).get("career") or {}
        batting = split.get("batting") or {}
        bowling = split.get("bowling") or {}
        career = {
            "wk_matches": max(
                int(batting.get("wk_matches") or 0),
                int(bowling.get("wk_matches") or 0),
            ),
            "captain_matches": max(
                int(batting.get("captain_matches") or 0),
                int(bowling.get("captain_matches") or 0),
            ),
            "position": batting.get("position"),
            "batting_balls": int(batting.get("balls") or 0),
            "strike_rate": batting.get("strike_rate"),
            "batting_dot_pct": batting.get("dot_pct"),
            "boundary_pct": batting.get("boundary_pct"),
            "bowling_balls": int(bowling.get("legal_balls") or 0),
            "economy": bowling.get("economy"),
            "bowling_dot_pct": bowling.get("dot_pct"),
            "wickets": int(bowling.get("wickets") or 0),
            "bowl_type": self._bowl_type(bowling),
        }
        self._career_cache[pid] = (stamp, career)
        return career

    @staticmethod
    def _bowl_type(bowling: dict) -> str | None:
        if not bowling:
            return None
        speed = (bowling.get("speed") or {}).get("plausible_average")
        if speed is not None:
            if float(speed) >= 105:
                return "Pace"
            if float(speed) < 95:
                return "Spin"
        style = bowling.get("style") or {}
        total = sum(int(v.get("balls") or 0) for v in style.values())
        if total:
            spin = sum(
                int(v.get("balls") or 0)
                for label, v in style.items()
                if label in SPIN_STYLES
            )
            return "Spin" if spin / total >= 0.4 else "Pace"
        return None

    # ------------------------------------------------------------------
    # Player rows
    # ------------------------------------------------------------------

    def _player_row(self, name: str, status: dict, bat: dict | None, bowl: dict | None) -> dict:
        index_names = self._index_names()
        pid = str(
            (bat or {}).get("player_id")
            or (bowl or {}).get("player_id")
            or index_names.get(name)
            or ""
        )
        career = self._career(pid)
        meta = self._meta().get(pid) or {}
        batting_balls = int((bat or {}).get("pressure_balls") or 0)
        bowling_balls = int((bowl or {}).get("pressure_balls") or 0)
        is_batter = bool(bat) and batting_balls >= MIN_ROLE_BALLS
        is_bowler = bool(bowl) and bowling_balls >= MIN_ROLE_BALLS
        if is_batter and is_bowler:
            primary = bat if bat["score"] >= bowl["score"] else bowl
        elif is_batter:
            primary = bat
        elif is_bowler:
            primary = bowl
        elif (bat or {}).get("score") is not None and (bowl or {}).get("score") is not None:
            primary = bat if bat["score"] >= bowl["score"] else bowl
        else:
            primary = bat or bowl or {}
        score = primary.get("score")
        roles = []
        if is_batter:
            roles.append(str(bat.get("role") or "Batter"))
        if is_bowler:
            roles.append(str(bowl.get("role") or "Bowler"))
        return {
            "name": name,
            "player_id": pid or None,
            "status": status.get("status"),
            "current_team": status.get("current_team"),
            "score": score,
            "rating": primary.get("rating100"),
            "role_fit": primary.get("role_fit"),
            "risk": primary.get("risk"),
            "best_use": primary.get("role") or (roles[0] if roles else None),
            "matches": primary.get("matches"),
            "experience": primary.get("experience"),
            "experience_marks": primary.get("experience_marks"),
            "average": primary.get("career_average"),
            "career_sr": primary.get("career_sr"),
            "career_fours": primary.get("career_fours"),
            "career_sixes": primary.get("career_sixes"),
            "balls_per_boundary": primary.get("balls_per_boundary"),
            "career_innings": primary.get("career_innings"),
            "career_runs": primary.get("career_runs"),
            "career_wickets": primary.get("career_wickets"),
            "career_econ": primary.get("career_econ"),
            "career_dot_pct": primary.get("career_dot_pct"),
            "selectable": is_batter or is_bowler,
            "score_lo": primary.get("score_lo"),
            "score_hi": primary.get("score_hi"),
            "all_rank": primary.get("all_rank"),
            "batting_score": (bat or {}).get("score"),
            "bowling_score": (bowl or {}).get("score"),
            "batting_rating": (bat or {}).get("rating100"),
            "bowling_rating": (bowl or {}).get("rating100"),
            "batting_rank": (bat or {}).get("all_rank"),
            "bowling_rank": (bowl or {}).get("all_rank"),
            "pressure_balls": max(batting_balls, bowling_balls),
            "batting_pressure_balls": batting_balls,
            "bowling_pressure_balls": bowling_balls,
            "delta": primary.get("delta"),
            "form2026": primary.get("form2026_impact100"),
            "batting_role": (bat or {}).get("role"),
            "bowling_role": (bowl or {}).get("role"),
            "dominant_phase": primary.get("dominant_phase"),
            "roles": roles,
            "is_batter": is_batter,
            "is_bowler": is_bowler,
            "bat_option": bool(bat) and batting_balls >= 30,
            "bowl_option": bool(bowl) and bowling_balls >= 30,
            "is_all_rounder": is_batter and is_bowler,
            "wk": int(career.get("wk_matches") or 0) >= 5,
            "wk_matches": career.get("wk_matches") or 0,
            "captain": int(career.get("captain_matches") or 0) >= 5,
            "position": career.get("position"),
            "strike_rate": (bat or {}).get("strike_rate") if bat else career.get("strike_rate"),
            "economy": (bowl or {}).get("economy") if bowl else career.get("economy"),
            "boundary_pct": career.get("boundary_pct"),
            "dot_pct": (bat or {}).get("dots_pct") if bat else (bowl or {}).get("dots_pct"),
            "wickets": (bowl or {}).get("wickets"),
            "bowl_type": career.get("bowl_type"),
            "overseas": bool(meta.get("overseas")),
            "country": meta.get("country"),
            "player_type": "Batter" if is_batter and not is_bowler else (
                "Bowler" if is_bowler and not is_batter else (
                    "All-rounder" if is_batter and is_bowler else "Squad"
                )
            ),
        }

    # ------------------------------------------------------------------
    # XI selection
    # ------------------------------------------------------------------

    def _greedy_xi(self, candidates: list[dict], keeper: dict | None) -> list[dict]:
        selected: list[dict] = []
        overseas = 0

        def add(player: dict) -> bool:
            nonlocal overseas
            if player in selected or len(selected) >= 11:
                return False
            if player["overseas"] and overseas >= OVERSEAS_CAP:
                return False
            selected.append(player)
            overseas += int(player["overseas"])
            return True

        if keeper:
            add(keeper)
        for player in sorted(
            (p for p in candidates if p["is_bowler"]),
            key=lambda p: -(self._fit_score(p, "bowling") or 0),
        ):
            if sum(1 for p in selected if p["is_bowler"]) >= 4:
                break
            add(player)
        for player in sorted(
            (p for p in candidates if p["is_batter"]),
            key=lambda p: -(self._fit_score(p, "batting") or 0),
        ):
            if sum(1 for p in selected if p["is_batter"]) >= 5:
                break
            add(player)
        for player in sorted(
            candidates,
            key=lambda p: -(
                p.get("rating") if p.get("rating") is not None else (p["score"] or 0)
            ),
        ):
            if len(selected) >= 11:
                break
            add(player)
        return selected

    def _select_xi(self, roster: list[dict]) -> tuple[list[dict], dict]:
        qualified = [p for p in roster if p["score"] is not None and p["selectable"]]
        scored = [p for p in roster if p["score"] is not None]
        candidates = qualified if len(qualified) >= 11 else scored
        keepers = [p for p in candidates if p["wk"]]
        keeper_options = sorted(
            keepers,
            key=lambda p: -(
                p.get("rating") if p.get("rating") is not None else (p["score"] or 0)
            ),
        )[:4] or [None]
        best: list[dict] = []
        for keeper in keeper_options:
            xi = self._greedy_xi(candidates, keeper)
            if not best or sum(p.get("rating") or 0 for p in xi) > sum(
                p.get("rating") or 0 for p in best
            ):
                best = xi
        added: list[dict] = []
        if len(best) < 11:
            selected = {p["name"] for p in best}
            overseas = sum(1 for p in best if p["overseas"])
            while len(best) < 11:
                bat_options = sum(1 for p in best if p["bat_option"])
                bowl_options = sum(1 for p in best if p["bowl_option"])
                pool = sorted(
                    scored,
                    key=lambda p: -(
                        p.get("rating")
                        if p.get("rating") is not None
                        else (p["score"] or 0)
                    ),
                )
                pick = None
                if bat_options < 5:
                    pick = next(
                        (
                            p
                            for p in pool
                            if p["name"] not in selected
                            and p["bat_option"]
                            and not (p["overseas"] and overseas >= OVERSEAS_CAP)
                        ),
                        None,
                    )
                if pick is None and bowl_options < 4:
                    pick = next(
                        (
                            p
                            for p in pool
                            if p["name"] not in selected
                            and p["bowl_option"]
                            and not (p["overseas"] and overseas >= OVERSEAS_CAP)
                        ),
                        None,
                    )
                if pick is None:
                    pick = next(
                        (
                            p
                            for p in pool
                            if p["name"] not in selected
                            and not (p["overseas"] and overseas >= OVERSEAS_CAP)
                        ),
                        None,
                    )
                if pick is None:
                    break
                best.append(pick)
                added.append(pick)
                selected.add(pick["name"])
                overseas += int(pick["overseas"])
        best = self._order_xi(best)
        return best, {
            "has_keeper": any(p["wk"] for p in best),
            "batters": sum(1 for p in best if p["bat_option"]),
            "bowlers": sum(1 for p in best if p["bowl_option"]),
            "overseas": sum(1 for p in best if p["overseas"]),
            "scored_candidates": len(candidates),
            "scored_total": len(scored),
            "low_sample": sum(1 for p in candidates if not p["selectable"]) + len(added),
        }

    @staticmethod
    def _order_xi(xi: list[dict]) -> list[dict]:
        def key(player: dict):
            if player["is_batter"]:
                return (
                    0,
                    player.get("position") or 6,
                    -(player.get("batting_rating") or 0),
                )
            if player["is_bowler"]:
                return (2, 0, -(player.get("bowling_rating") or 0))
            return (1, 0, -(player.get("rating") or 0))

        ordered = sorted(xi, key=key)
        return [{**player, "order": index + 1} for index, player in enumerate(ordered)]

    @staticmethod
    def _shape(xi: list[dict], roster: list[dict]) -> dict:
        return {
            "has_keeper": any(p["wk"] for p in xi),
            "batters": sum(1 for p in xi if p["bat_option"]),
            "bowlers": sum(1 for p in xi if p["bowl_option"]),
            "overseas": sum(1 for p in xi if p["overseas"]),
            "scored_candidates": sum(
                1 for p in roster if p["score"] is not None and p["selectable"]
            ),
            "scored_total": sum(1 for p in roster if p["score"] is not None),
            "low_sample": sum(1 for p in xi if not p["selectable"]),
        }

    @staticmethod
    def _primary_role(player: dict) -> str:
        if player["wk"]:
            return "keeping"
        if player["is_batter"]:
            return "batting"
        if player["is_bowler"]:
            return "bowling"
        return "batting"

    @staticmethod
    def _fit_score(player: dict, role: str):
        if role == "bowling":
            keys = ("bowling_rating", "rating", "bowling_score", "score")
        else:
            keys = ("batting_rating", "rating", "batting_score", "score")
        for key in keys:
            value = player.get(key)
            if value is not None:
                return value
        return None

    def _pool_rows(self) -> list[dict]:
        """Top available auction-pool players, one detailed row each.

        Best-fit suggestions may only come from the team's own squad or from this
        available pool; retained players from other teams are never offered.
        """
        payload = self.store.players(available_only=True)
        available = [
            row
            for row in payload.get("players", [])
            if row.get("available") and not row.get("current_team")
        ]
        rankings = self.store.rankings()
        batter_map = {
            row["name"]: row for row in rankings if row["player_type"] == "batter"
        }
        bowler_map = {
            row["name"]: row for row in rankings if row["player_type"] == "bowler"
        }
        statuses = self.store.status_map()
        rows: list[dict] = []
        seen: set[str] = set()
        for role in ("batter", "bowler"):
            top = sorted(
                (row for row in available if row["player_type"] == role),
                key=lambda row: -(
                    row.get("rating100")
                    if row.get("rating100") is not None
                    else (row.get("score") or 0)
                ),
            )[:20]
            for row in top:
                name = row["name"]
                if name in seen:
                    continue
                seen.add(name)
                player = self._player_row(
                    name,
                    statuses.get(name, {}),
                    batter_map.get(name),
                    bowler_map.get(name),
                )
                if player["score"] is not None:
                    rows.append(
                        {**player, "status": row.get("status"), "source": "pool"}
                    )
        return rows

    def _fit_options(
        self, roster: list[dict], xi: list[dict], pool_rows: list[dict]
    ) -> dict:
        picked = {p["name"] for p in xi}
        options = {}
        for slot in xi:
            role = self._primary_role(slot)
            if role == "keeping":
                squad = [p for p in roster if p["wk"]]
                pool = [p for p in pool_rows if p["wk"]]
            elif role == "bowling":
                squad = [p for p in roster if p["is_bowler"]]
                pool = [p for p in pool_rows if p["is_bowler"]]
            else:
                squad = [p for p in roster if p["is_batter"]]
                pool = [p for p in pool_rows if p["is_batter"]]
            squad = [
                {**p, "source": "squad"}
                for p in squad
                if p["name"] not in picked and p["score"] is not None
            ]
            pool = [p for p in pool if p["name"] not in picked]
            combined = squad + pool
            combined.sort(
                key=lambda p: (
                    -(self._fit_score(p, role) or 0),
                    -(p["score"] or 0),
                )
            )
            options[str(slot["player_id"])] = {
                "role": role,
                "players": [
                    {**p, "fit_score": _round(self._fit_score(p, role))}
                    for p in combined[:5]
                ],
            }
        return options

    def _pool_fit(self, pool_rows: list[dict]) -> dict:
        roles = {
            "keeping": lambda p: p["wk"],
            "batting": lambda p: p["is_batter"],
            "bowling": lambda p: p["is_bowler"],
        }
        payload = {}
        for role, match in roles.items():
            rows = [p for p in pool_rows if match(p)]
            rows.sort(key=lambda p: -(self._fit_score(p, role) or 0))
            payload[role] = [
                {**p, "fit_score": _round(self._fit_score(p, role))}
                for p in rows[:5]
            ]
        return payload

    # ------------------------------------------------------------------
    # Team profiles
    # ------------------------------------------------------------------

    def _metrics(self, roster: list[dict], xi: list[dict], shape: dict) -> dict:
        def top_mean(field, count):
            values = sorted(
                (p[field] for p in xi if p.get(field) is not None),
                reverse=True,
            )
            return _mean(values[:count])

        batting = top_mean("batting_rating", 5)
        bowling = top_mean("bowling_rating", 4)
        depth = sum(
            1
            for p in roster
            if p.get("rating") is not None
            and p["rating"] >= 60
            and p["pressure_balls"] >= 100
        )
        pressure = _mean(p.get("delta") for p in xi)
        experience = sum(int(p.get("matches") or 0) for p in xi)
        death = sum(
            1
            for p in xi
            if p["is_bowler"]
            and "death" in f"{p.get('bowling_role') or ''} {p.get('dominant_phase') or ''}".lower()
        )
        powerplay = sum(
            1
            for p in xi
            if p["is_batter"]
            and "powerplay" in f"{p.get('batting_role') or ''} {p.get('dominant_phase') or ''}".lower()
        )
        all_rounders = sum(1 for p in xi if p["is_all_rounder"])
        return {
            "batting": _round(batting),
            "bowling": _round(bowling),
            "depth": depth,
            "pressure": _round(pressure),
            "experience": experience,
            "death_options": death,
            "powerplay_batters": powerplay,
            "all_rounders": all_rounders,
            "xi_average": _round(_mean(p.get("rating") for p in xi)),
            "xi_top": _round(max((p.get("rating") or 0 for p in xi), default=None)),
            "overseas": shape["overseas"],
            "keeper": next((p["name"] for p in xi if p["wk"]), None),
            "scored": shape["scored_total"],
            "unscored": len(roster) - shape["scored_total"],
            "low_sample": shape["low_sample"],
            "batters": shape["batters"],
            "bowlers": shape["bowlers"],
            "shape_ok": shape["has_keeper"] and shape["batters"] >= 5 and shape["bowlers"] >= 4,
        }

    def _notes(self, metrics: dict, roster: list[dict]) -> list[str]:
        notes = []
        if metrics["unscored"]:
            notes.append(
                f"{metrics['unscored']} squad player(s) have no engine score and were not considered for the XI."
            )
        if metrics.get("low_sample"):
            notes.append(
                f"{metrics['low_sample']} XI candidate(s) fall below the 50-pressure-ball role minimum, so their scores carry wide uncertainty."
            )
        if not metrics["keeper"]:
            notes.append("No career wicketkeeper with 5+ appearances in the squad; the XI has no specialist keeper.")
        if metrics["batters"] < 5 or metrics["bowlers"] < 4:
            notes.append(
                f"Scored squad cannot fill the 5-batter/4-bowler shape (picked {metrics['batters']} batting and {metrics['bowlers']} bowling options)."
            )
        if metrics["overseas"] >= OVERSEAS_CAP:
            notes.append("XI uses the full four-overseas quota; any injury replacement must be domestic or a swap.")
        return notes

    def profiles(self) -> list[dict]:
        rankings = self.store.rankings()
        batter_map = {
            row["name"]: row for row in rankings if row["player_type"] == "batter"
        }
        bowler_map = {
            row["name"]: row for row in rankings if row["player_type"] == "bowler"
        }
        statuses = self.store.status_map()

        profiles = []
        for team in IPL_TEAMS:
            names = sorted(
                name
                for name, status in statuses.items()
                if status.get("current_team") == team
            )
            roster = [
                self._player_row(
                    name,
                    statuses.get(name, {}),
                    batter_map.get(name),
                    bowler_map.get(name),
                )
                for name in names
            ]
            slug = slugify(team)
            custom = self.store.custom_xi(slug)
            xi = None
            custom_applied = False
            if custom:
                by_name = {p["name"]: p for p in roster}
                names = custom["players"]
                picks = [by_name[name] for name in names if name in by_name]
                if (
                    len(names) == 11
                    and len(picks) == 11
                    and len({p["name"] for p in picks}) == 11
                ):
                    xi = [{**p, "order": index + 1} for index, p in enumerate(picks)]
                    shape = self._shape(xi, roster)
                    custom_applied = True
            if xi is None:
                xi, shape = self._select_xi(roster)
            metrics = self._metrics(roster, xi, shape)
            selected = {p["name"] for p in xi}
            bench = [
                {**p, "order": index + 1}
                for index, p in enumerate(
                    sorted(
                        (p for p in roster if p["name"] not in selected and p["score"] is not None),
                        key=lambda p: -(
                            p.get("rating")
                            if p.get("rating") is not None
                            else (p.get("score") or 0)
                        ),
                    )[:6]
                )
            ]
            profiles.append(
                {
                    "name": team,
                    "slug": slug,
                    "roster": sorted(
                        roster,
                        key=lambda p: (
                            -(p.get("rating") if p.get("rating") is not None else -1),
                            p["name"],
                        ),
                    ),
                    "xi": xi,
                    "xi_source": "custom" if custom_applied else "auto",
                    "xi_updated_at": custom["updated_at"] if custom_applied else None,
                    "bench": bench,
                    "metrics": metrics,
                    "notes": self._notes(metrics, roster),
                }
            )

        for key, _ in DIMENSIONS:
            ordered = sorted(
                (p for p in profiles if p["metrics"].get(key) is not None),
                key=lambda p: p["metrics"][key],
                reverse=True,
            )
            for rank, profile in enumerate(ordered, start=1):
                profile["metrics"].setdefault("ranks", {})[key] = rank

        for profile in profiles:
            profile["strengths"], profile["weaknesses"] = self._narrative(profile)
        return profiles

    @staticmethod
    def _narrative(profile: dict) -> tuple[list[dict], list[dict]]:
        metrics = profile["metrics"]
        ranks = metrics.get("ranks") or {}
        items = []
        for key, label in DIMENSIONS:
            value = metrics.get(key)
            if value is None or key not in ranks:
                continue
            items.append(
                {
                    "key": key,
                    "label": label,
                    "value": value,
                    "rank": ranks[key],
                    "text": TeamService._metric_text(key, value),
                }
            )
        ordered = sorted(items, key=lambda item: item["rank"])
        strengths = ordered[:2]
        weaknesses = list(reversed(ordered))[:2]
        return strengths, weaknesses

    @staticmethod
    def _metric_text(key: str, value) -> str:
        if key == "batting":
            return f"Top-5 XI batting rating average {value:.1f}/100"
        if key == "bowling":
            return f"Top-4 XI bowling rating average {value:.1f}/100"
        if key == "depth":
            return f"{value} squad players rated 60+/100 with 100+ pressure balls"
        if key == "pressure":
            return f"Mean pressure delta {value:+.1f} per 100 balls"
        if key == "experience":
            return f"{int(value):,} combined matches across the XI"
        if key == "death_options":
            return f"{value} death-phase bowling option(s) in the XI"
        if key == "powerplay_batters":
            return f"{value} powerplay-phase batter(s) in the XI"
        if key == "all_rounders":
            return f"{value} dual-threat all-rounder(s) in the XI"
        return str(value)

    # ------------------------------------------------------------------
    # Public payloads
    # ------------------------------------------------------------------

    def overview(self) -> dict:
        profiles = self.profiles()
        teams = []
        for profile in profiles:
            metrics = profile["metrics"]
            teams.append(
                {
                    "name": profile["name"],
                    "slug": profile["slug"],
                    "roster_count": len(profile["roster"]),
                    "scored_count": metrics["scored"],
                    "xi_average": metrics["xi_average"],
                    "batting": metrics["batting"],
                    "bowling": metrics["bowling"],
                    "depth": metrics["depth"],
                    "pressure": metrics["pressure"],
                    "experience": metrics["experience"],
                    "overseas": metrics["overseas"],
                    "ranks": metrics.get("ranks", {}),
                    "strengths": profile["strengths"],
                    "weaknesses": profile["weaknesses"],
                    "xi": [
                        {
                            "order": p["order"],
                            "name": p["name"],
                            "player_id": p["player_id"],
                            "role": p["player_type"],
                            "score": p["score"],
                            "overseas": p["overseas"],
                            "wk": p["wk"],
                        }
                        for p in profile["xi"]
                    ],
                }
            )
        return {
            "ready": bool(teams),
            "teams": teams,
            "meta": self._rules_meta(),
        }

    def detail(self, slug: str) -> dict | None:
        for profile in self.profiles():
            if profile["slug"] == slug:
                pool_rows = self._pool_rows()
                return {
                    "ready": True,
                    **profile,
                    "fit_options": self._fit_options(
                        profile["roster"], profile["xi"], pool_rows
                    ),
                    "pool_fit": self._pool_fit(pool_rows),
                    "meta": self._rules_meta(),
                }
        return None

    def save_xi(self, slug: str, players: list[str]) -> dict:
        profile = next((p for p in self.profiles() if p["slug"] == slug), None)
        if profile is None:
            raise LookupError("Unknown team.")
        names = [str(name).strip() for name in players if str(name).strip()]
        if len(names) != 11:
            raise ValueError("The XI must contain exactly 11 players.")
        if len(set(names)) != 11:
            raise ValueError("A player can only appear once in the XI.")
        roster_names = {p["name"] for p in profile["roster"]}
        unknown = [name for name in names if name not in roster_names]
        if unknown:
            raise ValueError(
                "Not in this squad: " + ", ".join(unknown[:3]) + ("…" if len(unknown) > 3 else "")
            )
        self.store.set_custom_xi(slug, names)
        return self.detail(slug)

    def reset_xi(self, slug: str) -> dict:
        if not any(p["slug"] == slug for p in self.profiles()):
            raise LookupError("Unknown team.")
        self.store.clear_custom_xi(slug)
        return self.detail(slug)

    def _rules_meta(self) -> dict:
        return {
            "overseas_cap": OVERSEAS_CAP,
            "min_role_pressure_balls": MIN_ROLE_BALLS,
            "nationality_ready": self.meta_path.exists(),
            "shape": "1 wicketkeeper, at least 5 batting options and 4 bowling options, maximum 4 overseas",
            "source": "engine composite scores; career stats for roles and wicketkeeping; T20I team mapping for nationality",
            "caveat": "The XI is a data-driven best selection, not a coach's tactical pick. Recent form is shown for context and never changes a score.",
        }


def team_service(store: Store) -> TeamService:
    return TeamService(store)
