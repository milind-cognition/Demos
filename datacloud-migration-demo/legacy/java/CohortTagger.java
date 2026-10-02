package com.acme.hrdata.jobs;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

/**
 * CohortTagger - tags every active employee with a hire cohort / tenure band / OT segment.
 *
 * Owner: HR Data Eng (hr-data-eng@acme-hcm.com)
 * Runs on the EMR master node from run_daily.sh AFTER the Oozie daily flow finishes.
 *
 *   java -cp hr-jobs-1.4.2.jar com.acme.hrdata.jobs.CohortTagger \
 *        employees.csv timecards.csv employee_cohorts.csv
 *
 * Downstream: Tableau "Workforce Cohorts" workbook + the retention model feature store.
 *
 * NOTE: plain CSV split, no quoting support. The HR extract is guaranteed comma-free (ticket HRDE-212).
 */
public class CohortTagger {

    // FIXME(HRDE-388): as-of date should come from args/oozie. Hardcoded for March close re-run.
    private static final String AS_OF_DATE = "2024-03-15";
    // pay week for the OT segment -- same window the hive + pig jobs use
    private static final String OT_WINDOW_START = "2024-03-11";
    private static final String OT_WINDOW_END = "2024-03-15";

    private static final double HIGH_OT_THRESHOLD = 8.0;

    // employees.csv columns
    private static final int E_EMP_ID = 0;
    private static final int E_DEPT_ID = 3;
    private static final int E_PAY_TYPE = 6;
    private static final int E_HIRE_DATE = 8;
    private static final int E_TERM_DATE = 9;
    private static final int E_EFFECTIVE_DATE = 13;

    // timecards.csv columns
    private static final int T_TIMECARD_ID = 0;
    private static final int T_EMP_ID = 1;
    private static final int T_WORK_DATE = 2;
    private static final int T_PAY_CODE = 3;
    private static final int T_HOURS = 4;
    private static final int T_APPROVED = 5;
    private static final int T_SUBMITTED_TS = 6;

    public static void main(String[] args) throws Exception {
        if (args.length < 3) {
            System.err.println("usage: CohortTagger <employees.csv> <timecards.csv> <out.csv>");
            System.exit(2);
        }
        Map<String, String[]> employees = loadCurrentEmployees(args[0]);
        Map<String, Double> otHours = loadOtHours(args[1]);
        int written = writeCohorts(employees, otHours, args[2]);
        System.out.println("CohortTagger: wrote " + written + " rows to " + args[2]);
    }

    /** latest HR version per emp_id with effective_date <= AS_OF_DATE */
    static Map<String, String[]> loadCurrentEmployees(String path) throws IOException {
        Map<String, String[]> latest = new TreeMap<String, String[]>();
        List<String[]> rows = readCsv(path);
        for (String[] r : rows) {
            if (r[E_EFFECTIVE_DATE].compareTo(AS_OF_DATE) > 0) {
                continue;
            }
            String[] prev = latest.get(r[E_EMP_ID]);
            if (prev == null || r[E_EFFECTIVE_DATE].compareTo(prev[E_EFFECTIVE_DATE]) > 0) {
                latest.put(r[E_EMP_ID], r);
            }
        }
        return latest;
    }

    /** copy of the hive/pig hours rollup: dedupe resubmissions, approved only, OT = OT + DT */
    static Map<String, Double> loadOtHours(String path) throws IOException, ParseException {
        SimpleDateFormat in = new SimpleDateFormat("MM/dd/yyyy");
        SimpleDateFormat iso = new SimpleDateFormat("yyyy-MM-dd");
        Map<String, String[]> latestCard = new HashMap<String, String[]>();
        for (String[] r : readCsv(path)) {
            String[] prev = latestCard.get(r[T_TIMECARD_ID]);
            if (prev == null || r[T_SUBMITTED_TS].compareTo(prev[T_SUBMITTED_TS]) > 0) {
                latestCard.put(r[T_TIMECARD_ID], r);
            }
        }
        Map<String, Double> ot = new HashMap<String, Double>();
        for (String[] r : latestCard.values()) {
            if (!"Y".equals(r[T_APPROVED])) {
                continue;
            }
            String workDate = iso.format(in.parse(r[T_WORK_DATE]));
            if (workDate.compareTo(OT_WINDOW_START) < 0 || workDate.compareTo(OT_WINDOW_END) > 0) {
                continue;
            }
            String code = r[T_PAY_CODE].trim().toUpperCase();
            if (code.equals("OT") || code.equals("DT")) {
                Double cur = ot.get(r[T_EMP_ID]);
                ot.put(r[T_EMP_ID], (cur == null ? 0.0 : cur) + Double.parseDouble(r[T_HOURS]));
            }
        }
        return ot;
    }

    static int writeCohorts(Map<String, String[]> employees, Map<String, Double> otHours, String out)
            throws IOException, ParseException {
        SimpleDateFormat iso = new SimpleDateFormat("yyyy-MM-dd");
        Date asOf = iso.parse(AS_OF_DATE);
        int n = 0;
        BufferedWriter w = new BufferedWriter(new FileWriter(out));
        try {
            w.write("emp_id,dept_id,pay_type,hire_date,tenure_years,tenure_band,hire_cohort,ot_hours,ot_segment,cohort_tag");
            w.newLine();
            for (String[] e : employees.values()) {
                String term = e[E_TERM_DATE];
                if (term != null && term.length() > 0 && term.compareTo(AS_OF_DATE) <= 0) {
                    continue; // termed on/before as-of
                }
                Date hire = iso.parse(e[E_HIRE_DATE]);
                int years = fullYearsBetween(hire, asOf);
                String band;
                if (years < 1) {
                    band = "LT1Y";
                } else if (years < 3) {
                    band = "1TO3Y";
                } else if (years < 5) {
                    band = "3TO5Y";
                } else {
                    band = "5YPLUS";
                }
                String cohort = fiscalCohort(hire);
                Double ot = otHours.get(e[E_EMP_ID]);
                double otVal = ot == null ? 0.0 : ot.doubleValue();
                String segment;
                if ("SALARY".equals(e[E_PAY_TYPE])) {
                    segment = "EXEMPT";
                } else if (otVal >= HIGH_OT_THRESHOLD) {
                    segment = "HIGH_OT";
                } else if (otVal > 0) {
                    segment = "SOME_OT";
                } else {
                    segment = "NO_OT";
                }
                w.write(e[E_EMP_ID] + "," + e[E_DEPT_ID] + "," + e[E_PAY_TYPE] + "," + e[E_HIRE_DATE] + ","
                        + years + "," + band + "," + cohort + "," + String.format(Locale.US, "%.2f", otVal) + ","
                        + segment + "," + cohort + "_" + band + "_" + segment);
                w.newLine();
                n++;
            }
        } finally {
            w.close();
        }
        return n;
    }

    static int fullYearsBetween(Date from, Date to) {
        Calendar a = Calendar.getInstance();
        a.setTime(from);
        Calendar b = Calendar.getInstance();
        b.setTime(to);
        int years = b.get(Calendar.YEAR) - a.get(Calendar.YEAR);
        if (b.get(Calendar.MONTH) < a.get(Calendar.MONTH)
                || (b.get(Calendar.MONTH) == a.get(Calendar.MONTH)
                    && b.get(Calendar.DAY_OF_MONTH) < a.get(Calendar.DAY_OF_MONTH))) {
            years--;
        }
        return years;
    }

    /** fiscal year starts July 1: hire 2019-08-12 -> FY20-Q1 */
    static String fiscalCohort(Date hire) {
        Calendar c = Calendar.getInstance();
        c.setTime(hire);
        int month = c.get(Calendar.MONTH) + 1;
        int fy = month >= 7 ? c.get(Calendar.YEAR) + 1 : c.get(Calendar.YEAR);
        int q = month >= 7 ? (month - 7) / 3 + 1 : (month + 5) / 3 + 1;
        return String.format("FY%02d-Q%d", fy % 100, q);
    }

    static List<String[]> readCsv(String path) throws IOException {
        List<String[]> rows = new ArrayList<String[]>();
        BufferedReader r = new BufferedReader(new FileReader(path));
        try {
            String line = r.readLine(); // header
            while ((line = r.readLine()) != null) {
                if (line.trim().length() == 0) {
                    continue;
                }
                rows.add(line.split(",", -1));
            }
        } finally {
            r.close();
        }
        return rows;
    }
}
