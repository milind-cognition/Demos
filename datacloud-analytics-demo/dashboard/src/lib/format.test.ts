import { describe, expect, it } from "vitest";

import { formatDelta, formatPeriod, formatPeriodShort, formatValue } from "./format";

describe("formatValue", () => {
  it("formats each unit", () => {
    expect(formatValue(1250, "count")).toBe("1,250");
    expect(formatValue(4.236, "percent")).toBe("4.2%");
    expect(formatValue(1840, "currency")).toBe("$1,840");
    expect(formatValue(1_250_000, "currency")).toBe("$1.3M");
    expect(formatValue(312, "hours")).toBe("312 hrs");
    expect(formatValue(1.075, "index")).toBe("1.07");
  });
});

describe("formatDelta", () => {
  it("signs changes and uses percentage points for percents", () => {
    expect(formatDelta(4, "count")).toBe("+4");
    expect(formatDelta(-0.42, "percent")).toBe("−0.4 pts");
    expect(formatDelta(0, "count")).toBe("±0");
  });
});

describe("formatPeriod", () => {
  it("renders YYYY-MM periods", () => {
    expect(formatPeriod("2026-09")).toBe("Sep 2026");
    expect(formatPeriodShort("2025-12")).toBe("Dec ’25");
  });
});
