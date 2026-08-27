from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from solar_collector.models import (
    CurrentMeasurements,
    DeviceInfo,
    InverterReading,
    MeterReading,
    SiteLivedata,
    SupervisorInfo,
)

_INVERTER_RE = re.compile(r"^/sys/devices/inverter/(\d+)/(.+)$")
_METER_RE = re.compile(r"^/sys/devices/meter/(\d+)/(.+)$")


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        return None if math.isnan(f) else f
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return None if math.isnan(f) else f


def _to_int(value: Any) -> int | None:
    f = _to_float(value)
    return int(f) if f is not None else None


def _parse_msmt(value: Any) -> datetime | None:
    if not value:
        return None
    s = str(value).strip()
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def parse_supervisor_dlcgi(payload: dict[str, Any]) -> SupervisorInfo:
    sup = payload.get("supervisor") or {}
    # Drop serial from retained raw
    raw = {k: v for k, v in sup.items() if k.upper() != "SERIAL"}
    return SupervisorInfo(
        model=sup.get("MODEL"),
        build=_to_int(sup.get("BUILD")),
        software_version=sup.get("SWVER"),
        firmware_version=sup.get("FWVER"),
        serial_redacted=True,
        raw=raw,
    )


def parse_livedata(obj: dict[str, Any]) -> SiteLivedata:
    def g(suffix: str) -> Any:
        return obj.get(f"/sys/livedata/{suffix}")

    return SiteLivedata(
        pvs_time_epoch=_to_int(g("time")),
        pv_power_kw=_to_float(g("pv_p")),
        pv_energy_kwh=_to_float(g("pv_en")),
        net_power_kw=_to_float(g("net_p")),
        net_energy_kwh=_to_float(g("net_en")),
        site_load_power_kw=_to_float(g("site_load_p")),
        site_load_energy_kwh=_to_float(g("site_load_en")),
        ess_power_kw=_to_float(g("ess_p")),
        ess_energy_kwh=_to_float(g("ess_en")),
        soc=_to_float(g("soc")),
        backup_time_remaining=_to_float(g("backupTimeRemaining")),
        midstate=_to_float(g("midstate")),
    )


def parse_meters_flat(obj: dict[str, Any]) -> list[MeterReading]:
    buckets: dict[int, dict[str, Any]] = defaultdict(dict)
    for key, value in obj.items():
        m = _METER_RE.match(key)
        if not m:
            continue
        buckets[int(m.group(1))][m.group(2)] = value

    readings: list[MeterReading] = []
    for idx in sorted(buckets):
        fields = buckets[idx]
        readings.append(
            MeterReading(
                meter_index=idx,
                model=str(fields["prodMdlNm"]) if "prodMdlNm" in fields else None,
                power_kw=_to_float(fields.get("p3phsumKw")),
                net_energy_kwh=_to_float(fields.get("netLtea3phsumKwh")),
                pos_energy_kwh=_to_float(fields.get("posLtea3phsumKwh")),
                neg_energy_kwh=_to_float(fields.get("negLtea3phsumKwh")),
                voltage_v=_to_float(fields.get("v12V")),
                freq_hz=_to_float(fields.get("freqHz")),
                measurement_time=_parse_msmt(fields.get("msmtEps")),
                serial_present="sn" in fields,
                raw_fields={k: v for k, v in fields.items() if k != "sn"},
            )
        )
    return readings


def parse_inverters_flat(obj: dict[str, Any]) -> list[InverterReading]:
    buckets: dict[int, dict[str, Any]] = defaultdict(dict)
    for key, value in obj.items():
        m = _INVERTER_RE.match(key)
        if not m:
            continue
        buckets[int(m.group(1))][m.group(2)] = value

    readings: list[InverterReading] = []
    for idx in sorted(buckets):
        fields = buckets[idx]
        readings.append(
            InverterReading(
                inverter_index=idx,
                model=str(fields["prodMdlNm"]) if "prodMdlNm" in fields else None,
                power_kw=_to_float(fields.get("pMppt1Kw")),
                lifetime_energy_kwh=_to_float(fields.get("ltea3phsumKwh")),
                voltage_v=_to_float(fields.get("vln3phavgV")),
                current_a=_to_float(fields.get("iMppt1A")),
                freq_hz=_to_float(fields.get("freqHz")),
                heatsink_c=_to_float(fields.get("tHtsnkDegc")),
                measurement_time=_parse_msmt(fields.get("msmtEps")),
                serial_present="sn" in fields,
                raw_fields={k: v for k, v in fields.items() if k != "sn"},
            )
        )
    return readings


def devices_from_measurements(m: CurrentMeasurements) -> list[DeviceInfo]:
    devices: list[DeviceInfo] = []
    for meter in m.meters:
        devices.append(
            DeviceInfo(
                device_type="meter",
                pvs_path_id=str(meter.meter_index),
                model=meter.model,
                serial_present=meter.serial_present,
            )
        )
    for inv in m.inverters:
        devices.append(
            DeviceInfo(
                device_type="inverter",
                pvs_path_id=str(inv.inverter_index),
                model=inv.model,
                serial_present=inv.serial_present,
            )
        )
    return devices


def assemble_measurements(
    livedata_obj: dict[str, Any] | None,
    meter_obj: dict[str, Any] | None,
    inverter_obj: dict[str, Any] | None,
) -> CurrentMeasurements:
    return CurrentMeasurements(
        livedata=parse_livedata(livedata_obj) if livedata_obj else None,
        meters=parse_meters_flat(meter_obj) if meter_obj else [],
        inverters=parse_inverters_flat(inverter_obj) if inverter_obj else [],
        collected_at=datetime.now(timezone.utc),
        parser_version="1",
    )
