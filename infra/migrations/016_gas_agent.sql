BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER TABLE bws_ai.readings DROP CONSTRAINT readings_resource_check;
ALTER TABLE bws_ai.readings ADD CONSTRAINT readings_resource_check
    CHECK (resource IN ('water', 'energy', 'gas'));
ALTER TABLE bws_ai.readings DROP CONSTRAINT readings_check;
ALTER TABLE bws_ai.readings ADD CONSTRAINT readings_check CHECK (
    (resource IN ('water', 'gas') AND unit = 'm3')
    OR (resource = 'energy' AND unit = 'kWh')
);
ALTER TABLE bws_ai.analyses DROP CONSTRAINT analyses_agent_check;
ALTER TABLE bws_ai.analyses ADD CONSTRAINT analyses_agent_check
    CHECK (agent IN ('water', 'energy', 'gas'));
ALTER TABLE bws_ai.chat_confirmations DROP CONSTRAINT chat_confirmations_resource_check;
ALTER TABLE bws_ai.chat_confirmations ADD CONSTRAINT chat_confirmations_resource_check
    CHECK (resource IN ('water', 'energy', 'gas'));
ALTER TABLE bws_ai.chat_conversations DROP CONSTRAINT chat_conversations_resource_check;
ALTER TABLE bws_ai.chat_conversations ADD CONSTRAINT chat_conversations_resource_check
    CHECK (resource IN ('water', 'energy', 'gas'));

CREATE POLICY simulator_gas_read ON bws_ai.readings
    FOR SELECT TO aegisai_simulator USING (
        data_source = 'synthetic_live_v1'
        AND resource = 'gas' AND unit = 'm3'
        AND (tenant_id, sensor_id) IN (
            ('11111111-1111-4111-8111-111111111111'::uuid, 'A-SIM-GAS-01'),
            ('22222222-2222-4222-8222-222222222222'::uuid, 'B-SIM-GAS-01')
        )
    );
CREATE POLICY simulator_gas_insert ON bws_ai.readings
    FOR INSERT TO aegisai_simulator WITH CHECK (
        data_source = 'synthetic_live_v1'
        AND resource = 'gas' AND unit = 'm3'
        AND (tenant_id, sensor_id) IN (
            ('11111111-1111-4111-8111-111111111111'::uuid, 'A-SIM-GAS-01'),
            ('22222222-2222-4222-8222-222222222222'::uuid, 'B-SIM-GAS-01')
        )
        AND interval_seconds = 3600
        AND value >= 0 AND value < 10000
        AND measured_at = date_trunc('hour', measured_at)
        AND measured_at + interval '1 hour' <= clock_timestamp()
        AND measured_at >= clock_timestamp() - interval '7 days'
    );
COMMIT;
