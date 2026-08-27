from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx

from solar_collector.config import Settings
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
from solar_collector.safety import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)


class VarserverDataSource(PvsDataSource):
    """Authenticated varserver client for PVS6 build 61840+.

    Uses flat `match=meter` / `match=inverter` queries observed on build 61846.
    Never issues `/vars?set=` writes.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=settings.pvs_base_url,
            verify=settings.pvs_verify_tls,
            timeout=settings.pvs_request_timeout_seconds,
            headers={"User-Agent": "solar-monitor-collector/0.1"},
        )
        self._breaker = CircuitBreaker(
            failure_threshold=settings.pvs_circuit_breaker_failures,
            reset_seconds=settings.pvs_circuit_breaker_reset_seconds,
        )
        import asyncio

        self._gate = asyncio.Lock()
        self._authenticated = False

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @asynccontextmanager
    async def _request_slot(self):
        self._breaker.before_call()
        async with self._gate:
            try:
                yield
                self._breaker.record_success()
            except Exception:
                self._breaker.record_failure()
                raise

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if method.upper() not in {"GET", "HEAD"}:
            raise ValueError(f"refusing non-read method: {method}")
        if "set=" in path or "set=" in str(kwargs.get("params", "")):
            raise ValueError("refusing varserver write (set=)")
        async with self._request_slot():
            response = await self._client.request(method, path, **kwargs)
            return response

    async def login(self) -> None:
        password = self._settings.pvs_password.get_secret_value()
        if not password:
            raise RuntimeError("PVS_PASSWORD is not configured")
        response = await self._request(
            "GET",
            "/auth?login",
            auth=(self._settings.pvs_username, password),
        )
        response.raise_for_status()
        self._authenticated = True
        logger.info("pvs_auth_login_ok")

    async def logout(self) -> None:
        password = self._settings.pvs_password.get_secret_value()
        try:
            await self._request(
                "GET",
                "/auth?logout",
                auth=(self._settings.pvs_username, password),
            )
        finally:
            self._authenticated = False
            logger.info("pvs_auth_logout_done")

    async def _ensure_auth(self) -> None:
        if not self._authenticated:
            await self.login()

    async def discover_capabilities(self) -> dict[str, Any]:
        return {
            "source": "varserver",
            "firmware_gate": ">=61840",
            "livedata": True,
            "meters_flat_match": "meter",
            "inverters_flat_match": "inverter",
            "legacy_meter_data_match": "meter/data (400 on build 61846)",
            "writes_allowed": False,
            "poll_interval_seconds": self._settings.pvs_poll_interval_seconds,
        }

    async def get_supervisor_info(self) -> SupervisorInfo:
        response = await self._request("GET", "/cgi-bin/dl_cgi/supervisor/info")
        response.raise_for_status()
        return parse_supervisor_dlcgi(response.json())

    async def get_system_status(self) -> SystemStatus:
        try:
            await self._ensure_auth()
            response = await self._request(
                "GET",
                "/vars",
                params={"name": "/sys/info/sw_rev", "fmt": "obj"},
            )
            response.raise_for_status()
            sw = response.json().get("/sys/info/sw_rev")
            return SystemStatus(reachable=True, authenticated=True, software_revision=sw)
        except CircuitOpenError as exc:
            return SystemStatus(reachable=False, authenticated=False, message=str(exc))
        except Exception as exc:  # noqa: BLE001 — surfaced as status
            return SystemStatus(reachable=False, authenticated=False, message=str(exc))

    async def health_check(self) -> SystemStatus:
        return await self.get_system_status()

    async def _vars_match(self, match: str, cache: str) -> dict[str, Any]:
        await self._ensure_auth()
        response = await self._request(
            "GET",
            "/vars",
            params={"match": match, "fmt": "obj", "cache": cache},
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("expected object fmt from /vars")
        return data

    async def get_current_measurements(self) -> CurrentMeasurements:
        livedata = await self._vars_match("livedata", "ldata")
        meters = await self._vars_match("meter", "mdata")
        inverters = await self._vars_match("inverter", "idata")
        return assemble_measurements(livedata, meters, inverters)

    async def get_devices(self) -> list[DeviceInfo]:
        return devices_from_measurements(await self.get_current_measurements())
