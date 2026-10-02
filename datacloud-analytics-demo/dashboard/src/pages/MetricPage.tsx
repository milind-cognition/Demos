import { DepartmentTable } from "../components/DepartmentTable";
import { PageHeader, Panel } from "../components/Panel";
import { TrendChart } from "../components/TrendChart";
import { cardConfig } from "../config/metricCards";
import { formatDelta, formatPeriod, formatValue } from "../lib/format";
import { summarizeMetric } from "../lib/summary";
import type { MetricPayload } from "../types";

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className={`stat__value${tone ? ` delta--${tone}` : ""}`}>{value}</span>
    </div>
  );
}

export function MetricPage({ payload }: { payload: MetricPayload }) {
  const summary = summarizeMetric(payload);
  const first = payload.total[0];
  const yearChange = summary.latest && first ? summary.latest.value - first.value : null;
  const accent = cardConfig(payload.key).accent;
  return (
    <div className="page">
      <PageHeader eyebrow={`Metric · ${payload.key}`} title={payload.label} description={payload.description} />

      <div className="stat-row" style={{ "--accent": accent } as React.CSSProperties}>
        <Stat
          label={summary.latest ? formatPeriod(summary.latest.period) : "Latest"}
          value={summary.latest ? formatValue(summary.latest.value, payload.unit) : "—"}
        />
        <Stat
          label="Change vs prior month"
          value={summary.delta !== null ? formatDelta(summary.delta, payload.unit) : "—"}
          tone={summary.sentiment}
        />
        <Stat label="12-month average" value={summary.average !== null ? formatValue(summary.average, payload.unit) : "—"} />
        <Stat
          label={first ? `Change since ${formatPeriod(first.period)}` : "12-month change"}
          value={yearChange !== null ? formatDelta(yearChange, payload.unit) : "—"}
        />
      </div>

      <div className="section-grid">
        <Panel title="All departments" subtitle="Company-wide value by month">
          <TrendChart payload={payload} kind="trend" accent={accent} />
        </Panel>
        <Panel title="By department" subtitle="Monthly value per department">
          <TrendChart payload={payload} kind="departments" />
        </Panel>
      </div>

      <Panel title="Department detail">
        <DepartmentTable payload={payload} />
      </Panel>
    </div>
  );
}
