import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { STORYBOARDS, type Storyboard } from "../config/storyboards";
import { generatedMetrics } from "../test/fixtures";
import { StoryboardPage } from "./StoryboardPage";

describe("StoryboardPage", () => {
  it.each(STORYBOARDS.map((s) => [s.id, s] as const))("renders every card and section for %s", (_id, storyboard) => {
    render(<StoryboardPage storyboard={storyboard} metrics={generatedMetrics} />);
    expect(screen.getByRole("heading", { level: 1, name: storyboard.title })).toBeInTheDocument();
    for (const key of storyboard.headline) {
      expect(screen.getByTestId(`headline-${key}`)).toBeInTheDocument();
    }
    for (const section of storyboard.sections) {
      expect(screen.getByRole("heading", { level: 2, name: section.title })).toBeInTheDocument();
      expect(screen.getByTestId(`chart-${section.metric}-${section.chart}`)).toBeInTheDocument();
    }
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("warns when a storyboard references a metric that was not computed", () => {
    const storyboard: Storyboard = {
      id: "draft",
      title: "Draft",
      description: "",
      headline: ["not_computed"],
      sections: [],
    };
    render(<StoryboardPage storyboard={storyboard} metrics={generatedMetrics} />);
    expect(screen.getByRole("alert")).toHaveTextContent("not_computed");
  });
});
