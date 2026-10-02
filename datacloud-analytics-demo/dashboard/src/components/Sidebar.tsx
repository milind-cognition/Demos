import { STORYBOARDS } from "../config/storyboards";
import { metricHref, storyboardHref, type Route } from "../lib/router";
import type { MetricIndexEntry } from "../types";

export interface SidebarProps {
  route: Route;
  metrics: MetricIndexEntry[];
  activeStoryboardId: string | undefined;
}

export function Sidebar({ route, metrics, activeStoryboardId }: SidebarProps) {
  return (
    <aside className="sidebar">
      <a className="brand" href={storyboardHref(STORYBOARDS[0]?.id ?? "")}>
        <span className="brand__mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <span className="brand__text">
          <strong>DataCloud</strong> Analytics
        </span>
      </a>

      <nav aria-label="Storyboards" className="nav-group">
        <span className="nav-group__title">Storyboards</span>
        {STORYBOARDS.map((storyboard) => (
          <a
            key={storyboard.id}
            href={storyboardHref(storyboard.id)}
            className={`nav-link${route.name === "storyboard" && activeStoryboardId === storyboard.id ? " is-active" : ""}`}
          >
            {storyboard.title}
          </a>
        ))}
      </nav>

      <nav aria-label="Metrics" className="nav-group">
        <span className="nav-group__title">Metrics</span>
        {metrics.map((metric) => (
          <a
            key={metric.key}
            href={metricHref(metric.key)}
            className={`nav-link${route.name === "metric" && route.key === metric.key ? " is-active" : ""}`}
          >
            {metric.label}
            <code className="nav-link__key" title={metric.key}>
              {metric.key}
            </code>
          </a>
        ))}
      </nav>

      <footer className="sidebar__footer">
        <span className="status-dot" aria-hidden="true" />
        Seed snapshot · local only
      </footer>
    </aside>
  );
}
