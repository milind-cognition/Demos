#!/bin/bash
#
# stage_and_publish.sh -- HR daily feed staging + publish
#
#   stage   : pull the SFTP drop, sanity-check headers, write _stage_audit.csv, push to HDFS staging
#   publish : getmerge the job outputs off HDFS into the edge-node publish dir for the downstream SFTP push
#
# usage: stage_and_publish.sh stage   <run_date yyyy-mm-dd>
#        stage_and_publish.sh publish <run_date yyyy-mm-dd>
#
# Called by: oozie hr_daily_wf (stage action) and run_daily.sh (publish, after oozie SUCCEEDED)
# Owner: hr-data-eng   On-call runbook: https://wiki.acme-hcm.internal/display/HRDE/HR+Daily+Feed
#
# LOCAL_MODE=1 swaps hdfs for the local filesystem (used for dev boxes / the qa sandbox).
#

MODE=$1
RUN_DATE=${2:-2024-03-15}     # TODO default should be yesterday, left at march close date - mk

SCRIPT_DIR=`cd "$(dirname "$0")" && pwd`
LEGACY_HOME=${LEGACY_HOME:-`cd $SCRIPT_DIR/.. && pwd`}

SFTP_INBOUND=${SFTP_INBOUND:-/mnt/sftp/inbound/hr}
HDFS_LANDING=/data/landing/hr
HDFS_STAGING=/data/staging/hr
HDFS_WAREHOUSE=/warehouse/hr.db
PUBLISH_DIR=${PUBLISH_DIR:-$LEGACY_HOME/publish}
LOG=/var/log/hr-data/stage_and_publish_${RUN_DATE}.log

if [ "$LOCAL_MODE" == "1" ]; then
  SFTP_INBOUND=${SFTP_INBOUND_LOCAL:-$LEGACY_HOME/sample_data}
  HDFS_LANDING=${LOCAL_ROOT:-/tmp/hr-local}/landing/hr
  HDFS_STAGING=${LOCAL_ROOT:-/tmp/hr-local}/staging/hr
  HDFS_WAREHOUSE=${LOCAL_ROOT:-/tmp/hr-local}/warehouse/hr.db
  LOG=${LOCAL_ROOT:-/tmp/hr-local}/stage_and_publish_${RUN_DATE}.log
fi

mkdir -p `dirname $LOG`

log() {
  echo "`date '+%Y-%m-%d %H:%M:%S'` [stage_and_publish] $*" | tee -a $LOG
}

hdfs_mkdir() {
  if [ "$LOCAL_MODE" == "1" ]; then mkdir -p "$1"; else hdfs dfs -mkdir -p "$1"; fi
}
hdfs_put() {
  if [ "$LOCAL_MODE" == "1" ]; then cp -f "$1" "$2"; else hdfs dfs -put -f "$1" "$2"; fi
}
hdfs_getmerge() {
  if [ "$LOCAL_MODE" == "1" ]; then cat "$1"/* > "$2"; else hdfs dfs -getmerge "$1" "$2"; fi
}

# expected headers -- keep in sync with the hive DDL (yes, by hand)
EXPECTED_departments="dept_id,dept_name,cost_center,division,region,is_active"
EXPECTED_employees="emp_id,first_name,last_name,dept_id,job_title,employment_type,pay_type,hourly_rate,hire_date,term_date,term_reason,location,manager_id,effective_date,record_source"
EXPECTED_timecards="timecard_id,emp_id,work_date,pay_code,hours,approved_flag,submitted_ts,source_system"

# business key columns (1-based) for the duplicate check
KEYCOLS_departments="1"
KEYCOLS_employees="1,14"
KEYCOLS_timecards="1"

do_stage() {
  local stage_tmp=/tmp/hr_stage_$$
  mkdir -p $stage_tmp
  local audit=$stage_tmp/_stage_audit.csv
  echo "load_date,dataset,row_count,distinct_key_count,duplicate_key_count,status" > $audit

  for ds in departments employees timecards; do
    src=$SFTP_INBOUND/$ds.csv
    if [ ! -f $src ]; then
      log "ERROR missing inbound file $src"
      exit 1
    fi
    # strip CRs from the windows-generated KRONOS export
    tr -d '\r' < $src > $stage_tmp/$ds.csv

    hdr=`head -1 $stage_tmp/$ds.csv`
    eval expected=\$EXPECTED_$ds
    if [ "$hdr" != "$expected" ]; then
      log "ERROR header mismatch for $ds"
      log "  got:      $hdr"
      log "  expected: $expected"
      echo "$RUN_DATE,$ds,0,0,0,FAILED_HEADER" >> $audit
      exit 1
    fi

    eval keycols=\$KEYCOLS_$ds
    rows=`tail -n +2 $stage_tmp/$ds.csv | grep -v '^[[:space:]]*$' | wc -l`
    distinct=`tail -n +2 $stage_tmp/$ds.csv | grep -v '^[[:space:]]*$' | cut -d, -f$keycols | sort -u | wc -l`
    dups=$((rows - distinct))
    status=OK
    if [ $dups -gt 0 ]; then
      status=WARN_DUP_KEYS
      log "WARN $ds has $dups duplicate business keys (downstream jobs dedupe)"
    fi
    echo "$RUN_DATE,$ds,$rows,$distinct,$dups,$status" >> $audit
    log "$ds rows=$rows distinct_keys=$distinct"

    hdfs_mkdir $HDFS_LANDING/$ds/dt=$RUN_DATE
    hdfs_put $src $HDFS_LANDING/$ds/dt=$RUN_DATE/$ds.csv
    hdfs_mkdir $HDFS_STAGING/$ds/dt=$RUN_DATE
    hdfs_put $stage_tmp/$ds.csv $HDFS_STAGING/$ds/dt=$RUN_DATE/$ds.csv
  done

  hdfs_mkdir $HDFS_STAGING/_audit/dt=$RUN_DATE
  hdfs_put $audit $HDFS_STAGING/_audit/dt=$RUN_DATE/_stage_audit.csv
  rm -rf $stage_tmp
  log "stage complete for $RUN_DATE"
}

do_publish() {
  local out=$PUBLISH_DIR/$RUN_DATE
  mkdir -p $out
  # table dir -> published file name
  for pair in \
      dim_employee:dim_employee \
      fct_emp_metrics_daily:fct_emp_metrics_daily \
      payroll_by_employee:payroll_by_employee \
      payroll_by_cost_center:payroll_by_cost_center \
      employee_cohorts:employee_cohorts ; do
    tbl=${pair%%:*}
    name=${pair##*:}
    if [ "$LOCAL_MODE" == "1" ] && [ ! -d $HDFS_WAREHOUSE/$tbl ]; then
      log "skip $tbl (not built locally)"
      continue
    fi
    hdfs_getmerge $HDFS_WAREHOUSE/$tbl $out/$name.csv
    log "published $name.csv (`wc -l < $out/$name.csv` lines)"
  done
  # turnover only exists on month-close days
  if [ -d $HDFS_WAREHOUSE/turnover_snapshot ] || [ "$LOCAL_MODE" != "1" ]; then
    hdfs_getmerge $HDFS_WAREHOUSE/turnover_snapshot $out/turnover_snapshot.csv 2>/dev/null || log "no turnover snapshot today"
  fi
  touch $out/_SUCCESS
  log "publish complete -> $out"
}

case "$MODE" in
  stage)   do_stage ;;
  publish) do_publish ;;
  *) echo "usage: $0 {stage|publish} <run_date>"; exit 2 ;;
esac
