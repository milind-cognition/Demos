export type MetricUnit = "count" | "percent" | "currency" | "hours" | "index";

export interface SeriesPoint {
  period: string;
  value: number;
}

export interface DepartmentSeries {
  department: string;
  series: SeriesPoint[];
}

/** Shape of `public/metrics/<key>.json`, written by scripts/compute_metrics.py. */
export interface MetricPayload {
  schema_version: number;
  key: string;
  label: string;
  description: string;
  unit: MetricUnit;
  higher_is_better: boolean;
  periods: string[];
  total: SeriesPoint[];
  by_department: DepartmentSeries[];
}

export interface MetricIndexEntry {
  key: string;
  label: string;
  unit: MetricUnit;
  file: string;
}

/** Shape of `public/metrics/index.json`. */
export interface MetricIndex {
  schema_version: number;
  metrics: MetricIndexEntry[];
}
