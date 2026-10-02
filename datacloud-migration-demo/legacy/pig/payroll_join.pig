/*
 * payroll_join.pig -- weekly gross-pay estimate for hourly associates
 *
 *   Oozie: hr_daily_wf -> action "payroll_join" (runs after emp_metrics_daily)
 *   Inputs : staged employees / departments / timecards (shell stage action)
 *   Outputs: /warehouse/hr.db/payroll_by_employee     one row per hourly employee with hours
 *            /warehouse/hr.db/payroll_by_cost_center  rollup for the GL accrual feed
 *   Owner  : payroll-analytics (pig because "hive was too slow in 2016")
 *
 *   Pay rule: (REG + PTO/HOL) * rate + OT * rate * 1.5
 *             DT is paid at 1.5x here pending PAY-1123 (payroll engine pays the real 2.0x).
 *             JURY and other codes count toward total_hours but are not paid by this estimate.
 *   Rate   : rate on the HR record current at pay-period end (NOT per-day like hive).
 */

SET job.name 'hr_daily.payroll_join';
SET default_parallel 4;
SET mapreduce.job.queuename 'hr_batch';

%default RUN_DATE   '2024-03-15'
%default STAGING    '/data/staging/hr'
%default WAREHOUSE  '/warehouse/hr.db'

-- FIXME pay period should be derived from RUN_DATE (HRDE-388). hardcoded for March close.
%declare PERIOD_START '2024-03-11'
%declare PERIOD_END   '2024-03-15'

-- ------------------------------------------------------------------ timecards
raw_tc = LOAD '$STAGING/timecards/dt=$RUN_DATE/timecards.csv' USING PigStorage(',') AS (
    timecard_id:chararray, emp_id:chararray, work_date:chararray, pay_code:chararray,
    hours:chararray, approved_flag:chararray, submitted_ts:chararray, source_system:chararray);

tc_body = FILTER raw_tc BY timecard_id != 'timecard_id';   -- header row

-- corrections are resubmitted with the same timecard_id: keep the latest submission
tc_by_id = GROUP tc_body BY timecard_id;
tc_latest = FOREACH tc_by_id {
    srt  = ORDER tc_body BY submitted_ts DESC;
    top1 = LIMIT srt 1;
    GENERATE FLATTEN(top1);
};

tc_norm = FOREACH tc_latest GENERATE
    top1::emp_id                                                        AS emp_id,
    ToString(ToDate(top1::work_date, 'MM/dd/yyyy'), 'yyyy-MM-dd')       AS work_dt,
    UPPER(TRIM(top1::pay_code))                                         AS pay_code,
    (double) top1::hours                                                AS hours,
    top1::approved_flag                                                 AS approved_flag;

tc_ok = FILTER tc_norm BY approved_flag == 'Y'
                      AND work_dt >= '$PERIOD_START'
                      AND work_dt <= '$PERIOD_END';

-- same bucketing as hive tmp_emp_day_hours / CohortTagger.loadOtHours
tc_coded = FOREACH tc_ok GENERATE
    emp_id,
    (pay_code == 'REG' ? hours : 0.0)                           AS reg_hours,
    ((pay_code == 'OT'  OR pay_code == 'DT')  ? hours : 0.0)    AS ot_hours,
    ((pay_code == 'PTO' OR pay_code == 'HOL') ? hours : 0.0)    AS pto_hours,
    hours                                                       AS total_hours;

hrs_by_emp = GROUP tc_coded BY emp_id;
emp_hours = FOREACH hrs_by_emp GENERATE
    group                       AS emp_id,
    SUM(tc_coded.reg_hours)     AS reg_hours,
    SUM(tc_coded.ot_hours)      AS ot_hours,
    SUM(tc_coded.pto_hours)     AS pto_hours,
    SUM(tc_coded.total_hours)   AS total_hours;

-- ------------------------------------------------------------------ employees
raw_emp = LOAD '$STAGING/employees/dt=$RUN_DATE/employees.csv' USING PigStorage(',') AS (
    emp_id:chararray, first_name:chararray, last_name:chararray, dept_id:chararray,
    job_title:chararray, employment_type:chararray, pay_type:chararray, hourly_rate:chararray,
    hire_date:chararray, term_date:chararray, term_reason:chararray, location:chararray,
    manager_id:chararray, effective_date:chararray, record_source:chararray);

emp_body = FILTER raw_emp BY emp_id != 'emp_id' AND effective_date <= '$PERIOD_END';

emp_by_id = GROUP emp_body BY emp_id;
emp_cur = FOREACH emp_by_id {
    srt  = ORDER emp_body BY effective_date DESC;
    top1 = LIMIT srt 1;
    GENERATE FLATTEN(top1);
};

-- termed employees are kept on purpose: their final check still needs an estimate
emp_hourly = FILTER emp_cur BY top1::pay_type == 'HOURLY';

emp_slim = FOREACH emp_hourly GENERATE
    top1::emp_id                                                        AS emp_id,
    CONCAT(TRIM(top1::first_name), CONCAT(' ', TRIM(top1::last_name)))  AS full_name,
    top1::dept_id                                                       AS dept_id,
    (double) top1::hourly_rate                                          AS hourly_rate;

-- ------------------------------------------------------------------ departments
raw_dept = LOAD '$STAGING/departments/dt=$RUN_DATE/departments.csv' USING PigStorage(',') AS (
    dept_id:chararray, dept_name:chararray, cost_center:chararray, division:chararray,
    region:chararray, is_active:chararray);
dept = FILTER raw_dept BY dept_id != 'dept_id';

-- ------------------------------------------------------------------ join + pay
j_emp  = JOIN emp_hours BY emp_id, emp_slim BY emp_id;
j_dept = JOIN j_emp BY emp_slim::dept_id, dept BY dept_id;   -- inner: D999 / unknown depts drop out

pay = FOREACH j_dept GENERATE
    '$PERIOD_START'                         AS pay_period_start,
    '$PERIOD_END'                           AS pay_period_end,
    emp_hours::emp_id                       AS emp_id,
    emp_slim::full_name                     AS full_name,
    emp_slim::dept_id                       AS dept_id,
    dept::dept_name                         AS dept_name,
    dept::cost_center                       AS cost_center,
    dept::region                            AS region,
    emp_slim::hourly_rate                   AS hourly_rate,
    emp_hours::reg_hours                    AS reg_hours,
    emp_hours::ot_hours                     AS ot_hours,
    emp_hours::pto_hours                    AS pto_hours,
    emp_hours::total_hours                  AS total_hours,
    -- 4 == java.math.RoundingMode.HALF_UP
    ROUND_TO(((emp_hours::reg_hours + emp_hours::pto_hours) * emp_slim::hourly_rate)
             + (emp_hours::ot_hours * emp_slim::hourly_rate * 1.5), 2, 4)   AS gross_pay,
    (emp_hours::ot_hours > 0.0 ? 'Y' : 'N') AS ot_flag;

by_employee = FOREACH pay GENERATE
    pay_period_start, pay_period_end, emp_id, full_name, dept_id, dept_name, cost_center,
    hourly_rate, reg_hours, ot_hours, pto_hours, total_hours, gross_pay, ot_flag;

rmf $WAREHOUSE/payroll_by_employee
STORE by_employee INTO '$WAREHOUSE/payroll_by_employee' USING PigStorage(',');

-- ------------------------------------------------------------------ GL accrual rollup
-- sums the already-rounded employee gross_pay (matches what payroll posts)
pay_by_cc = GROUP pay BY (cost_center, region);
by_cost_center = FOREACH pay_by_cc GENERATE
    '$PERIOD_START'                         AS pay_period_start,
    '$PERIOD_END'                           AS pay_period_end,
    FLATTEN(group)                          AS (cost_center, region),
    COUNT(pay)                              AS employee_count,
    ROUND_TO(SUM(pay.total_hours), 2, 4)    AS total_hours,
    ROUND_TO(SUM(pay.ot_hours), 2, 4)       AS ot_hours,
    ROUND_TO(SUM(pay.gross_pay), 2, 4)      AS gross_pay;

rmf $WAREHOUSE/payroll_by_cost_center
STORE by_cost_center INTO '$WAREHOUSE/payroll_by_cost_center' USING PigStorage(',');
