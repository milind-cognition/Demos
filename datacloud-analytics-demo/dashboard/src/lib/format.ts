import type { MetricUnit } from "../types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function parsePeriod(period: string): { year: string; month: string } {
  const [year = "", month = "01"] = period.split("-");
  return { year, month: MONTHS[Number(month) - 1] ?? month };
}

/** "2026-09" -> "Sep 2026" */
export function formatPeriod(period: string): string {
  const { year, month } = parsePeriod(period);
  return `${month} ${year}`;
}

/** "2026-09" -> "Sep ’26" */
export function formatPeriodShort(period: string): string {
  const { year, month } = parsePeriod(period);
  return `${month} ’${year.slice(-2)}`;
}

const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const compactCurrency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function formatValue(value: number, unit: MetricUnit, options: { compact?: boolean } = {}): string {
  switch (unit) {
    case "count":
      return integer.format(value);
    case "percent":
      return `${value.toFixed(1)}%`;
    case "currency":
      return options.compact || Math.abs(value) >= 100_000 ? compactCurrency.format(value) : currency.format(value);
    case "hours":
      return `${integer.format(value)} hrs`;
    case "index":
      return value.toFixed(2);
  }
}

const DISPLAY_DECIMALS: Record<MetricUnit, number> = { count: 0, percent: 1, currency: 0, hours: 0, index: 2 };

/** Round to the precision `formatValue` displays for the unit. */
export function roundForDisplay(value: number, unit: MetricUnit): number {
  const factor = 10 ** DISPLAY_DECIMALS[unit];
  return Math.round(value * factor) / factor;
}

/** `current - previous` as displayed, so a change always agrees with the two values shown beside it. */
export function displayedChange(current: number, previous: number, unit: MetricUnit): number {
  return roundForDisplay(roundForDisplay(current, unit) - roundForDisplay(previous, unit), unit);
}

/** Signed change between two values; percents are reported in percentage points. */
export function formatDelta(delta: number, unit: MetricUnit): string {
  const rounded = roundForDisplay(delta, unit);
  const sign = rounded > 0 ? "+" : rounded < 0 ? "−" : "±";
  const magnitude = Math.abs(rounded);
  switch (unit) {
    case "percent":
      return `${sign}${magnitude.toFixed(1)} pts`;
    case "count":
      return `${sign}${integer.format(magnitude)}`;
    default:
      return `${sign}${formatValue(magnitude, unit, { compact: true })}`;
  }
}
