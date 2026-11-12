from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from saham_signal.domain.mode import Mode

ErrorCode = Literal[
    "INVALID_REQUEST",
    "UNAUTHENTICATED",
    "FORBIDDEN",
    "NOT_FOUND",
    "CONFLICT",
    "RATE_LIMITED",
    "DATA_UNAVAILABLE",
    "UNSUPPORTED_VERSION",
    "RESYNC_REQUIRED",
    "INTERNAL_ERROR",
]


class ErrorData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: ErrorCode
    request_id: str
    retryable: bool
    fields: list[str]


class UnavailableQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["unavailable"] = "unavailable"
    feed: Literal["unavailable"] = "unavailable"
    last_heartbeat_at: None = None
    reasons: list[Literal["SIMULATION"]]


class ErrorResponse(BaseModel):
    """SS-002 envelope; actual responses are validated against its source schema."""

    model_config = ConfigDict(extra="forbid")
    contract_version: Literal["1.0.0"] = "1.0.0"
    as_of: datetime
    mode: Mode
    data_origin: Literal["simulation", "market"]
    quality: UnavailableQuality
    data: ErrorData


def error_response(request: Request, status: int, code: ErrorCode) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or str(uuid4())
    mode: Mode = request.app.state.mode
    simulated = mode != "live"
    body = ErrorResponse(
        as_of=datetime.now(UTC),
        mode=mode,
        data_origin="simulation" if simulated else "market",
        quality=UnavailableQuality(reasons=["SIMULATION"] if simulated else []),
        data=ErrorData(
            code=code, request_id=request_id, retryable=status >= 500 or status == 429, fields=[]
        ),
    )
    headers = {"X-Request-ID": request_id}
    if status in {429, 503}:
        headers["Retry-After"] = "3"
    return JSONResponse(
        status_code=status,
        content=body.model_dump(mode="json"),
        headers=headers,
    )
