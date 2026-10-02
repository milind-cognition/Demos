/**
 * Dashboard presentation for each metric key in public/metrics/index.json.
 * Every computed metric needs an entry here (enforced by config.test.ts).
 */
export interface MetricCardConfig {
  /** Accent used for the card rule, sparkline, and charts. */
  accent: string;
  /** One-line plain-English definition shown under the headline number. */
  caption: string;
}

export const METRIC_CARDS: Record<string, MetricCardConfig> = {
  headcount: { accent: "#3e63dd", caption: "Active employees at period end" },
  turnover: { accent: "#0e7c86", caption: "Leavers ÷ average headcount, monthly" },
  overtime: { accent: "#6e56cf", caption: "Overtime share of all hours worked" },
  overtime_cost_per_employee: { accent: "#a16207", caption: "Overtime pay (1.5×) per active employee" },
};

export const FALLBACK_CARD: MetricCardConfig = { accent: "#475467", caption: "" };

export function cardConfig(key: string): MetricCardConfig {
  return METRIC_CARDS[key] ?? FALLBACK_CARD;
}
