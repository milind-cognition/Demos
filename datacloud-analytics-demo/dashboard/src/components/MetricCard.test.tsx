import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { makePayload } from "../test/fixtures";
import { MetricCard } from "./MetricCard";

describe("MetricCard", () => {
  it("shows the headline number, period, and change", () => {
    render(<MetricCard payload={makePayload()} />);
    expect(screen.getByText("Headcount")).toBeInTheDocument();
    expect(screen.getByText("Sep 2026")).toBeInTheDocument();
    expect(screen.getByTestId("headline-headcount")).toHaveTextContent("250");
    expect(screen.getByTestId("delta-headcount")).toHaveTextContent("+4");
    expect(screen.getByTestId("delta-headcount")).toHaveClass("delta--positive");
  });

  it("marks an increase as negative when lower is better", () => {
    const payload = makePayload({
      key: "turnover",
      label: "Turnover Rate",
      unit: "percent",
      higher_is_better: false,
      total: [
        { period: "2026-08", value: 1.5 },
        { period: "2026-09", value: 2.0 },
      ],
    });
    render(<MetricCard payload={payload} />);
    expect(screen.getByTestId("headline-turnover")).toHaveTextContent("2.0%");
    expect(screen.getByTestId("delta-turnover")).toHaveTextContent("+0.5 pts");
    expect(screen.getByTestId("delta-turnover")).toHaveClass("delta--negative");
  });

  it("links to the metric page", () => {
    render(<MetricCard payload={makePayload()} />);
    expect(screen.getByRole("link")).toHaveAttribute("href", "#/metrics/headcount");
  });
});
