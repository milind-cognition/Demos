import type { MetricPayload } from "../types";

export interface BenchmarkRow {
  department: string;
  value: number;
  /** Strictly above the company-wide value for the same period. */
  flagged: boolean;
}

export interface Benchmark {
  period: string | undefined;
  company: number | undefined;
  rows: BenchmarkRow[];
}

/** Latest-period value per group against the company-wide total, highest first. */
export function benchmarkLatest(payload: MetricPayload): Benchmark {
  const period = payload.periods.at(-1);
  const company = payload.total.find((p) => p.period === period)?.value;
  const rows = payload.by_department
    .map((dept) => {
      const value = dept.series.find((p) => p.period === period)?.value ?? 0;
      return { department: dept.department, value, flagged: company !== undefined && value > company };
    })
    .sort((a, b) => b.value - a.value);
  return { period, company, rows };
}
