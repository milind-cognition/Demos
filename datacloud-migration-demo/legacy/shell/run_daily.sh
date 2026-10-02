#!/bin/bash
# run_daily.sh -- cron entry point for the HR daily batch on the EMR master node
#
#   crontab (hadoop@emr-hr-prod-master):
#   15 6 * * * /home/hadoop/hr-jobs/shell/run_daily.sh >> /var/log/hr-data/run_daily.log 2>&1
#
# 1. submits the oozie coordinator run for today (stage -> emp_metrics_daily -> payroll_join)
# 2. polls oozie until the workflow finishes
# 3. runs CohortTagger (java, not in oozie -- "temporary" since 2019)
# 4. on the 1st of the month runs the turnover snapshot hive script
# 5. publishes everything to the edge node + drops _SUCCESS for the SFTP pusher
#
# !! if this fails, re-run by hand with: run_daily.sh 2024-03-15

RUN_DATE=$1
if [ -z "$RUN_DATE" ]; then
  RUN_DATE=`date -d yesterday +%Y-%m-%d`
fi

HR_HOME=/home/hadoop/hr-jobs
OOZIE_URL=http://emr-hr-prod-master.acme-hcm.internal:11000/oozie
NAME_NODE=hdfs://emr-hr-prod-master.acme-hcm.internal:8020
JAR=$HR_HOME/java/hr-jobs-1.4.2.jar
ALERT_EMAIL=hr-data-eng@acme-hcm.com

echo "=== run_daily $RUN_DATE start `date` ==="

# --- 1. oozie ---
JOB_ID=`oozie job -oozie $OOZIE_URL -config $HR_HOME/oozie/job.properties \
  -D runDate=$RUN_DATE -D nameNode=$NAME_NODE -run | awk -F': ' '{print $2}'`
echo "submitted oozie workflow $JOB_ID"

# --- 2. poll (max ~2h) ---
STATUS=RUNNING
i=0
while [ "$STATUS" == "RUNNING" ] || [ "$STATUS" == "PREP" ]; do
  sleep 60
  STATUS=`oozie job -oozie $OOZIE_URL -info $JOB_ID | grep '^Status' | awk '{print $3}'`
  i=$((i+1))
  if [ $i -gt 120 ]; then
    echo "oozie job $JOB_ID still running after 2h, giving up"
    echo "hr daily $RUN_DATE TIMEOUT $JOB_ID" | mail -s "[HR-DAILY] TIMEOUT $RUN_DATE" $ALERT_EMAIL
    exit 1
  fi
done
if [ "$STATUS" != "SUCCEEDED" ]; then
  echo "oozie job $JOB_ID ended $STATUS"
  echo "hr daily $RUN_DATE $STATUS $JOB_ID" | mail -s "[HR-DAILY] FAILED $RUN_DATE" $ALERT_EMAIL
  exit 1
fi

# --- 3. cohort tagger (reads the staged CSVs straight off hdfs) ---
WORK=/mnt/tmp/hr_daily_$RUN_DATE
rm -rf $WORK; mkdir -p $WORK
hdfs dfs -get /data/staging/hr/employees/dt=$RUN_DATE/employees.csv $WORK/
hdfs dfs -get /data/staging/hr/timecards/dt=$RUN_DATE/timecards.csv $WORK/
java -Xmx2g -cp $JAR com.acme.hrdata.jobs.CohortTagger \
  $WORK/employees.csv $WORK/timecards.csv $WORK/employee_cohorts.csv || exit 1
hdfs dfs -mkdir -p /warehouse/hr.db/employee_cohorts
hdfs dfs -put -f $WORK/employee_cohorts.csv /warehouse/hr.db/employee_cohorts/000000_0

# --- 4. month close ---
if [ `date -d $RUN_DATE +%d` == "01" ] || [ "$FORCE_TURNOVER" == "1" ]; then
  echo "month close -> turnover snapshot"
  hive -hiveconf hive.execution.engine=tez -f $HR_HOME/hive/turnover_snapshot.sql || exit 1
fi

# --- 5. publish ---
$HR_HOME/shell/stage_and_publish.sh publish $RUN_DATE || exit 1

echo "=== run_daily $RUN_DATE done `date` ==="
