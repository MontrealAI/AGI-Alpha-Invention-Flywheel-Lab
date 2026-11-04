-- Bind :raw to the complete synthetic JSON order. All amounts use integer cents.
WITH metrics AS (
    SELECT
        value ->> '$.metric' AS metric,
        value ->> '$.prior_cents' AS prior_cents,
        value ->> '$.current_cents' AS current_cents
    FROM json_each(:raw, '$.source_order.metrics')
), changes AS (
    SELECT *, current_cents - prior_cents AS delta_cents FROM metrics
)
SELECT json_object(
    'order_id', :raw ->> '$.order_id',
    'scope', :raw ->> '$.scope',
    'currency', :raw ->> '$.currency',
    'rows', json_group_array(json_object(
        'metric', metric, 'prior_cents', prior_cents, 'current_cents', current_cents,
        'delta_cents', delta_cents, 'direction',
        CASE WHEN delta_cents > 0 THEN 'UP' WHEN delta_cents < 0 THEN 'DOWN' ELSE 'UNCHANGED' END,
        'change_ratio', json(CASE WHEN prior_cents = 0 THEN 'null' ELSE json_array(delta_cents, prior_cents) END)
    ) ORDER BY metric),
    'totals', json_object(
        'prior_cents', COALESCE(SUM(prior_cents), 0),
        'current_cents', COALESCE(SUM(current_cents), 0),
        'delta_cents', COALESCE(SUM(delta_cents), 0)
    )
)
FROM changes;
