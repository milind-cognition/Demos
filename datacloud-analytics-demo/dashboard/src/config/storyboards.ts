/**
 * Storyboards: curated pages that compose metric cards and charts into a narrative.
 * Each `metric` must be a key in public/metrics/index.json (enforced by config.test.ts).
 */
export type ChartKind =
  /** Company-wide total over time. */
  | "trend"
  /** One line per department over time. */
  | "departments"
  /** Latest period, one bar per department. */
  | "breakdown"
  /** Latest period, one bar per group against the company-wide value; groups above it are flagged. */
  | "benchmark";

export interface StoryboardSection {
  metric: string;
  chart: ChartKind;
  title: string;
  narrative: string;
}

export interface Storyboard {
  id: string;
  title: string;
  description: string;
  /** Metric keys rendered as headline cards at the top of the page. */
  headline: string[];
  sections: StoryboardSection[];
}

export const STORYBOARDS: Storyboard[] = [
  {
    id: "workforce-overview",
    title: "Workforce Overview",
    description: "Trailing twelve months across all departments.",
    headline: ["headcount", "turnover", "overtime"],
    sections: [
      {
        metric: "headcount",
        chart: "trend",
        title: "Headcount trend",
        narrative: "Seasonal warehouse hiring lifts Q4 headcount; the January roll-off resets the baseline.",
      },
      {
        metric: "turnover",
        chart: "trend",
        title: "Monthly turnover",
        narrative: "January spikes as seasonal assignments end; underlying attrition holds near 2% a month.",
      },
      {
        metric: "overtime",
        chart: "breakdown",
        title: "Where overtime concentrates",
        narrative: "Hourly, non-exempt teams in logistics and payroll carry most overtime hours.",
      },
    ],
  },
  {
    id: "retention",
    title: "Retention & Attrition",
    description: "Who is leaving, and how it shapes the size of each team.",
    headline: ["turnover", "headcount"],
    sections: [
      {
        metric: "turnover",
        chart: "breakdown",
        title: "Turnover by department, latest month",
        narrative: "Frontline teams turn over fastest; engineering and finance are comparatively stable.",
      },
      {
        metric: "headcount",
        chart: "departments",
        title: "Headcount by department",
        narrative: "Product Engineering is the main growth engine; most teams backfill to plan.",
      },
    ],
  },
  {
    id: "labor-utilization",
    title: "Overtime & Labor Utilization",
    description: "How much of the work week runs on overtime, and where.",
    headline: ["overtime"],
    sections: [
      {
        metric: "overtime",
        chart: "trend",
        title: "Company-wide overtime rate",
        narrative: "Overtime peaks in December with the holiday shipping surge and year-end payroll close.",
      },
      {
        metric: "overtime",
        chart: "departments",
        title: "Overtime rate by department",
        narrative: "Warehouse and Fleet run consistently above the company rate; exempt teams sit near zero.",
      },
    ],
  },
  {
    id: "overtime-cost-benchmark",
    title: "Overtime Cost Benchmark",
    description: "What overtime costs per employee in each industry cohort, against the company-wide figure.",
    headline: ["overtime_cost_per_employee", "overtime"],
    sections: [
      {
        metric: "overtime_cost_per_employee",
        chart: "trend",
        title: "Company-wide overtime cost per employee",
        narrative: "Peaks at $563 in December with the holiday surge, then eases to $239 in September from $335 in August.",
      },
      {
        metric: "overtime_cost_per_employee",
        chart: "benchmark",
        title: "Where we are running hot",
        narrative:
          "Transportation & Logistics ($498) and Financial Services ($317) sit above the $239 company figure; Field Operations has no staff yet.",
      },
      {
        metric: "overtime_cost_per_employee",
        chart: "departments",
        title: "Overtime cost per employee by cohort",
        narrative:
          "The company figure is the headcount-weighted average of these lines; Transportation & Logistics leads in 11 of 12 months.",
      },
      {
        metric: "overtime",
        chart: "breakdown",
        title: "Overtime rate by department, latest month",
        narrative: "In hours, Warehouse (9.2%) and Fleet (8.5%) run hottest against a 3.8% company rate.",
      },
    ],
  },
];

export function findStoryboard(id: string | null): Storyboard | undefined {
  return id === null ? STORYBOARDS[0] : STORYBOARDS.find((s) => s.id === id);
}
