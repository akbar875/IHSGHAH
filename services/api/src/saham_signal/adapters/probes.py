from collections.abc import Awaitable
from dataclasses import dataclass
from typing import cast

import psycopg
from redis.asyncio import Redis


@dataclass(frozen=True)
class PostgresProbe:
    dsn: str

    async def check(self) -> None:
        async with await psycopg.AsyncConnection.connect(self.dsn, connect_timeout=2) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT 1")
                if await cursor.fetchone() != (1,):
                    raise RuntimeError("Database probe failed")


@dataclass(frozen=True)
class RedisProbe:
    url: str

    async def check(self) -> None:
        async with Redis.from_url(self.url, socket_connect_timeout=2, socket_timeout=2) as client:
            # Redis 7 types share sync/async command mixins; this client is always async.
            if not await cast(Awaitable[bool], client.ping()):
                raise RuntimeError("Redis probe failed")
