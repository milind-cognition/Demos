import { describe, expect, it } from "vitest";

import { generatedIndex, generatedMetrics } from "../test/fixtures";
import { METRIC_CARDS } from "./metricCards";
import { STORYBOARDS } from "./storyboards";

const computedKeys = generatedIndex.metrics.map((m) => m.key);

describe("dashboard config matches computed metrics", () => {
  it("has a payload file for every index entry", () => {
    for (const key of computedKeys) {
      expect(generatedMetrics[key]?.key, `public/metrics/${key}.json`).toBe(key);
    }
  });

  it("has a card config for every computed metric", () => {
    expect(Object.keys(METRIC_CARDS).sort()).toEqual([...computedKeys].sort());
  });

  it("only references computed metrics in storyboards", () => {
    for (const storyboard of STORYBOARDS) {
      const referenced = [...storyboard.headline, ...storyboard.sections.map((s) => s.metric)];
      for (const key of referenced) {
        expect(computedKeys, `storyboard "${storyboard.id}" references "${key}"`).toContain(key);
      }
    }
  });

  it("features every computed metric on at least one storyboard", () => {
    const featured = new Set(STORYBOARDS.flatMap((s) => s.headline));
    for (const key of computedKeys) {
      expect(featured.has(key), `metric "${key}" is not on any storyboard`).toBe(true);
    }
  });

  it("uses unique storyboard ids", () => {
    const ids = STORYBOARDS.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
