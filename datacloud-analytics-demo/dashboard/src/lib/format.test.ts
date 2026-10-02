import { describe, expect, it } from "vitest";

import { displayedChange, formatDelta, formatPeriod, formatPeriodShort, formatValue } from "./format";

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

describe("displayedChange", () => {
  it("agrees with the rounded values shown on screen", () => {
    expect(displayedChange(0.52, 0.48, "percent")).toBe(0);
    expect(formatDelta(displayedChange(0.52, 0.48, "percent"), "percent")).toBe("±0.0 pts");
    expect(displayedChange(0.56, 0.44, "percent")).toBe(0.2);
  });

  it("never renders a signed zero", () => {
    expect(formatDelta(-0.04, "percent")).toBe("±0.0 pts");
    expect(formatDelta(0.3, "count")).toBe("±0");
  });
});
