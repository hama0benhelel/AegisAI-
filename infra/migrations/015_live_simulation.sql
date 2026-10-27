BEGIN;

CREATE UNIQUE INDEX readings_live_simulation_unique
    ON bws_ai.readings (tenant_id, sensor_id, resource, measured_at)
    WHERE data_source = 'synthetic_live_v1';

CREATE ROLE aegisai_simulator
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOINHERIT NOREPLICATION NOBYPASSRLS;

GRANT CONNECT ON DATABASE aegisai TO aegisai_simulator;
GRANT USAGE ON SCHEMA bws_ai TO aegisai_simulator;

GRANT SELECT ON bws_ai.readings TO aegisai_simulator;
GRANT INSERT (
    tenant_id, sensor_id, resource, value, unit,
    measured_at, data_source, interval_seconds
) ON bws_ai.readings TO aegisai_simulator;

CREATE POLICY simulator_read ON bws_ai.readings
    FOR SELECT TO aegisai_simulator
    USING (
        data_source = 'synthetic_live_v1'
        AND (tenant_id, sensor_id, resource, unit) IN (
            ('11111111-1111-4111-8111-111111111111'::uuid, 'A-SIM-WATER-01', 'water', 'm3'),
            ('11111111-1111-4111-8111-111111111111'::uuid, 'A-SIM-ENERGY-01', 'energy', 'kWh'),
            ('22222222-2222-4222-8222-222222222222'::uuid, 'B-SIM-WATER-01', 'water', 'm3'),
            ('22222222-2222-4222-8222-222222222222'::uuid, 'B-SIM-ENERGY-01', 'energy', 'kWh')
        )
    );

CREATE POLICY simulator_insert ON bws_ai.readings
    FOR INSERT TO aegisai_simulator
    WITH CHECK (
        data_source = 'synthetic_live_v1'
        AND interval_seconds = 3600
        AND value >= 0 AND value < 10000
        AND measured_at = date_trunc('hour', measured_at)
        AND measured_at + interval '1 hour' <= clock_timestamp()
        AND measured_at >= clock_timestamp() - interval '7 days'
        AND (tenant_id, sensor_id, resource, unit) IN (
            ('11111111-1111-4111-8111-111111111111'::uuid, 'A-SIM-WATER-01', 'water', 'm3'),
            ('11111111-1111-4111-8111-111111111111'::uuid, 'A-SIM-ENERGY-01', 'energy', 'kWh'),
            ('22222222-2222-4222-8222-222222222222'::uuid, 'B-SIM-WATER-01', 'water', 'm3'),
            ('22222222-2222-4222-8222-222222222222'::uuid, 'B-SIM-ENERGY-01', 'energy', 'kWh')
        )
    );

COMMIT;
