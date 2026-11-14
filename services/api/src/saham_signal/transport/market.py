"""Contract-v1 market queries and conservative websocket resynchronization."""

import asyncio
import hmac
import json
import re
from dataclasses import replace
from datetime import timedelta
from email.utils import format_datetime
from typing import Annotated, Any, Literal
from uuid import uuid4

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket
from jsonschema import ValidationError
from starlette.websockets import WebSocketDisconnect

from saham_signal.application.market import (
    FixtureMarket,
    MarketNotFound,
    MarketScope,
    MarketUnavailable,
    validate,
)
from saham_signal.application.preferences import (
    PreferenceConflict,
    PreferenceStore,
    eligibility,
    fees_current,
    validate_preference,
)
from saham_signal.config import Settings
from saham_signal.transport.errors import ErrorCode


def market_router(
    config: Settings, market: FixtureMarket, preferences: PreferenceStore
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def authorize(cookie: str | None) -> MarketScope:
        if not config.market_fixture_enabled:
            raise HTTPException(503)
        expected = config.market_fixture_token
        if (
            not expected
            or not cookie
            or not hmac.compare_digest(cookie.encode(), expected.get_secret_value().encode())
        ):
            raise HTTPException(401)
        return MarketScope(
            account=config.pilot_account_id or "fixture-pilot",
            mode=config.app_mode,
            nominal_idr=config.market_nominal_idr,
            horizon_minutes=config.market_horizon_minutes,
        )

    def session(request: Request, response: Response) -> MarketScope:
        scope = authorize(request.cookies.get("saham_session"))
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie"
        response.headers["Expires"] = format_datetime(
            market.started + timedelta(minutes=scope.horizon_minutes), usegmt=True
        )
        # Identity/mode/horizon remain server-owned. Only candidate sizing is selectable.
        allowed = {"interval"} if request.url.path.endswith("/chart") else set()
        if request.url.path.endswith("/candidates"):
            allowed = {"nominal_idr"}
        if set(request.query_params) - allowed:
            raise HTTPException(422)
        if "nominal_idr" in request.query_params:
            values = request.query_params.getlist("nominal_idr")
            if len(values) != 1 or not re.fullmatch(
                r"(?:0\.(?:0[1-9]|[1-9][0-9])|[1-9][0-9]{0,15}\.[0-9]{2})", values[0]
            ):
                raise HTTPException(422)
            scope = replace(scope, nominal_idr=values[0])
        return scope

    def personal(scope: MarketScope, kind: str) -> dict[str, Any] | None:
        try:
            return preferences.get(scope, kind)
        except psycopg.Error:
            raise HTTPException(503) from None

    def envelope(scope: MarketScope, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        result = market.read(scope, "candidates")
        result["data"] = data
        result["as_of"] = market.clock().isoformat().replace("+00:00", "Z")
        validate(kind + "Response", result)
        return result

    @router.get("/watchlist")
    def watchlist(scope: Annotated[MarketScope, Depends(session)]) -> dict[str, Any]:
        return envelope(scope, "Watchlist", personal(scope, "Watchlist") or {"symbols": []})

    @router.get("/settings/risk")
    def risk_settings(scope: Annotated[MarketScope, Depends(session)]) -> dict[str, Any]:
        settings = personal(scope, "RiskSettings")
        if settings is None:
            raise HTTPException(404)
        return envelope(
            scope, "RiskSettings", {k: v for k, v in settings.items() if k != "fee_schedule"}
        )

    @router.get("/settings/profile")
    def risk_profile(scope: Annotated[MarketScope, Depends(session)]) -> dict[str, Any]:
        settings = personal(scope, "RiskSettings")
        if settings is None:
            raise HTTPException(404)
        return envelope(scope, "RiskProfile", settings)

    @router.get("/settings/eligibility")
    def risk_eligibility(scope: Annotated[MarketScope, Depends(session)]) -> dict[str, Any]:
        settings = personal(scope, "RiskSettings")
        if settings is None:
            raise HTTPException(404)
        return envelope(scope, "SettingsEligibility", eligibility(settings, market.clock()))

    def save(
        request: Request, scope: MarketScope, kind: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        if request.headers.get("origin") not in config.cors_origins:
            raise HTTPException(403)
        key = request.headers.get("idempotency-key", "")
        if not 1 <= len(key) <= 128:
            raise HTTPException(422)
        try:
            validate_preference(kind, data)
            result = preferences.put(scope, kind, key, data)
        except PreferenceConflict:
            raise HTTPException(409) from None
        except (ValidationError, ValueError):
            raise HTTPException(422) from None
        except psycopg.Error:
            raise HTTPException(503) from None
        # Scope/version keys also isolate other processes; evict this account locally.
        with market.lock:
            for cached in list(market.cache):
                if cached[0].account == scope.account and cached[0].mode == scope.mode:
                    del market.cache[cached]
        return envelope(scope, "RiskProfile" if kind == "RiskSettings" else kind, result)

    @router.put("/watchlist")
    def replace_watchlist(
        request: Request, data: dict[str, Any], scope: Annotated[MarketScope, Depends(session)]
    ) -> dict[str, Any]:
        return save(request, scope, "Watchlist", data)

    @router.put("/settings/risk")
    def replace_settings(
        request: Request, data: dict[str, Any], scope: Annotated[MarketScope, Depends(session)]
    ) -> dict[str, Any]:
        try:
            validate("RiskSettings", data)
        except ValidationError:
            raise HTTPException(422) from None
        current = personal(scope, "RiskSettings")
        if current is None or current["fee_schedule_version"] != data["fee_schedule_version"]:
            raise HTTPException(422)
        result = save(
            request, scope, "RiskSettings", {**data, "fee_schedule": current["fee_schedule"]}
        )
        result["data"].pop("fee_schedule")
        validate("RiskSettingsResponse", result)
        return result

    @router.put("/settings/profile")
    def replace_profile(
        request: Request, data: dict[str, Any], scope: Annotated[MarketScope, Depends(session)]
    ) -> dict[str, Any]:
        return save(request, scope, "RiskSettings", data)

    def read(
        scope: MarketScope, resource: str, symbol: str | None = None, interval: str = "1m"
    ) -> dict[str, Any]:
        try:
            # Persisted personal settings override the transient dashboard nominal.
            settings = personal(scope, "RiskSettings")
            if settings:
                scope = replace(
                    scope,
                    nominal_idr=settings["nominal_idr"],
                    configuration_version=settings["configuration_version"],
                )
            result = market.read(scope, resource, symbol, interval)
            signals = (
                result["data"]
                if resource in {"candidates", "history"}
                else ([result["data"]["signal"]] if resource == "detail" else [])
            )
            if settings:
                for signal in signals:
                    signal["assumptions"]["fee_schedule_version"] = settings["fee_schedule_version"]
                    # Without validated feed/model/portfolio the contract must abstain.
                    # Re-evaluate on every read, including fee expiry and config changes.
                    if signal["state"] in {"WATCH", "READY"}:
                        signal["state"] = "WATCH"
                        signal["invalidation"] = "DATA_UNHEALTHY"
                if not fees_current(settings, market.clock()):
                    result["quality"]["status"] = "unavailable"
            return result
        except MarketNotFound:
            raise HTTPException(404) from None
        except MarketUnavailable:
            raise HTTPException(503) from None

    @router.get("/candidates")
    async def candidates(scope: Annotated[MarketScope, Depends(session)]) -> dict[str, Any]:
        return read(scope, "candidates")

    @router.get("/stocks/{symbol}")
    async def detail(
        symbol: str, scope: Annotated[MarketScope, Depends(session)]
    ) -> dict[str, Any]:
        return read(scope, "detail", symbol)

    @router.get("/stocks/{symbol}/depth")
    async def depth(symbol: str, scope: Annotated[MarketScope, Depends(session)]) -> dict[str, Any]:
        return read(scope, "depth", symbol)

    @router.get("/stocks/{symbol}/chart")
    async def chart(
        symbol: str,
        scope: Annotated[MarketScope, Depends(session)],
        interval: Literal["1m", "5m", "15m"],
    ) -> dict[str, Any]:
        return read(scope, "chart", symbol, interval)

    @router.get("/stocks/{symbol}/signals")
    async def history(
        symbol: str, scope: Annotated[MarketScope, Depends(session)]
    ) -> dict[str, Any]:
        return read(scope, "history", symbol)

    @router.websocket("/stream")
    async def stream(ws: WebSocket) -> None:
        try:
            scope = authorize(ws.cookies.get("saham_session"))
            if ws.headers.get("origin") not in config.cors_origins or ws.query_params:
                raise HTTPException(403)
        except HTTPException:
            await ws.close(code=1008)
            return
        await ws.accept()
        subscriptions: dict[str, dict[str, Any]] = {}

        async def error(code: ErrorCode) -> None:
            meta = market.read(scope, "candidates")
            body = {k: v for k, v in meta.items() if k != "data"}
            body["data"] = {
                "code": code,
                "request_id": str(uuid4()),
                "retryable": code in {"RESYNC_REQUIRED", "DATA_UNAVAILABLE", "RATE_LIMITED"},
                "fields": [],
            }
            validate("ErrorResponse", body)
            await ws.send_json(body)

        def state(topic: str, symbol: str | None) -> dict[str, Any]:
            response = read(scope, "depth" if topic == "depth" else "candidates", symbol)
            if topic == "depth":
                response["data"] = [response["data"]]
            elif symbol:
                response["data"] = [s for s in response["data"] if s["symbol"] == symbol]
            return response

        try:
            while True:
                received = True
                try:
                    message = await asyncio.wait_for(ws.receive_json(), timeout=0.25)
                except TimeoutError:
                    received = False
                    message = None
                except (json.JSONDecodeError, UnicodeDecodeError, KeyError):
                    await error("INVALID_REQUEST")
                    continue
                if received:
                    try:
                        validate("Subscribe", message)
                    except ValidationError:
                        await error("INVALID_REQUEST")
                        continue
                    if message["resume_cursor"] is not None:
                        # No retained replay chain: even a previously issued cursor needs resync.
                        subscriptions.pop(message["subscription_id"], None)
                        await error("RESYNC_REQUIRED")
                        continue
                    if message["topic"] not in {"signals", "depth"}:
                        await error("DATA_UNAVAILABLE")
                        continue
                    if len(subscriptions) >= 8 and message["subscription_id"] not in subscriptions:
                        await error("RATE_LIMITED")
                        continue
                    try:
                        response = state(message["topic"], message["symbol"])
                    except HTTPException:
                        await error("NOT_FOUND")
                        continue
                    snapshot = {k: v for k, v in response.items() if k != "data"}
                    snapshot.update(
                        kind="snapshot",
                        stream_id=str(uuid4()),
                        subscription_id=message["subscription_id"],
                        topic=message["topic"],
                        symbol=message["symbol"],
                        user_id=scope.account,
                        cursor=str(uuid4()),
                        sequence="1",
                        items=response["data"],
                    )
                    validate("Snapshot", snapshot)
                    subscriptions[message["subscription_id"]] = snapshot
                    await ws.send_json(snapshot)

                for sub in subscriptions.values():
                    response = state(sub["topic"], sub["symbol"])
                    if response["data"] == sub["items"]:
                        continue
                    id_field = "symbol" if sub["topic"] == "depth" else "signal_id"
                    old = {i[id_field]: i for i in sub["items"]}
                    new = {i[id_field]: i for i in response["data"]}
                    operations = [
                        {"op": "remove", "entity_id": entity_id}
                        for entity_id in old.keys() - new.keys()
                    ] + [
                        {"op": "upsert", "entity_id": entity_id, "entity": entity}
                        for entity_id, entity in new.items()
                        if old.get(entity_id) != entity
                    ]
                    delta = {k: v for k, v in sub.items() if k != "items"}
                    delta.update(
                        kind="delta",
                        previous_sequence=sub["sequence"],
                        sequence=str(int(sub["sequence"]) + 1),
                        cursor=str(uuid4()),
                        as_of=response["as_of"],
                        quality=response["quality"],
                        operations=operations,
                    )
                    validate("Delta", delta)
                    await ws.send_json(delta)
                    sub.update(
                        sequence=delta["sequence"],
                        cursor=delta["cursor"],
                        items=response["data"],
                        as_of=response["as_of"],
                        quality=response["quality"],
                    )
        except WebSocketDisconnect:
            return

    return router
