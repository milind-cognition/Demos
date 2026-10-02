import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ChartKind } from "../config/storyboards";
import { formatPeriod, formatPeriodShort, formatValue } from "../lib/format";
import type { MetricPayload } from "../types";

const DEPARTMENT_PALETTE = ["#3e63dd", "#0e7c86", "#6e56cf", "#c2410c", "#4d7c0f", "#be185d", "#475467", "#a16207"];
const AXIS = { stroke: "#98a2b3", fontSize: 12 };
const GRID = "#eaecf0";

export interface TrendChartProps {
  payload: MetricPayload;
  kind?: ChartKind;
  accent?: string;
  height?: number;
}

function TotalTrend({ payload, accent, height }: Required<Omit<TrendChartProps, "kind">>) {
  const gradientId = `fill-${payload.key}`;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={payload.total} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity={0.18} />
            <stop offset="100%" stopColor={accent} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="period" tickFormatter={formatPeriodShort} tickLine={false} axisLine={false} tick={AXIS} />
        <YAxis
          width={56}
          tickFormatter={(v: number) => formatValue(v, payload.unit, { compact: true })}
          tickLine={false}
          axisLine={false}
          tick={AXIS}
          domain={payload.unit === "count" ? ["dataMin - 10", "dataMax + 10"] : [0, "auto"]}
        />
        <Tooltip
          labelFormatter={(label) => formatPeriod(String(label))}
          formatter={(value) => [formatValue(Number(value), payload.unit), payload.label]}
        />
        <Area
          type="monotone"
          dataKey="value"
          stroke={accent}
          strokeWidth={2}
          fill={`url(#${gradientId})`}
          dot={false}
          activeDot={{ r: 4 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function DepartmentLines({ payload, height }: Required<Omit<TrendChartProps, "kind" | "accent">>) {
  const rows = payload.periods.map((period) => {
    const row: Record<string, string | number> = { period };
    for (const dept of payload.by_department) {
      row[dept.department] = dept.series.find((p) => p.period === period)?.value ?? 0;
    }
    return row;
  });
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="period" tickFormatter={formatPeriodShort} tickLine={false} axisLine={false} tick={AXIS} />
        <YAxis
          width={56}
          tickFormatter={(v: number) => formatValue(v, payload.unit, { compact: true })}
          tickLine={false}
          axisLine={false}
          tick={AXIS}
        />
        <Tooltip
          labelFormatter={(label) => formatPeriod(String(label))}
          formatter={(value, name) => [formatValue(Number(value), payload.unit), String(name)]}
        />
        <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
        {payload.by_department.map((dept, i) => (
          <Line
            key={dept.department}
            type="monotone"
            dataKey={dept.department}
            stroke={DEPARTMENT_PALETTE[i % DEPARTMENT_PALETTE.length]}
            strokeWidth={1.75}
            dot={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function LatestBreakdown({ payload, accent, height }: Required<Omit<TrendChartProps, "kind">>) {
  const latest = payload.periods.at(-1);
  const rows = payload.by_department
    .map((dept) => ({
      department: dept.department,
      value: dept.series.find((p) => p.period === latest)?.value ?? 0,
    }))
    .sort((a, b) => b.value - a.value);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 24, bottom: 0, left: 8 }}>
        <CartesianGrid stroke={GRID} horizontal={false} />
        <XAxis
          type="number"
          tickFormatter={(v: number) => formatValue(v, payload.unit, { compact: true })}
          tickLine={false}
          axisLine={false}
          tick={AXIS}
        />
        <YAxis type="category" dataKey="department" width={170} tickLine={false} axisLine={false} tick={AXIS} />
        <Tooltip
          cursor={{ fill: "#f2f4f7" }}
          formatter={(value) => [formatValue(Number(value), payload.unit), latest ? formatPeriod(latest) : ""]}
        />
        <Bar dataKey="value" fill={accent} radius={[0, 4, 4, 0]} barSize={14} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function TrendChart({ payload, kind = "trend", accent = "#3e63dd", height = 260 }: TrendChartProps) {
  return (
    <div className="chart" data-testid={`chart-${payload.key}-${kind}`}>
      {kind === "trend" && <TotalTrend payload={payload} accent={accent} height={height} />}
      {kind === "departments" && <DepartmentLines payload={payload} height={height} />}
      {kind === "breakdown" && <LatestBreakdown payload={payload} accent={accent} height={height} />}
    </div>
  );
}

export function Sparkline({ payload, accent }: { payload: MetricPayload; accent: string }) {
  return (
    <div className="sparkline" aria-hidden="true">
      <ResponsiveContainer width="100%" height={44}>
        <LineChart data={payload.total} margin={{ top: 4, right: 2, bottom: 4, left: 2 }}>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Line type="monotone" dataKey="value" stroke={accent} strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
