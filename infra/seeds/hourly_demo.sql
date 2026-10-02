BEGIN;

WITH sensors(tenant_id, sensor_id, resource, unit, baseline, latest) AS (
    VALUES
    ('11111111-1111-4111-8111-111111111111'::uuid,
     'A-WATER-01', 'water', 'm3', 10, 35),
    ('11111111-1111-4111-8111-111111111111'::uuid,
     'A-ENERGY-01', 'energy', 'kWh', 80, 240),
    ('22222222-2222-4222-8222-222222222222'::uuid,
     'B-WATER-01', 'water', 'm3', 8, 8),
    ('22222222-2222-4222-8222-222222222222'::uuid,
     'B-ENERGY-01', 'energy', 'kWh', 60, 60)
)
INSERT INTO bws_ai.readings (
    id, tenant_id, sensor_id, resource, value, unit,
    measured_at, data_source, interval_seconds
)
SELECT
    md5('synthetic_hourly_v1:' || sensor_id || ':' || h::text)::uuid,
    tenant_id, sensor_id, resource,
    CASE WHEN h = 23 THEN latest ELSE baseline END,
    unit,
    date_trunc('hour', now()) - (23 - h) * interval '1 hour',
    'synthetic_hourly_v1',
    3600
FROM sensors
CROSS JOIN generate_series(0, 23) AS h
ON CONFLICT (id) DO NOTHING;

COMMIT;
