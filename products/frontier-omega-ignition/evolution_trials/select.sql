-- Times are integer nanoseconds since the Unix epoch; thresholds are evaluated on the publisher's decimal quantities.
WITH latest AS (
    SELECT n.t AS issue, o.*,
           row_number() OVER (PARTITION BY n.t, o.target, o.band
                              ORDER BY o.t DESC, length(o.candid), o.candid) AS position
      FROM nights n JOIN valid o ON o.t >= n.t - :day AND o.t < n.t
), pairs AS (
    SELECT c.target, c.band, c.issue, c.candid AS current_id, b.candid AS base_id,
           c.mag AS current_mag, c.err AS current_err, c.t AS current_t,
           b.mag AS base_mag, b.err AS base_err, b.t AS base_t,
           row_number() OVER (PARTITION BY c.issue, c.target, c.band
                              ORDER BY abs(c.t - b.t - 2*:day), b.t, length(b.candid), b.candid) AS priority
      FROM latest c JOIN history b ON b.target=c.target AND b.band=c.band
                   AND b.ref=c.ref AND c.t - b.t BETWEEN :day/2 AND 7*:day
     WHERE c.position=1
), tested AS (
    SELECT *, trigger_pass(base_mag,current_mag,base_err,current_err,current_t-base_t) AS fires
      FROM pairs WHERE priority=1
), first_issue AS (
    SELECT target, band, min(issue) AS issued
      FROM tested WHERE fires=1 GROUP BY target, band
), issued AS (
    SELECT t.* FROM tested t JOIN first_issue f
        ON t.target=f.target AND t.band=f.band AND t.issue=f.issued
), follow_options AS (
    SELECT i.target, i.band, f.candid AS next_id, f.mag AS next_mag, f.err AS next_err,
           row_number() OVER (PARTITION BY i.target,i.band ORDER BY f.t,length(f.candid),f.candid) AS priority
      FROM issued i JOIN valid f ON f.target=i.target AND f.band=i.band
        AND f.ref=(SELECT ref FROM valid WHERE candid=i.current_id) AND f.t>=i.issue AND f.t - i.current_t >= :day/2 AND f.t < i.issue+3*:day
), examined AS (
    SELECT t.* FROM tested t LEFT JOIN first_issue f ON f.target=t.target AND f.band=t.band
     WHERE f.issued IS NULL OR t.issue<=f.issued
), strongest AS (
    SELECT *, row_number() OVER (PARTITION BY target,band
             ORDER BY change_abs(base_mag,current_mag) COLLATE magnitude DESC, issue) AS strongest_rank
      FROM examined
), comparisons AS (
    SELECT t.target,t.band,count(*) AS number FROM examined t
     GROUP BY t.target,t.band
), observed AS (
    SELECT target,band,count(*) AS number FROM valid GROUP BY target,band
)
SELECT r.target,b.band,coalesce(o.number,0) AS detections,coalesce(c.number,0) AS comparisons,
       i.issue,i.base_id,i.current_id,f.next_id,
       s.issue AS strongest_issue,s.base_id AS strongest_base,s.current_id AS strongest_current,
       CASE WHEN i.issue IS NULL THEN 'no_trigger'
            WHEN f.next_id IS NOT NULL THEN follow_disposition(i.base_mag,i.current_mag,f.next_mag,i.base_err,f.next_err)
            WHEN i.issue+3*:day <= :cutoff THEN 'coverage_gap'
            WHEN :cutoff >= :end THEN 'right_censored' ELSE 'awaiting_repeat' END AS status
  FROM roster r CROSS JOIN bands b
  LEFT JOIN observed o ON o.target=r.target AND o.band=b.band
  LEFT JOIN comparisons c ON c.target=r.target AND c.band=b.band
  LEFT JOIN strongest s ON s.target=r.target AND s.band=b.band AND s.strongest_rank=1
  LEFT JOIN issued i ON i.target=r.target AND i.band=b.band
  LEFT JOIN follow_options f ON f.target=r.target AND f.band=b.band AND f.priority=1
ORDER BY r.target,b.band;
