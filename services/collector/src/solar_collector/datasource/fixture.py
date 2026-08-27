from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from solar_collector.datasource.base import PvsDataSource
from solar_collector.models import (
    CurrentMeasurements,
    DeviceInfo,
    SupervisorInfo,
    SystemStatus,
)
from solar_collector.parse import (
    assemble_measurements,
    devices_from_measurements,
    parse_supervisor_dlcgi,
)


class FixtureDataSource(PvsDataSource):
    """Replay sanitized fixtures. Never contacts the PVS."""

    def __init__(self, fixtures_dir: str | Path) -> None:
        self._dir = Path(fixtures_dir)

    def _load(self, name: str) -> dict[str, Any]:
        path = self._dir / name
        return json.loads(path.read_text(encoding="utf-8"))

    async def discover_capabilities(self) -> dict[str, Any]:
        return {
            "source": "fixture",
            "livedata": True,
            "meters_flat": True,
            "inverters_flat": True,
            "supervisor_dlcgi": True,
            "writes_allowed": False,
        }

    async def get_supervisor_info(self) -> SupervisorInfo:
        return parse_supervisor_dlcgi(self._load("supervisor-info.json"))

    async def get_system_status(self) -> SystemStatus:
        sw = self._load("vars-sw-rev.json").get("/sys/info/sw_rev")
        return SystemStatus(reachable=True, authenticated=True, software_revision=sw)

    async def health_check(self) -> SystemStatus:
        return await self.get_system_status()

    async def get_current_measurements(self) -> CurrentMeasurements:
        return assemble_measurements(
            self._load("vars-livedata.json"),
            self._load("vars-meter.json"),
            self._load("vars-inverter.json"),
        )

    async def get_devices(self) -> list[DeviceInfo]:
        return devices_from_measurements(await self.get_current_measurements())
