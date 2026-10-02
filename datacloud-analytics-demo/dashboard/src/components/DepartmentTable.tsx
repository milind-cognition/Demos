import { formatDelta, formatPeriod, formatValue } from "../lib/format";
import { summarize } from "../lib/summary";
import type { MetricPayload } from "../types";

export function DepartmentTable({ payload }: { payload: MetricPayload }) {
  const rows = payload.by_department.map((dept) => ({
    department: dept.department,
    ...summarize(dept.series, payload.higher_is_better),
  }));
  const total = { department: "All Departments", ...summarize(payload.total, payload.higher_is_better) };
  const latest = payload.periods.at(-1);
  const previous = payload.periods.at(-2);
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Department</th>
          <th className="num">{latest ? formatPeriod(latest) : "Latest"}</th>
          <th className="num">{previous ? formatPeriod(previous) : "Prior"}</th>
          <th className="num">Change</th>
          <th className="num">12-mo avg</th>
        </tr>
      </thead>
      <tbody>
        {[...rows, total].map((row) => (
          <tr key={row.department} className={row === total ? "table__total" : undefined}>
            <td>{row.department}</td>
            <td className="num">{row.latest ? formatValue(row.latest.value, payload.unit) : "—"}</td>
            <td className="num">{row.previous ? formatValue(row.previous.value, payload.unit) : "—"}</td>
            <td className="num">
              {row.delta !== null ? (
                <span className={`delta delta--${row.sentiment}`}>{formatDelta(row.delta, payload.unit)}</span>
              ) : (
                "—"
              )}
            </td>
            <td className="num">{row.average !== null ? formatValue(row.average, payload.unit) : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
