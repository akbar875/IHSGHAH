import asyncio
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp

from saham_signal.adapters.probes import PostgresProbe, RedisProbe
from saham_signal.application.market import FixtureMarket
from saham_signal.application.readiness import DependencyProbe, check_dependencies
from saham_signal.config import Settings, load_settings
from saham_signal.domain.mode import Mode
from saham_signal.transport.errors import ErrorCode, ErrorResponse, error_response
from saham_signal.transport.market import market_router


class HealthResponse(BaseModel):
    status: str
    mode: Mode


class ReadyResponse(HealthResponse):
    dependencies: dict[str, bool]


def create_app(
    settings: Settings | None = None,
    probes: dict[str, DependencyProbe] | None = None,
    market: FixtureMarket | None = None,
) -> ASGIApp:
    config = settings if settings is not None else load_settings()
    dependencies: dict[str, DependencyProbe] = (
        probes
        if probes is not None
        else {
            "postgresql": PostgresProbe(config.database_url.get_secret_value()),
            "redis": RedisProbe(config.redis_url.get_secret_value()),
        }
    )
    if set(dependencies) != {"postgresql", "redis"}:
        raise ValueError("Readiness requires both postgresql and redis probes")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.started = True
        try:
            yield
        finally:
            app.state.started = False

    app = FastAPI(title="Saham Signal bootstrap API", version="0.1.0", lifespan=lifespan)
    app.state.started = False
    app.state.mode = config.app_mode
    app.include_router(market_router(config, market if market is not None else FixtureMarket()))

    @app.middleware("http")
    async def request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Generate IDs server-side; do not reflect untrusted request headers.
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> Response:
        codes: dict[int, ErrorCode] = {
            401: "UNAUTHENTICATED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            429: "RATE_LIMITED",
            503: "DATA_UNAVAILABLE",
        }
        response = error_response(
            request, exc.status_code, codes.get(exc.status_code, "INVALID_REQUEST")
        )
        if exc.headers and "Allow" in exc.headers:
            response.headers["Allow"] = exc.headers["Allow"]
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> Response:
        return error_response(request, 422, "INVALID_REQUEST")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> Response:
        return error_response(request, 500, "INTERNAL_ERROR")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", mode=config.app_mode)

    @app.get("/ready", response_model=ReadyResponse, responses={503: {"model": ErrorResponse}})
    async def ready(request: Request) -> ReadyResponse | Response:
        if not app.state.started:
            return error_response(request, 503, "DATA_UNAVAILABLE")
        result = await check_dependencies(dependencies, config.readiness_timeout_seconds)
        if not all(result.values()):
            return error_response(request, 503, "DATA_UNAVAILABLE")
        return ReadyResponse(status="ready", mode=config.app_mode, dependencies=result)

    # Wrap the whole app so unhandled 500 responses also receive CORS headers.
    return CORSMiddleware(
        app,
        allow_origins=config.cors_origins,
        allow_credentials=config.market_fixture_enabled,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )


def main() -> None:
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Local Saham Signal API")
    parser.add_argument("--env-file", default=None)
    args = parser.parse_args()
    # Psycopg async connections require a selector loop on Windows.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(
        "saham_signal.transport.http:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        env_file=args.env_file,
    )


if __name__ == "__main__":
    main()
