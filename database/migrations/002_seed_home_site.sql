-- 002_seed_home_site.sql — single-home seed (idempotent)

INSERT INTO sites (id, name, timezone)
VALUES ('11111111-1111-1111-1111-111111111111', 'Home', 'America/Los_Angeles')
ON CONFLICT (id) DO NOTHING;

INSERT INTO supervisors (id, site_id, external_key, model, firmware_build, software_version, collection_method, capabilities)
VALUES (
    '22222222-2222-2222-2222-222222222222',
    '11111111-1111-1111-1111-111111111111',
    'primary',
    'PVS6',
    61846,
    '2025.10.20.61846',
    'varserver',
    '{"livedata": true, "meters_flat": true, "inverters_flat": true, "panel_count_expected": 44}'::jsonb
)
ON CONFLICT (site_id, external_key) DO UPDATE
SET model = EXCLUDED.model,
    firmware_build = EXCLUDED.firmware_build,
    software_version = EXCLUDED.software_version,
    capabilities = EXCLUDED.capabilities;

-- Synthetic site device for livedata aggregates
INSERT INTO devices (id, site_id, supervisor_id, device_type, pvs_path_id, model, name, rated_watts)
VALUES (
    '33333333-3333-3333-3333-333333333333',
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
    'site',
    'livedata',
    'PVS6',
    'Site totals',
    NULL
)
ON CONFLICT (supervisor_id, device_type, pvs_path_id) DO NOTHING;

INSERT INTO schema_migrations (version) VALUES ('002_seed_home_site')
ON CONFLICT (version) DO NOTHING;
