"""Real dependency checks, invoked by scripts/check-local-infra.mjs only."""

import asyncio
import os
import sys

import psycopg
from fastapi.testclient import TestClient
from redis import Redis

from saham_signal.config import Settings
from saham_signal.transport.http import create_app

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

settings = Settings()
action = sys.argv[1]
with TestClient(create_app(settings)) as client:
    assert client.get("/health").status_code == 200
    response = client.get("/ready")
    expected = 503 if action == "unavailable" else 200
    assert response.status_code == expected, f"Readiness expected {expected}"
    if expected == 503:
        assert response.json()["data"]["code"] == "DATA_UNAVAILABLE"
    else:
        assert all(response.json()["dependencies"].values())

if action in {"write", "persisted", "isolated", "cleanup"}:
    with psycopg.connect(settings.database_url.get_secret_value()) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SHOW timezone")
            assert cursor.fetchone() == ("UTC",)
            if action == "write":
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS local_infra_smoke (id integer PRIMARY KEY)"
                )
                cursor.execute(
                    "INSERT INTO local_infra_smoke VALUES (1) ON CONFLICT DO NOTHING"
                )
            elif action == "persisted":
                cursor.execute("SELECT id FROM local_infra_smoke")
                assert cursor.fetchone() == (1,)
            elif action == "isolated":
                cursor.execute("SELECT to_regclass('public.local_infra_smoke')")
                assert cursor.fetchone() == (None,)
                cursor.execute("SELECT datname FROM pg_database")
                assert ("saham_signal_research",) not in cursor.fetchall()
            else:
                cursor.execute("DROP TABLE local_infra_smoke")
    with Redis.from_url(settings.redis_url.get_secret_value()) as redis:
        key = "saham-signal:research:local-infra-smoke"
        if action == "write":
            redis.set(key, "persistent")
        elif action == "persisted":
            assert redis.get(key) == b"persistent"
        elif action == "isolated":
            assert redis.get(key) is None
        else:
            redis.delete(key)
    # Wrong credentials must fail; readiness must not return success.
    if action == "write":
        for field, variable in (
            ("redis_url", "BAD_REDIS_URL"),
            ("database_url", "BAD_DATABASE_URL"),
        ):
            bad = settings.model_copy(
                update={field: settings.redis_url.__class__(os.environ[variable])}
            )
            with TestClient(create_app(bad)) as client:
                assert client.get("/ready").status_code == 503

print(f"Dependency integration: {action} passed")
