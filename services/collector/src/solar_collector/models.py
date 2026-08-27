from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Quality(StrEnum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    AGGREGATED = "aggregated"
    UNKNOWN = "unknown"


class SupervisorInfo(BaseModel):
    model: str | None = None
    build: int | None = None
    software_version: str | None = None
    firmware_version: str | None = None
    serial_redacted: bool = True
    raw: dict[str, Any] = Field(default_factory=dict)


class SystemStatus(BaseModel):
    reachable: bool
    authenticated: bool = False
    software_revision: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str | None = None


class DeviceInfo(BaseModel):
    device_type: str
    pvs_path_id: str
    model: str | None = None
    serial_present: bool = False


class SiteLivedata(BaseModel):
    pvs_time_epoch: int | None = None
    pv_power_kw: float | None = None
    pv_energy_kwh: float | None = None
    net_power_kw: float | None = None
    net_energy_kwh: float | None = None
    site_load_power_kw: float | None = None
    site_load_energy_kwh: float | None = None
    ess_power_kw: float | None = None
    ess_energy_kwh: float | None = None
    soc: float | None = None
    backup_time_remaining: float | None = None
    midstate: float | None = None
    quality: Quality = Quality.MEASURED
    source: str = "varserver.livedata"
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MeterReading(BaseModel):
    meter_index: int
    model: str | None = None
    power_kw: float | None = None
    net_energy_kwh: float | None = None
    pos_energy_kwh: float | None = None
    neg_energy_kwh: float | None = None
    voltage_v: float | None = None
    freq_hz: float | None = None
    measurement_time: datetime | None = None
    serial_present: bool = False
    quality: Quality = Quality.MEASURED
    source: str = "varserver.meter"
    raw_fields: dict[str, Any] = Field(default_factory=dict)


class InverterReading(BaseModel):
    inverter_index: int
    model: str | None = None
    power_kw: float | None = None
    lifetime_energy_kwh: float | None = None
    voltage_v: float | None = None
    current_a: float | None = None
    freq_hz: float | None = None
    heatsink_c: float | None = None
    measurement_time: datetime | None = None
    serial_present: bool = False
    quality: Quality = Quality.MEASURED
    source: str = "varserver.inverter"
    raw_fields: dict[str, Any] = Field(default_factory=dict)


class CurrentMeasurements(BaseModel):
    livedata: SiteLivedata | None = None
    meters: list[MeterReading] = Field(default_factory=list)
    inverters: list[InverterReading] = Field(default_factory=list)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    parser_version: str = "1"
