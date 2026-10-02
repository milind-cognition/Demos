-- =====================================================================================
-- turnover_snapshot.sql  -- monthly turnover by department (month close)
--
--   NOT in oozie. run_daily.sh runs it on the 1st of the month (or FORCE_TURNOVER=1).
--   Output: hr.turnover_snapshot (full overwrite, one row per snapshot_month x dept_id)
--   Owner:  hr-data-eng / people-analytics (Q1 FY24 board deck)
--
--   HACK: finance asked for Jan-Mar restated in one shot, so the three months are
--         UNIONed with hardcoded dates. Copy the block for April. (HRDE-402)
--   NOTE: "active" here uses term_date >= day (people analytics definition -- an employee
--         termed ON the day still counts). emp_metrics_daily uses term_date > day.
--         Known, documented, do not "fix" without people-analytics sign off.
-- =====================================================================================

SET hive.execution.engine=tez;
SET mapreduce.job.queuename=hr_batch;

USE hr;

-- latest HR record per employee as of quarter end
-- (same idea as tmp_emp_versions in emp_metrics_daily.sql, but latest-only)
DROP TABLE IF EXISTS tmp_emp_latest;
CREATE TABLE tmp_emp_latest STORED AS ORC AS
SELECT *
FROM (
  SELECT e.*,
         ROW_NUMBER() OVER (PARTITION BY e.emp_id ORDER BY e.effective_date DESC) AS rn
  FROM stg_employees e
  WHERE e.effective_date <= '2024-03-31'
) x
WHERE x.rn = 1;

INSERT OVERWRITE TABLE turnover_snapshot
SELECT * FROM (

  -- ===== January 2024 =====
  SELECT
    '2024-01'                                                                     AS snapshot_month,
    e.dept_id, d.dept_name, d.region,
    SUM(CASE WHEN e.hire_date <= '2024-01-01'
              AND (e.term_date = '' OR e.term_date IS NULL OR e.term_date >= '2024-01-01') THEN 1 ELSE 0 END) AS headcount_start,
    SUM(CASE WHEN e.hire_date <= '2024-01-31'
              AND (e.term_date = '' OR e.term_date IS NULL OR e.term_date >= '2024-01-31') THEN 1 ELSE 0 END) AS headcount_end,
    SUM(CASE WHEN e.hire_date BETWEEN '2024-01-01' AND '2024-01-31' THEN 1 ELSE 0 END)                       AS hires,
    SUM(CASE WHEN e.term_date BETWEEN '2024-01-01' AND '2024-01-31' THEN 1 ELSE 0 END)                       AS terminations,
    SUM(CASE WHEN e.term_date BETWEEN '2024-01-01' AND '2024-01-31'
              AND e.term_reason = 'VOLUNTARY' THEN 1 ELSE 0 END)                                             AS voluntary_terminations
  FROM tmp_emp_latest e
  JOIN stg_departments d ON d.dept_id = e.dept_id
  GROUP BY e.dept_id, d.dept_name, d.region

  UNION ALL

  -- ===== February 2024 =====  (leap year! 29th)
  SELECT
    '2024-02'                                                                     AS snapshot_month,
    e.dept_id, d.dept_name, d.region,
    SUM(CASE WHEN e.hire_date <= '2024-02-01'
              AND (e.term_date = '' OR e.term_date IS NULL OR e.term_date >= '2024-02-01') THEN 1 ELSE 0 END) AS headcount_start,
    SUM(CASE WHEN e.hire_date <= '2024-02-29'
              AND (e.term_date = '' OR e.term_date IS NULL OR e.term_date >= '2024-02-29') THEN 1 ELSE 0 END) AS headcount_end,
    SUM(CASE WHEN e.hire_date BETWEEN '2024-02-01' AND '2024-02-29' THEN 1 ELSE 0 END)                       AS hires,
    SUM(CASE WHEN e.term_date BETWEEN '2024-02-01' AND '2024-02-29' THEN 1 ELSE 0 END)                       AS terminations,
    SUM(CASE WHEN e.term_date BETWEEN '2024-02-01' AND '2024-02-29'
              AND e.term_reason = 'VOLUNTARY' THEN 1 ELSE 0 END)                                             AS voluntary_terminations
  FROM tmp_emp_latest e
  JOIN stg_departments d ON d.dept_id = e.dept_id
  GROUP BY e.dept_id, d.dept_name, d.region

  UNION ALL

  -- ===== March 2024 =====
  SELECT
    '2024-03'                                                                     AS snapshot_month,
    e.dept_id, d.dept_name, d.region,
    SUM(CASE WHEN e.hire_date <= '2024-03-01'
              AND (e.term_date = '' OR e.term_date IS NULL OR e.term_date >= '2024-03-01') THEN 1 ELSE 0 END) AS headcount_start,
    SUM(CASE WHEN e.hire_date <= '2024-03-31'
              AND (e.term_date = '' OR e.term_date IS NULL OR e.term_date >= '2024-03-31') THEN 1 ELSE 0 END) AS headcount_end,
    SUM(CASE WHEN e.hire_date BETWEEN '2024-03-01' AND '2024-03-31' THEN 1 ELSE 0 END)                       AS hires,
    SUM(CASE WHEN e.term_date BETWEEN '2024-03-01' AND '2024-03-31' THEN 1 ELSE 0 END)                       AS terminations,
    SUM(CASE WHEN e.term_date BETWEEN '2024-03-01' AND '2024-03-31'
              AND e.term_reason = 'VOLUNTARY' THEN 1 ELSE 0 END)                                             AS voluntary_terminations
  FROM tmp_emp_latest e
  JOIN stg_departments d ON d.dept_id = e.dept_id
  GROUP BY e.dept_id, d.dept_name, d.region

) m
-- turnover % = terms / avg(start, end) headcount
LATERAL VIEW INLINE(ARRAY(STRUCT(
  CASE WHEN (m.headcount_start + m.headcount_end) > 0
       THEN ROUND(m.terminations * 100 / ((m.headcount_start + m.headcount_end) / 2), 2)
       ELSE 0 END
))) r AS turnover_rate_pct
WHERE m.headcount_start > 0 OR m.headcount_end > 0 OR m.hires > 0 OR m.terminations > 0;

DROP TABLE IF EXISTS tmp_emp_latest;
