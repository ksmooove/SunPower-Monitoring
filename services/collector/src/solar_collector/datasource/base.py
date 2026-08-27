from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from solar_collector.models import (
    CurrentMeasurements,
    DeviceInfo,
    SupervisorInfo,
    SystemStatus,
)


class PvsDataSource(ABC):
    """Protocol-neutral interface to a PVS supervisor."""

    @abstractmethod
    async def discover_capabilities(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_system_status(self) -> SystemStatus:
        raise NotImplementedError

    @abstractmethod
    async def get_supervisor_info(self) -> SupervisorInfo:
        raise NotImplementedError

    @abstractmethod
    async def get_devices(self) -> list[DeviceInfo]:
        raise NotImplementedError

    @abstractmethod
    async def get_current_measurements(self) -> CurrentMeasurements:
        raise NotImplementedError

    async def stream_measurements(self) -> AsyncIterator[CurrentMeasurements]:
        """Optional streaming. Default: not supported."""
        raise NotImplementedError("stream_measurements is not available for this source")
        yield  # pragma: no cover

    @abstractmethod
    async def health_check(self) -> SystemStatus:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None
