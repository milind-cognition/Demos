-- =====================================================================================
-- emp_metrics_daily.sql
--   Daily headcount / hours / overtime by department + Type-2 employee dimension.
--
--   Oozie: hr_daily_wf -> action "emp_metrics_daily" (hive2), runs after the stage shell action
--   Outputs: hr.dim_employee            (full rebuild, SCD2)
--            hr.fct_emp_metrics_daily   (one row per work_date x dept_id)
--   Owner:   hr-data-eng  (orig. author: jdoe 2017, OT logic: mkhan 2021)
--
--   NOTE: oozie passes ${run_date} but the March close re-run hardcoded the pay week below.
--         Do NOT remove the hardcoded dates until finance signs off (HRDE-388).
-- =====================================================================================

SET hive.execution.engine=tez;
SET hive.exec.dynamic.partition.mode=nonstrict;
SET mapreduce.job.queuename=hr_batch;
SET hive.auto.convert.join=true;

USE hr;

-- ---------- staging tables (external, over the shell stage output) ----------
CREATE EXTERNAL TABLE IF NOT EXISTS stg_employees (
  emp_id STRING, first_name STRING, last_name STRING, dept_id STRING, job_title STRING,
  employment_type STRING, pay_type STRING, hourly_rate STRING, hire_date STRING, term_date STRING,
  term_reason STRING, location STRING, manager_id STRING, effective_date STRING, record_source STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
LOCATION '/data/staging/hr/employees/dt=2024-03-15'
TBLPROPERTIES ("skip.header.line.count"="1");

CREATE EXTERNAL TABLE IF NOT EXISTS stg_departments (
  dept_id STRING, dept_name STRING, cost_center STRING, division STRING, region STRING, is_active STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
LOCATION '/data/staging/hr/departments/dt=2024-03-15'
TBLPROPERTIES ("skip.header.line.count"="1");

CREATE EXTERNAL TABLE IF NOT EXISTS stg_timecards (
  timecard_id STRING, emp_id STRING, work_date STRING, pay_code STRING, hours STRING,
  approved_flag STRING, submitted_ts STRING, source_system STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
LOCATION '/data/staging/hr/timecards/dt=2024-03-15'
TBLPROPERTIES ("skip.header.line.count"="1");

-- ---------- 1. Type-2 employee dimension ----------
-- extract sometimes sends the same row twice -> DISTINCT
DROP TABLE IF EXISTS tmp_emp_versions;
CREATE TABLE tmp_emp_versions STORED AS ORC AS
SELECT DISTINCT *
FROM stg_employees
WHERE effective_date <= '2024-03-15';      -- no future-dated HR changes

INSERT OVERWRITE TABLE dim_employee
SELECT
  ROW_NUMBER() OVER (ORDER BY v.emp_id, v.effective_date)            AS employee_sk,
  v.emp_id,
  CONCAT(TRIM(v.first_name), ' ', TRIM(v.last_name))                  AS full_name,
  v.dept_id,
  v.job_title,
  v.employment_type,
  v.pay_type,
  CAST(v.hourly_rate AS DECIMAL(10,2))                                AS hourly_rate,
  v.hire_date,
  v.term_date,
  v.effective_date                                                    AS eff_start_date,
  COALESCE(DATE_SUB(LEAD(v.effective_date) OVER (PARTITION BY v.emp_id ORDER BY v.effective_date), 1),
           '9999-12-31')                                              AS eff_end_date,
  CASE WHEN LEAD(v.effective_date) OVER (PARTITION BY v.emp_id ORDER BY v.effective_date) IS NULL
       THEN 'Y' ELSE 'N' END                                          AS is_current
FROM tmp_emp_versions v;

-- ---------- 2. clean timecards (copied into payroll_join.pig + CohortTagger -- keep in sync!!) ----------
DROP TABLE IF EXISTS tmp_timecards_clean;
CREATE TABLE tmp_timecards_clean STORED AS ORC AS
SELECT *
FROM (
  SELECT
    t.timecard_id,
    t.emp_id,
    FROM_UNIXTIME(UNIX_TIMESTAMP(t.work_date, 'MM/dd/yyyy'), 'yyyy-MM-dd') AS work_dt,
    UPPER(TRIM(t.pay_code))                                               AS pay_code,
    CAST(t.hours AS DECIMAL(10,2))                                        AS hours,
    t.approved_flag,
    ROW_NUMBER() OVER (PARTITION BY t.timecard_id ORDER BY t.submitted_ts DESC) AS rn
  FROM stg_timecards t
) x
WHERE x.rn = 1                    -- KRONOS resubmits corrections under the same id
  AND x.approved_flag = 'Y'
  AND x.work_dt BETWEEN '2024-03-11' AND '2024-03-15';

-- hours per employee per day
DROP TABLE IF EXISTS tmp_emp_day_hours;
CREATE TABLE tmp_emp_day_hours STORED AS ORC AS
SELECT
  emp_id,
  work_dt,
  SUM(CASE WHEN pay_code = 'REG' THEN hours ELSE 0 END)                 AS reg_hours,
  SUM(CASE WHEN pay_code IN ('OT', 'DT') THEN hours ELSE 0 END)         AS ot_hours,
  SUM(CASE WHEN pay_code IN ('PTO', 'HOL') THEN hours ELSE 0 END)       AS pto_hours,
  SUM(hours)                                                            AS total_hours
FROM tmp_timecards_clean
GROUP BY emp_id, work_dt;

-- ---------- 3. active employee x day (SCD2 version valid on the day) ----------
DROP TABLE IF EXISTS tmp_emp_day_active;
CREATE TABLE tmp_emp_day_active STORED AS ORC AS
SELECT d.work_dt, e.*
FROM (SELECT DISTINCT work_dt FROM tmp_timecards_clean) d
CROSS JOIN dim_employee e
WHERE e.eff_start_date <= d.work_dt
  AND e.eff_end_date   >= d.work_dt
  AND e.hire_date      <= d.work_dt
  AND (e.term_date IS NULL OR e.term_date = '' OR e.term_date > d.work_dt);

-- ---------- 4. daily dept fact ----------
INSERT OVERWRITE TABLE fct_emp_metrics_daily
SELECT
  a.work_dt                                                       AS work_date,
  a.dept_id,
  dp.dept_name,
  dp.cost_center,
  COUNT(DISTINCT a.emp_id)                                        AS headcount,
  CAST(SUM(COALESCE(h.reg_hours, 0))   AS DECIMAL(18,2))          AS reg_hours,
  CAST(SUM(COALESCE(h.ot_hours, 0))    AS DECIMAL(18,2))          AS ot_hours,
  CAST(SUM(COALESCE(h.pto_hours, 0))   AS DECIMAL(18,2))          AS pto_hours,
  CAST(SUM(COALESCE(h.total_hours, 0)) AS DECIMAL(18,2))          AS total_hours,
  CASE WHEN SUM(COALESCE(h.total_hours, 0)) > 0
       THEN ROUND(SUM(COALESCE(h.ot_hours, 0)) * 100 / SUM(COALESCE(h.total_hours, 0)), 2)
       ELSE 0 END                                                 AS ot_pct,
  COUNT(DISTINCT CASE WHEN h.ot_hours > 0 THEN a.emp_id END)      AS employees_with_ot
FROM tmp_emp_day_active a
LEFT JOIN tmp_emp_day_hours h
  ON h.emp_id = a.emp_id AND h.work_dt = a.work_dt
LEFT JOIN stg_departments dp          -- left: D999 "unassigned" employees still count
  ON dp.dept_id = a.dept_id
GROUP BY a.work_dt, a.dept_id, dp.dept_name, dp.cost_center;

DROP TABLE IF EXISTS tmp_emp_versions;
DROP TABLE IF EXISTS tmp_timecards_clean;
DROP TABLE IF EXISTS tmp_emp_day_hours;
DROP TABLE IF EXISTS tmp_emp_day_active;
