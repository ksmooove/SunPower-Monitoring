# Data model

See also [adr/0002-measurement-schema.md](adr/0002-measurement-schema.md).

## Entities

| Table | Purpose |
|-------|---------|
| `sites` | Installation (seeded `Home`, TZ from `SITE_TIMEZONE`) |
| `supervisors` | PVS6 supervisor metadata |
| `devices` | `site` / `meter` / `inverter` identities (`pvs_path_id`) |
| `measurements` | Timescale hypertable of metric samples (UTC) |
| `collector_runs` | Collector health history |
| `schema_migrations` | Applied SQL migration versions |

## Metrics (source units preserved)

| Metric | Typical device | Unit |
|--------|----------------|------|
| `pv_power_kw` | site | kW |
| `pv_energy_kwh` | site | kWh |
| `net_power_kw` | site | kW |
| `net_energy_kwh` | site | kWh |
| `site_load_power_kw` | site | kW |
| `site_load_energy_kwh` | site | kWh |
| `power_kw` | meter, inverter | kW |
| `lifetime_energy_kwh` | inverter | kWh |
| `net_energy_kwh` / `pos_energy_kwh` / `neg_energy_kwh` | meter | kWh |
| `voltage_v`, `current_a`, `freq_hz`, `heatsink_c` | inverter/meter | V / A / Hz / °C |

Quality is `measured` for varserver/fixture samples. Estimated values must be labeled if added later.

## Data retention

Configured intent in `.env.example`: `MEASUREMENT_RETENTION_DAYS=1825` (~5 years). **Automated purge is not implemented yet**, so samples currently remain until you delete them or free disk space. Stored values do **not** degrade or downsample over time today—each poll keeps full precision.

When retention jobs are added, older raw high-resolution points may be downsampled to hourly/daily aggregates; that change will be documented in an ADR.
