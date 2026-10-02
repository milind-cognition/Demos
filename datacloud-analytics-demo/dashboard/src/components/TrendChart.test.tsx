import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { generatedMetrics, makePayload } from "../test/fixtures";
import { TrendChart } from "./TrendChart";

describe("TrendChart benchmark", () => {
  it("names the cohorts above the company-wide value", () => {
    render(<TrendChart payload={generatedMetrics.overtime_cost_per_employee!} kind="benchmark" />);
    expect(screen.getByTestId("flags-overtime_cost_per_employee")).toHaveTextContent(
      "Above company-wide: Transportation & Logistics, Financial Services",
    );
  });

  it("says so when no group is above the company-wide value", () => {
    const payload = makePayload({ total: [{ period: "2026-09", value: 36 }], periods: ["2026-09"] });
    render(<TrendChart payload={payload} kind="benchmark" />);
    expect(screen.getByTestId("flags-headcount")).toHaveTextContent("No group is above the company-wide value.");
  });
});
