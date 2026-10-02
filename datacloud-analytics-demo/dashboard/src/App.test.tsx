import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { STORYBOARDS } from "./config/storyboards";
import { fetchFromGenerated, generatedIndex } from "./test/fixtures";

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(fetchFromGenerated));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads metrics and opens the first storyboard with nav for every metric", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: STORYBOARDS[0]!.title })).toBeInTheDocument();
    const metricsNav = screen.getByRole("navigation", { name: "Metrics" });
    for (const metric of generatedIndex.metrics) {
      expect(metricsNav).toHaveTextContent(metric.label);
    }
  });

  it("routes to a metric detail page", async () => {
    window.location.hash = "#/metrics/overtime";
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: "Overtime Rate" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveTextContent("Warehouse Operations");
  });

  it("shows an error when metrics are missing", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response("", { status: 404 }))));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("compute_metrics.py");
  });
});
