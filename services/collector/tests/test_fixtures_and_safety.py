from __future__ import annotations

import json
from pathlib import Path

import pytest

from solar_collector.datasource.fixture import FixtureDataSource
from solar_collector.parse import parse_inverters_flat, parse_livedata, parse_meters_flat
from solar_collector.safety import CircuitBreaker, CircuitOpenError

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "pvs6"


@pytest.fixture
def fixtures_dir() -> Path:
    assert FIXTURES.is_dir(), FIXTURES
    return FIXTURES


def test_parse_livedata_nan_ess(fixtures_dir: Path) -> None:
    obj = json.loads((fixtures_dir / "vars-livedata.json").read_text(encoding="utf-8"))
    livedata = parse_livedata(obj)
    assert livedata.pv_power_kw is not None and livedata.pv_power_kw > 0
    assert livedata.site_load_power_kw is not None
    assert livedata.ess_power_kw is None
    assert livedata.soc is None


def test_parse_meters_production_and_consumption(fixtures_dir: Path) -> None:
    obj = json.loads((fixtures_dir / "vars-meter.json").read_text(encoding="utf-8"))
    meters = parse_meters_flat(obj)
    assert len(meters) == 2
    models = {m.model for m in meters}
    assert "PVS6M0400p" in models
    assert "PVS6M0400c" in models


def test_parse_inverters_count(fixtures_dir: Path) -> None:
    obj = json.loads((fixtures_dir / "vars-inverter.json").read_text(encoding="utf-8"))
    inverters = parse_inverters_flat(obj)
    assert len(inverters) == 44
    assert all(i.serial_present for i in inverters)
    assert sum(1 for i in inverters if i.power_kw is not None) == 44


@pytest.mark.asyncio
async def test_fixture_source_end_to_end(fixtures_dir: Path) -> None:
    ds = FixtureDataSource(fixtures_dir)
    status = await ds.health_check()
    assert status.reachable is True
    assert status.software_revision and "61846" in status.software_revision
    m = await ds.get_current_measurements()
    assert m.livedata is not None
    assert len(m.meters) == 2
    assert len(m.inverters) == 44
    devices = await ds.get_devices()
    assert len(devices) == 46


def test_circuit_breaker_opens() -> None:
    br = CircuitBreaker(failure_threshold=3, reset_seconds=900)
    br.record_failure()
    br.record_failure()
    br.before_call()
    br.record_failure()
    with pytest.raises(CircuitOpenError):
        br.before_call()
