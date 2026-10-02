import { describe, expect, it } from "vitest";

import { makePayload } from "../test/fixtures";
import { sentimentFor, summarizeMetric } from "./summary";

describe("summarizeMetric", () => {
  it("compares the latest period to the prior one", () => {
    const summary = summarizeMetric(makePayload());
    expect(summary.latest).toEqual({ period: "2026-09", value: 250 });
    expect(summary.delta).toBe(4);
    expect(summary.sentiment).toBe("positive");
    expect(summary.average).toBeCloseTo(245.33, 2);
  });

  it("is neutral when the change rounds to zero", () => {
    const summary = summarizeMetric(
      makePayload({
        unit: "percent",
        total: [
          { period: "2026-08", value: 0.52 },
          { period: "2026-09", value: 0.48 },
        ],
      }),
    );
    expect(summary.delta).toBe(0);
    expect(summary.sentiment).toBe("neutral");
  });

  it("handles a single-period series", () => {
    const summary = summarizeMetric(makePayload({ total: [{ period: "2026-09", value: 1 }] }));
    expect(summary.delta).toBeNull();
    expect(summary.sentiment).toBe("neutral");
  });
});

describe("sentimentFor", () => {
  it("respects metric direction", () => {
    expect(sentimentFor(1, false)).toBe("negative");
    expect(sentimentFor(-1, false)).toBe("positive");
    expect(sentimentFor(0, true)).toBe("neutral");
  });
});
