import { MetricCard } from "../components/MetricCard";
import { Notice, PageHeader, Panel } from "../components/Panel";
import { TrendChart } from "../components/TrendChart";
import { cardConfig } from "../config/metricCards";
import type { Storyboard } from "../config/storyboards";
import { formatPeriod } from "../lib/format";
import type { MetricPayload } from "../types";

export interface StoryboardPageProps {
  storyboard: Storyboard;
  metrics: Record<string, MetricPayload>;
}

function MissingMetric({ metricKey }: { metricKey: string }) {
  return (
    <Notice>
      Metric <code>{metricKey}</code> has no computed data. Run <code>python scripts/compute_metrics.py</code>.
    </Notice>
  );
}

export function StoryboardPage({ storyboard, metrics }: StoryboardPageProps) {
  const periods = Object.values(metrics)[0]?.periods ?? [];
  const range = periods.length ? `${formatPeriod(periods[0]!)} – ${formatPeriod(periods.at(-1)!)}` : "";
  return (
    <div className="page">
      <PageHeader eyebrow={`Storyboard${range ? ` · ${range}` : ""}`} title={storyboard.title} description={storyboard.description} />

      <div className="card-grid">
        {storyboard.headline.map((key) => {
          const payload = metrics[key];
          return payload ? <MetricCard key={key} payload={payload} /> : <MissingMetric key={key} metricKey={key} />;
        })}
      </div>

      <div className="section-grid">
        {storyboard.sections.map((section) => {
          const payload = metrics[section.metric];
          return (
            <Panel key={`${section.metric}-${section.chart}`} title={section.title} subtitle={section.narrative}>
              {payload ? (
                <TrendChart payload={payload} kind={section.chart} accent={cardConfig(payload.key).accent} />
              ) : (
                <MissingMetric metricKey={section.metric} />
              )}
            </Panel>
          );
        })}
      </div>
    </div>
  );
}
