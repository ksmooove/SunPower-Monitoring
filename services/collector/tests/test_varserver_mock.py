from __future__ import annotations

import httpx
import pytest
import respx

from solar_collector.config import Settings
from solar_collector.datasource.varserver import VarserverDataSource


@pytest.mark.asyncio
@respx.mock
async def test_varserver_refuses_set_query() -> None:
    settings = Settings(pvs_password="dummy")
    async with httpx.AsyncClient(base_url="https://pvs.test") as client:
        ds = VarserverDataSource(settings, client=client)
        with pytest.raises(ValueError, match="refusing"):
            await ds._request("GET", "/vars?set=/sys/telemetryws/enable=1")


@pytest.mark.asyncio
@respx.mock
async def test_varserver_login_and_livedata_path() -> None:
    settings = Settings(
        pvs_host="pvs.test",
        pvs_password="dummy",
        pvs_verify_tls=False,
    )
    respx.get("https://pvs.test:443/auth?login").mock(
        return_value=httpx.Response(200, json={"session": "SESSION_REDACTED"})
    )
    respx.get("https://pvs.test:443/vars").mock(
        side_effect=[
            httpx.Response(200, json={"/sys/info/sw_rev": "2025.10.20.61846"}),
            httpx.Response(
                200,
                json={
                    "/sys/livedata/pv_p": "1.5",
                    "/sys/livedata/site_load_p": "0.5",
                    "/sys/livedata/ess_p": "nan",
                },
            ),
            httpx.Response(
                200,
                json={
                    "/sys/devices/meter/0/prodMdlNm": "PVS6M0400p",
                    "/sys/devices/meter/0/p3phsumKw": "1.5",
                },
            ),
            httpx.Response(
                200,
                json={
                    "/sys/devices/inverter/0/prodMdlNm": "AC_Module",
                    "/sys/devices/inverter/0/pMppt1Kw": "0.1",
                    "/sys/devices/inverter/0/sn": "INVERTER_SERIAL_REDACTED",
                },
            ),
        ]
    )
    async with httpx.AsyncClient(base_url="https://pvs.test:443", verify=False) as client:
        ds = VarserverDataSource(settings, client=client)
        status = await ds.get_system_status()
        assert status.reachable
        assert status.software_revision == "2025.10.20.61846"
        measurements = await ds.get_current_measurements()
        assert measurements.livedata is not None
        assert measurements.livedata.pv_power_kw == 1.5
        assert len(measurements.meters) == 1
        assert len(measurements.inverters) == 1
