-- 001_init.sql — solar-monitor core schema (TimescaleDB)
-- Timestamps are UTC. Display TZ is application-side (America/Los_Angeles).

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS sites (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    timezone        TEXT NOT NULL DEFAULT 'America/Los_Angeles',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS supervisors (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id             UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    external_key        TEXT NOT NULL,
    model               TEXT,
    firmware_build      INTEGER,
    software_version    TEXT,
    collection_method   TEXT NOT NULL DEFAULT 'varserver',
    last_seen_at        TIMESTAMPTZ,
    capabilities        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (site_id, external_key)
);

CREATE TABLE IF NOT EXISTS devices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id         UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    supervisor_id   UUID NOT NULL REFERENCES supervisors(id) ON DELETE CASCADE,
    device_type     TEXT NOT NULL CHECK (device_type IN ('site', 'meter', 'inverter')),
    pvs_path_id     TEXT NOT NULL,
    model           TEXT,
    name            TEXT,
    rated_watts     INTEGER,
    grid_row        INTEGER,
    grid_col        INTEGER,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (supervisor_id, device_type, pvs_path_id)
);

CREATE INDEX IF NOT EXISTS devices_site_type_idx ON devices (site_id, device_type);

CREATE TABLE IF NOT EXISTS measurements (
    time            TIMESTAMPTZ NOT NULL,
    device_id       UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    metric          TEXT NOT NULL,
    value           DOUBLE PRECISION NOT NULL,
    unit            TEXT NOT NULL,
    quality         TEXT NOT NULL DEFAULT 'measured',
    source          TEXT NOT NULL,
    parser_version  TEXT NOT NULL DEFAULT '1',
    collected_at    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (time, device_id, metric, source)
);

SELECT create_hypertable('measurements', by_range('time'), if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS measurements_device_metric_time_idx
    ON measurements (device_id, metric, time DESC);

CREATE TABLE IF NOT EXISTS collector_runs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id          UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at      TIMESTAMPTZ,
    status           TEXT NOT NULL,
    source           TEXT NOT NULL,
    message          TEXT,
    meter_count      INTEGER,
    inverter_count   INTEGER,
    measurement_rows INTEGER
);

CREATE INDEX IF NOT EXISTS collector_runs_started_idx ON collector_runs (started_at DESC);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO schema_migrations (version) VALUES ('001_init')
ON CONFLICT (version) DO NOTHING;
