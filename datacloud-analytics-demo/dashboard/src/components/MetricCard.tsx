import { cardConfig } from "../config/metricCards";
import { formatDelta, formatPeriod, formatValue } from "../lib/format";
import { metricHref } from "../lib/router";
import { summarizeMetric } from "../lib/summary";
import type { MetricPayload } from "../types";
import { Sparkline } from "./TrendChart";

export interface MetricCardProps {
  payload: MetricPayload;
  /** Link the card to the metric's detail page. */
  linked?: boolean;
}

export function MetricCard({ payload, linked = true }: MetricCardProps) {
  const config = cardConfig(payload.key);
  const summary = summarizeMetric(payload);
  const body = (
    <>
      <div className="metric-card__header">
        <span className="metric-card__label">{payload.label}</span>
        {summary.latest && <span className="metric-card__period">{formatPeriod(summary.latest.period)}</span>}
      </div>
      <div className="metric-card__value" data-testid={`headline-${payload.key}`}>
        {summary.latest ? formatValue(summary.latest.value, payload.unit) : "—"}
      </div>
      <div className="metric-card__meta">
        {summary.delta !== null && (
          <span className={`delta delta--${summary.sentiment}`} data-testid={`delta-${payload.key}`}>
            {formatDelta(summary.delta, payload.unit)}
          </span>
        )}
        <span className="metric-card__vs">vs prior month</span>
      </div>
      <Sparkline payload={payload} accent={config.accent} />
      {config.caption && <p className="metric-card__caption">{config.caption}</p>}
    </>
  );
  const style = { "--accent": config.accent } as React.CSSProperties;
  return linked ? (
    <a className="metric-card metric-card--link" href={metricHref(payload.key)} style={style}>
      {body}
    </a>
  ) : (
    <div className="metric-card" style={style}>
      {body}
    </div>
  );
}
