WITH RECURSIVE
header AS (
  SELECT CASE WHEN
    (SELECT COUNT(total_slots) FROM budget) != 1 OR
    EXISTS (SELECT 1 FROM budget WHERE total_slots IS NULL OR total_slots NOT BETWEEN 0 AND 8) OR
    (SELECT COUNT(group_id) FROM groups) NOT BETWEEN 1 AND 3 OR
    EXISTS (SELECT 1 FROM groups WHERE group_id IS NULL OR length(CAST(group_id AS BLOB)) NOT BETWEEN 1 AND 64
      OR min_slots IS NULL OR max_slots IS NULL OR min_slots NOT BETWEEN 0 AND 8
      OR max_slots NOT BETWEEN min_slots AND 8) OR
    (SELECT COUNT(group_id) FROM groups) != (SELECT COUNT(DISTINCT group_id) FROM groups) OR
    (SELECT COUNT(scenario_id) FROM scenarios) NOT BETWEEN 1 AND 4 OR
    EXISTS (SELECT 1 FROM scenarios WHERE scenario_id IS NULL OR length(CAST(scenario_id AS BLOB)) NOT BETWEEN 1 AND 64) OR
    (SELECT COUNT(scenario_id) FROM scenarios) != (SELECT COUNT(DISTINCT scenario_id) FROM scenarios) OR
    EXISTS (SELECT 1 FROM forecasts AS f
      WHERE f.group_id IS NULL OR f.scenario_id IS NULL OR f.demand NOT BETWEEN 0 AND 1000000
      OR NOT EXISTS (SELECT 1 FROM groups AS g WHERE g.group_id = f.group_id)
      OR NOT EXISTS (SELECT 1 FROM scenarios AS s WHERE s.scenario_id = f.scenario_id)) OR
    EXISTS (SELECT 1 FROM forecasts GROUP BY scenario_id, group_id HAVING COUNT(group_id) != 1)
  THEN 0 ELSE 1 END AS valid
),
missing AS (
  SELECT s.scenario_id, g.group_id FROM scenarios AS s CROSS JOIN groups AS g
  LEFT JOIN forecasts AS f ON f.scenario_id = s.scenario_id AND f.group_id = g.group_id
  WHERE f.demand IS NULL
),
disposition AS (
  SELECT CASE WHEN NOT valid THEN 'INVALID_INPUT'
    WHEN EXISTS (SELECT 1 FROM missing) THEN 'MISSING_FORECAST'
    WHEN (SELECT SUM(min_slots) FROM groups) > (SELECT total_slots FROM budget) THEN 'INFEASIBLE_MINIMA'
    ELSE 'OK' END AS verdict
  FROM header
),
ordered_groups AS (
  SELECT group_id, min_slots, max_slots, ROW_NUMBER() OVER (ORDER BY group_id) AS position FROM groups
),
slot_values(n) AS (VALUES (0), (1), (2), (3), (4), (5), (6), (7), (8)),
decisions(position, used, choice) AS (
  SELECT 0, 0, '' FROM disposition WHERE verdict = 'OK'
  UNION ALL
  SELECT d.position + 1, d.used + v.n, d.choice || v.n FROM decisions AS d
  JOIN ordered_groups AS g ON g.position = d.position + 1
  CROSS JOIN slot_values AS v CROSS JOIN budget AS b
  WHERE v.n BETWEEN g.min_slots AND g.max_slots AND d.used + v.n <= b.total_slots
),
scores AS MATERIALIZED (
  SELECT d.choice, f.scenario_id,
    SUM(MIN(f.demand, CAST(substr(d.choice, g.position, 1) AS INTEGER))) AS service
  FROM decisions AS d CROSS JOIN ordered_groups AS g
  JOIN forecasts AS f ON f.group_id = g.group_id
  WHERE d.position = (SELECT COUNT(group_id) FROM groups)
  GROUP BY d.choice, f.scenario_id
),
scenario_oracles AS MATERIALIZED (
  SELECT choice, scenario_id, service FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY scenario_id ORDER BY service DESC, choice) AS preference
    FROM scores
  ) WHERE preference = 1
),
best AS (
  SELECT s.choice, MAX(o.service - s.service) AS worst_regret, SUM(s.service) AS total_service
  FROM scores AS s JOIN scenario_oracles AS o USING (scenario_id)
  GROUP BY s.choice ORDER BY worst_regret, total_service DESC, s.choice LIMIT 1
),
allocation AS (
  SELECT s.scenario_id, g.group_id, f.demand,
    CAST(substr(b.choice, g.position, 1) AS INTEGER) AS slots,
    CAST(substr(o.choice, g.position, 1) AS INTEGER) AS oracle_slots,
    o.service - s.service AS regret, b.worst_regret, b.total_service
  FROM best AS b JOIN scores AS s ON s.choice = b.choice
  JOIN scenario_oracles AS o USING (scenario_id)
  JOIN forecasts AS f USING (scenario_id)
  JOIN ordered_groups AS g USING (group_id)
),
service AS (
  SELECT *, MIN(slots, demand) AS served, MIN(oracle_slots, demand) AS oracle_served FROM allocation
)
SELECT 'OK' AS verdict, scenario_id, group_id, slots, demand, served, demand - served,
  oracle_slots, oracle_served, oracle_served - served, regret, worst_regret, total_service
FROM service
UNION ALL
SELECT verdict, m.scenario_id, m.group_id, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM disposition CROSS JOIN missing AS m WHERE verdict = 'MISSING_FORECAST'
UNION ALL
SELECT verdict, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM disposition WHERE verdict IN ('INVALID_INPUT', 'INFEASIBLE_MINIMA')
ORDER BY scenario_id, group_id
