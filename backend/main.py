"""FastAPI application for the RR pressure dashboard."""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from .auth import (
    COOKIE_NAME,
    SESSION_TTL,
    is_authenticated,
    issue_token,
    password_ok,
    require_auth,
)
from .store import (
    ALLOWED_STATUSES,
    AVAILABLE_STATUSES,
    CURRENT_TEAM_TYPES,
    IPL_TEAMS,
    SPECIAL_CURRENT_TEAMS,
    Store,
    suggest_status_for_team,
    status_suggestion,
)
from .teams import TeamService


class StatusUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    status: str | None = None
    current_team: str | None = None
    current_team_type: str | None = None
    note: str | None = None
    rr_fit: str | None = None


class StatusPatch(BaseModel):
    status: str | None = None
    current_team: str | None = None
    current_team_type: str | None = None
    note: str | None = None
    rr_fit: str | None = None


class BulkStatusUpdate(BaseModel):
    names: list[str] = Field(..., min_length=1, max_length=1000)
    status: str | None = None
    current_team: str | None = None
    current_team_type: str | None = None


class BulkUndoRequest(BaseModel):
    names: list[str] = Field(..., min_length=1, max_length=1000)


class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=200)


class TeamXiRequest(BaseModel):
    players: list[str] = Field(..., min_length=11, max_length=11)


STATUS_PAYLOAD_FIELDS = {"status", "current_team", "current_team_type", "note", "rr_fit"}


def _status_payload(store: Store) -> dict:
    players = store.status_map()
    typed_teams = sorted(
        {
            entry["current_team"]
            for entry in players.values()
            if entry.get("current_team_type") == "other" and entry.get("current_team")
        }
    )
    return {
        "players": players,
        "allowed_statuses": list(ALLOWED_STATUSES),
        "available_statuses": sorted(AVAILABLE_STATUSES),
        "current_team_options": {
            "ipl_teams": list(IPL_TEAMS),
            "special_values": list(SPECIAL_CURRENT_TEAMS),
            "types": list(CURRENT_TEAM_TYPES),
        },
        "team_suggestions": {
            team: suggest_status_for_team(team)
            for team in (*IPL_TEAMS, *SPECIAL_CURRENT_TEAMS)
        },
        "data_teams": store.data_team_values(),
        "typed_teams": typed_teams,
    }


def _update_kwargs(model, fields: set[str]) -> dict:
    kwargs = {}
    if "status" in fields:
        if model.status is None:
            raise HTTPException(status_code=400, detail="status cannot be null")
        kwargs["status"] = model.status
    if "note" in fields:
        kwargs["note"] = "" if model.note is None else model.note
    if "rr_fit" in fields:
        kwargs["rr_fit"] = "" if model.rr_fit is None else model.rr_fit
    if "current_team" in fields:
        kwargs["current_team"] = model.current_team
    if "current_team_type" in fields:
        kwargs["current_team_type"] = model.current_team_type
    return kwargs


def _csv_records(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    records = []
    for row in reader:
        record = {"player": (row.get("player") or row.get("name") or "").strip()}
        for field in ("status", "current_team", "current_team_type", "note", "rr_fit"):
            if field in row:
                value = row.get(field)
                record[field] = None if value == "" else value
        records.append(record)
    return records


def create_app(
    root: str | Path | None = None,
    rankings_dir: str | Path | None = None,
    derived_dir: str | Path | None = None,
    status_file: str | Path | None = None,
    history_file: str | Path | None = None,
    db_file: str | Path | None = None,
) -> FastAPI:
    store = Store(
        root=root,
        rankings_dir=rankings_dir,
        derived_dir=derived_dir,
        status_file=status_file,
        history_file=history_file,
        db_file=db_file,
    )
    teams = TeamService(store)

    app = FastAPI(
        title="Reliability Under Pressure — RR IPL 2027 Auction Scouting",
        version="0.3.0",
        description=(
            "Presentation layer for supplied headline rankings plus derived, "
            "rule-based pressure modules. Rankings are never recomputed here."
        ),
    )
    app.state.store = store

    origins = [
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "PUT", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def cache_headers(request, call_next):
        response = await call_next(request)
        if request.method == "GET" and request.url.path.startswith("/api/"):
            if (
                request.url.path.startswith("/api/status")
                or request.url.path.startswith("/api/auth")
                or request.url.path == "/api/health"
            ):
                response.headers["Cache-Control"] = "no-store"
            else:
                response.headers["Cache-Control"] = "public, max-age=120"
        return response

    @app.get("/")
    def root():
        return {
            "service": "RR pressure dashboard API",
            "docs": "/docs",
            "health": "/api/health",
        }

    @app.get("/api/health")
    def health():
        payload = store.health()
        payload["status_db"] = store.database_available()
        payload["status_history"] = store.history_available()
        payload["stats_files"] = len(list(store.stats_dir.glob("*.json"))) if store.stats_dir.exists() else 0
        return payload

    @app.get("/api/auth/me")
    def auth_me(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return {"authenticated": is_authenticated(request)}

    @app.post("/api/auth/login")
    def auth_login(body: LoginRequest, response: Response):
        if not password_ok(body.password):
            raise HTTPException(status_code=401, detail="Incorrect password.")
        response.set_cookie(
            COOKIE_NAME,
            issue_token(),
            max_age=SESSION_TTL,
            httponly=True,
            samesite="lax",
            path="/",
        )
        return {"authenticated": True}

    @app.post("/api/auth/logout")
    def auth_logout(response: Response):
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"authenticated": False}

    @app.get("/api/players")
    def players(
        role: str | None = Query(default=None, description="batter or bowler"),
        available_only: bool = Query(default=True),
        team: str | None = Query(default=None),
        phase: str | None = Query(default=None),
        min_ipl_balls: int | None = Query(default=None, ge=0),
        min_matches: int | None = Query(default=None, ge=0),
        current_team_unset: bool = Query(default=False),
    ):
        try:
            return store.players(
                role=role,
                available_only=available_only,
                team=team,
                phase=phase,
                min_ipl_balls=min_ipl_balls,
                min_matches=min_matches,
                current_team_unset=current_team_unset,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/player/{role}/{player_id}")
    def player(role: str, player_id: str):
        result = store.player(role, player_id)
        if result is None:
            detail = "Player not found for that role."
            if not store.rankings_loaded:
                detail += " Headline ranking CSVs have not been loaded yet."
            raise HTTPException(status_code=404, detail=detail)
        return result

    @app.get("/api/summary")
    def summary():
        return store.summary()

    @app.get("/api/shortlist")
    def shortlist(role: str = Query(..., description="batter or bowler")):
        try:
            return store.shortlist(role)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/derived/{module}/{player_id}")
    def derived(module: str, player_id: str):
        try:
            payload = store.derived(module, player_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if payload is None:
            raise HTTPException(
                status_code=404, detail="Derived module data not found for this player."
            )
        return payload

    @app.get("/api/search")
    def search(
        q: str = Query(..., min_length=1, max_length=80, description="Partial player name"),
    ):
        return store.search(q, limit=10)

    @app.get("/api/recent/{player_id}")
    def recent(player_id: str):
        payload = store.recent(player_id)
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Recent-form data not found for this player. Run precompute.py "
                    "and check the player id."
                ),
            )
        return payload

    @app.get("/api/scores/meta")
    def scores_meta():
        path = store.derived_dir / "scores" / "meta.json"
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail="Engine metadata not found. Run python engine/run_all.py.",
            )
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - surfaced via API
            raise HTTPException(status_code=500, detail=f"Could not read engine metadata: {exc}")

    @app.get("/api/teams")
    def teams_overview():
        payload = teams.overview()
        if not payload["teams"]:
            raise HTTPException(
                status_code=404,
                detail="No teams found. Assign current teams in the Availability workspace first.",
            )
        return payload

    @app.get("/api/teams/{slug}")
    def team_detail(slug: str):
        payload = teams.detail(slug)
        if payload is None:
            raise HTTPException(status_code=404, detail="Team not found.")
        return payload

    @app.put("/api/teams/{slug}/xi")
    def team_xi_save(
        slug: str,
        body: TeamXiRequest,
        _auth: None = Depends(require_auth),
    ):
        try:
            return teams.save_xi(slug, body.players)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/teams/{slug}/xi")
    def team_xi_reset(slug: str, _auth: None = Depends(require_auth)):
        try:
            return teams.reset_xi(slug)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/stats-index")
    def stats_index(
        role: str | None = Query(default=None, pattern="^(batter|bowler|both)$"),
        min_balls: int = Query(default=0, ge=0),
        season: str | None = Query(default=None),
        competition: str | None = Query(default=None),
        team: str | None = Query(default=None),
    ):
        return store.stats_index(
            role=role,
            min_balls=min_balls,
            season=season,
            competition=competition,
            team=team,
        )

    @app.get("/api/stats/{player_id}")
    def stats_player(
        player_id: str,
        role: str | None = Query(default=None, pattern="^(batter|bowler)$"),
        split: str = Query(default="career"),
    ):
        payload = store.stats_player(player_id, split=split)
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Stats not found for this player. Run precompute.py to build "
                    "data_derived/stats."
                ),
            )
        payload["requested_role"] = role
        return payload

    @app.get("/api/matchups/{player_id}")
    def matchups_player(
        player_id: str,
        role: str | None = Query(default=None, pattern="^(batter|bowler)$"),
    ):
        payload = store.matchups_player(player_id)
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Matchups not found for this player. Run "
                    "python scripts/build_matchups.py to build data_derived/matchups."
                ),
            )
        payload["requested_role"] = role
        return payload

    @app.get("/api/status")
    def get_status():
        return _status_payload(store)

    @app.put("/api/status")
    def put_status(update: StatusUpdate, _auth: None = Depends(require_auth)):
        fields = update.model_fields_set - {"name"}
        if not fields & STATUS_PAYLOAD_FIELDS:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Provide at least one of status, current_team, current_team_type, "
                    "note or rr_fit."
                ),
            )
        try:
            store.update_status(name=update.name, **_update_kwargs(update, fields))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload = _status_payload(store)
        if "current_team" in fields or "current_team_type" in fields:
            entry = store.status_map().get(update.name.strip(), {})
            payload["suggestion"] = status_suggestion(entry.get("current_team"))
        return payload

    @app.put("/api/status/bulk")
    def put_status_bulk(update: BulkStatusUpdate, _auth: None = Depends(require_auth)):
        fields = update.model_fields_set - {"names"}
        if not fields & STATUS_PAYLOAD_FIELDS:
            raise HTTPException(
                status_code=400,
                detail="Provide status or current_team for a bulk edit.",
            )
        kwargs = {}
        if "status" in fields:
            if update.status is None:
                raise HTTPException(status_code=400, detail="status cannot be null")
            kwargs["status"] = update.status
        if "current_team" in fields:
            kwargs["current_team"] = update.current_team
        if "current_team_type" in fields:
            kwargs["current_team_type"] = update.current_team_type
        try:
            return store.bulk_update(names=update.names, **kwargs)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/status/export")
    def export_status(
        fmt: str = Query(default="json", alias="format", pattern="^(json|csv)$"),
        _auth: None = Depends(require_auth),
    ):
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if fmt == "csv":
            return Response(
                content="\ufeff" + store.export_csv(),
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="rr-status-{stamp}.csv"',
                    "Cache-Control": "no-store",
                },
            )
        payload = json.dumps(store.export_payload(), ensure_ascii=False, indent=2)
        return Response(
            content=payload,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="rr-status-{stamp}.json"',
                "Cache-Control": "no-store",
            },
        )

    @app.post("/api/status/import")
    def import_status(
        payload: Any = Body(...),
        dry_run: bool | None = Query(default=None),
        _auth: None = Depends(require_auth),
    ):
        body_dry_run = None
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            if "csv" in payload:
                records = _csv_records(str(payload.get("csv") or ""))
            else:
                body_dry_run = payload.get("dry_run")
                data = payload.get("players", payload.get("records", payload.get("data")))
                if data is None:
                    data = {
                        key: value
                        for key, value in payload.items()
                        if key not in {"dry_run", "exported_at", "roles"}
                    }
                if isinstance(data, dict):
                    records = []
                    for name, entry in data.items():
                        if not isinstance(entry, dict):
                            raise HTTPException(
                                status_code=400,
                                detail=f"Import entry for '{name}' must be an object",
                            )
                        records.append({"player": name, **entry})
                elif isinstance(data, list):
                    records = data
                else:
                    raise HTTPException(
                        status_code=400, detail="Import payload has no player records"
                    )
        else:
            raise HTTPException(status_code=400, detail="Import payload must be JSON")
        use_dry_run = dry_run if dry_run is not None else (
            bool(body_dry_run) if body_dry_run is not None else True
        )
        try:
            return store.import_status(records, dry_run=use_dry_run)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/status/history/{name}")
    def status_history(name: str):
        entries = store.history_for(name)
        return {"player": name, "entries": entries, "last": entries[-5:]}

    @app.post("/api/status/undo/{name}")
    def status_undo(name: str, _auth: None = Depends(require_auth)):
        try:
            result = store.undo_last(name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload = _status_payload(store)
        payload["undone"] = result["undone"]
        return payload

    @app.post("/api/status/undo-bulk")
    def status_undo_bulk(
        body: BulkUndoRequest,
        _auth: None = Depends(require_auth),
    ):
        try:
            result = store.undo_many(body.names)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload = _status_payload(store)
        payload["undone"] = result["undone"]
        payload["skipped"] = result["skipped"]
        payload["summary"] = result["summary"]
        return payload

    @app.put("/api/status/{name}")
    def put_status_path(
        name: str,
        update: StatusPatch,
        _auth: None = Depends(require_auth),
    ):
        fields = update.model_fields_set
        if not fields & STATUS_PAYLOAD_FIELDS:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Provide at least one of status, current_team, current_team_type, "
                    "note or rr_fit."
                ),
            )
        try:
            store.update_status(name=name, **_update_kwargs(update, fields))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload = _status_payload(store)
        if "current_team" in fields or "current_team_type" in fields:
            entry = store.status_map().get(name.strip(), {})
            payload["suggestion"] = status_suggestion(entry.get("current_team"))
        return payload

    return app


app = create_app()
