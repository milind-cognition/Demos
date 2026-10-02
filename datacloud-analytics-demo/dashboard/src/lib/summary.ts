import type { MetricPayload, SeriesPoint } from "../types";

export type Sentiment = "positive" | "negative" | "neutral";

export interface MetricSummary {
  latest: SeriesPoint | undefined;
  previous: SeriesPoint | undefined;
  delta: number | null;
  sentiment: Sentiment;
  average: number | null;
}

export function sentimentFor(delta: number | null, higherIsBetter: boolean): Sentiment {
  if (delta === null || Math.abs(delta) < 1e-9) return "neutral";
  return delta > 0 === higherIsBetter ? "positive" : "negative";
}

export function summarize(series: SeriesPoint[], higherIsBetter: boolean): MetricSummary {
  const latest = series.at(-1);
  const previous = series.at(-2);
  const delta = latest && previous ? latest.value - previous.value : null;
  const average = series.length ? series.reduce((sum, p) => sum + p.value, 0) / series.length : null;
  return { latest, previous, delta, sentiment: sentimentFor(delta, higherIsBetter), average };
}

export function summarizeMetric(payload: MetricPayload): MetricSummary {
  return summarize(payload.total, payload.higher_is_better);
}

export function latestPeriod(payload: MetricPayload): string | undefined {
  return payload.periods.at(-1);
}
