import type { MetricIndex, MetricPayload } from "../types";

/** The checked-in JSON written by scripts/compute_metrics.py, keyed by file name. */
const files = import.meta.glob<unknown>("../../public/metrics/*.json", { eager: true, import: "default" });

export const generatedFiles: Record<string, unknown> = Object.fromEntries(
  Object.entries(files).map(([path, json]) => [path.split("/").at(-1)!, json]),
);

export const generatedIndex = generatedFiles["index.json"] as MetricIndex;

export const generatedMetrics: Record<string, MetricPayload> = Object.fromEntries(
  generatedIndex.metrics.map((entry) => [entry.key, generatedFiles[entry.file] as MetricPayload]),
);

export function makePayload(overrides: Partial<MetricPayload> = {}): MetricPayload {
  return {
    schema_version: 1,
    key: "headcount",
    label: "Headcount",
    description: "Active employees on the last day of the period.",
    unit: "count",
    higher_is_better: true,
    periods: ["2026-07", "2026-08", "2026-09"],
    total: [
      { period: "2026-07", value: 240 },
      { period: "2026-08", value: 246 },
      { period: "2026-09", value: 250 },
    ],
    by_department: [
      {
        department: "Sales",
        series: [
          { period: "2026-07", value: 30 },
          { period: "2026-08", value: 33 },
          { period: "2026-09", value: 36 },
        ],
      },
    ],
    ...overrides,
  };
}

/** Serve `generatedFiles` through a stubbed fetch, as Vite would serve public/metrics/. */
export function fetchFromGenerated(input: RequestInfo | URL): Promise<Response> {
  const name = String(input).split("/").at(-1)!;
  const body = generatedFiles[name];
  return Promise.resolve(
    body === undefined
      ? new Response("not found", { status: 404 })
      : new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } }),
  );
}
