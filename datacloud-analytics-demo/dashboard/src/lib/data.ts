import type { MetricIndex, MetricPayload } from "../types";

const METRICS_BASE = `${import.meta.env.BASE_URL}metrics/`;

async function getJson<T>(file: string): Promise<T> {
  const response = await fetch(`${METRICS_BASE}${file}`);
  if (!response.ok) {
    throw new Error(`Failed to load metrics/${file} (HTTP ${response.status}). Run scripts/compute_metrics.py.`);
  }
  return (await response.json()) as T;
}

export interface MetricsBundle {
  index: MetricIndex;
  metrics: Record<string, MetricPayload>;
}

export async function loadMetrics(): Promise<MetricsBundle> {
  const index = await getJson<MetricIndex>("index.json");
  const payloads = await Promise.all(index.metrics.map((entry) => getJson<MetricPayload>(entry.file)));
  return { index, metrics: Object.fromEntries(payloads.map((p) => [p.key, p])) };
}
