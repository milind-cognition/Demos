import { describe, expect, it } from "vitest";

import { makePayload } from "../test/fixtures";
import { benchmarkLatest } from "./benchmark";

const series = (values: [number, number]) => [
  { period: "2026-08", value: values[0] },
  { period: "2026-09", value: values[1] },
];

const payload = makePayload({
  unit: "currency",
  periods: ["2026-08", "2026-09"],
  total: series([300, 250]),
  by_department: [
    { department: "Above", series: series([100, 250.01]) },
    { department: "At", series: series([999, 250]) },
    { department: "Below", series: series([999, 249.99]) },
    { department: "Empty", series: series([0, 0]) },
  ],
});

describe("benchmarkLatest", () => {
  it("compares the latest period against the company-wide value", () => {
    const benchmark = benchmarkLatest(payload);
    expect(benchmark.period).toBe("2026-09");
    expect(benchmark.company).toBe(250);
  });

  it("flags only groups strictly above the company value, highest first", () => {
    expect(benchmarkLatest(payload).rows).toEqual([
      { department: "Above", value: 250.01, flagged: true },
      { department: "At", value: 250, flagged: false },
      { department: "Below", value: 249.99, flagged: false },
      { department: "Empty", value: 0, flagged: false },
    ]);
  });

  it("flags nothing when the company value is missing", () => {
    const rows = benchmarkLatest({ ...payload, total: [] }).rows;
    expect(rows.some((r) => r.flagged)).toBe(false);
  });
});
