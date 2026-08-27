-- 003_historical_reports.sql -- imported SunPower monthly reports

CREATE TABLE IF NOT EXISTS historical_reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    source_file         TEXT NOT NULL,
    this_period_kwh     DOUBLE PRECISION,
    last_period_kwh     DOUBLE PRECISION,
    last_year_kwh       DOUBLE PRECISION,
    lifetime_kwh        DOUBLE PRECISION,
    this_period_max_kw  DOUBLE PRECISION,
    imported_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (period_start, period_end)
);

CREATE TABLE IF NOT EXISTS historical_report_days (
    report_id       UUID NOT NULL REFERENCES historical_reports(id) ON DELETE CASCADE,
    local_date      DATE NOT NULL,
    energy_kwh      DOUBLE PRECISION NOT NULL,
    max_power_kw    DOUBLE PRECISION,
    PRIMARY KEY (report_id, local_date)
);

CREATE INDEX IF NOT EXISTS historical_report_days_date_idx
    ON historical_report_days (local_date);

INSERT INTO schema_migrations (version) VALUES ('003_historical_reports')
ON CONFLICT (version) DO NOTHING;