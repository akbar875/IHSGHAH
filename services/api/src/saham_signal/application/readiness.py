import asyncio
from typing import Protocol


class DependencyProbe(Protocol):
    async def check(self) -> None:
        """Raise if this dependency cannot serve requests."""
        ...


async def check_dependencies(
    probes: dict[str, DependencyProbe], timeout_seconds: float
) -> dict[str, bool]:
    async def check(probe: DependencyProbe) -> bool:
        try:
            async with asyncio.timeout(timeout_seconds):
                await probe.check()
            return True
        except Exception:
            # Dependency errors can contain credentials; never return exception text.
            return False

    results = await asyncio.gather(*(check(probe) for probe in probes.values()))
    return dict(zip(probes, results, strict=True))
