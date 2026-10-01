\echo 'TEST 1: Without tenant context, expected count = 0'
SELECT current_user;
SELECT count(*) AS visible_without_tenant FROM bws_ai.readings;

BEGIN;
SET LOCAL app.tenant_id = '11111111-1111-4111-8111-111111111111';

\echo 'TEST 2: Client A sees only A-WATER-01 and A-ENERGY-01'
SELECT sensor_id, value, unit
FROM bws_ai.readings
ORDER BY sensor_id;

\echo 'TEST 3: Client A requests Client B data, expected count = 0'
SELECT count(*) AS cross_tenant_visible
FROM bws_ai.readings
WHERE tenant_id = '22222222-2222-4222-8222-222222222222';
COMMIT;

BEGIN;
SET LOCAL app.tenant_id = '22222222-2222-4222-8222-222222222222';

\echo 'TEST 4: Client B sees only B-WATER-01 and B-ENERGY-01'
SELECT sensor_id, value, unit
FROM bws_ai.readings
ORDER BY sensor_id;
COMMIT;

\echo 'TEST 5: After transaction, expected count = 0'
SELECT count(*) AS visible_after_transaction FROM bws_ai.readings;
