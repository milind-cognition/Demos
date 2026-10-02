import { Notice, PageHeader } from "./components/Panel";
import { Sidebar } from "./components/Sidebar";
import { findStoryboard } from "./config/storyboards";
import { MetricsProvider, useMetrics } from "./lib/MetricsContext";
import { useHashRoute, type Route } from "./lib/router";
import { MetricPage } from "./pages/MetricPage";
import { StoryboardPage } from "./pages/StoryboardPage";
import type { MetricPayload } from "./types";

function NotFound({ what }: { what: string }) {
  return (
    <div className="page">
      <PageHeader eyebrow="Not found" title="Nothing here yet" description={`No ${what} matches this address.`} />
    </div>
  );
}

function Content({ route, metrics }: { route: Route; metrics: Record<string, MetricPayload> }) {
  if (route.name === "metric") {
    const payload = metrics[route.key];
    return payload ? <MetricPage payload={payload} /> : <NotFound what={`metric "${route.key}"`} />;
  }
  if (route.name === "storyboard") {
    const storyboard = findStoryboard(route.id);
    return storyboard ? <StoryboardPage storyboard={storyboard} metrics={metrics} /> : <NotFound what="storyboard" />;
  }
  return <NotFound what="page" />;
}

function Shell() {
  const route = useHashRoute();
  const state = useMetrics();
  const activeStoryboard = route.name === "storyboard" ? findStoryboard(route.id) : undefined;
  return (
    <div className="app">
      <Sidebar
        route={route}
        metrics={state.status === "ready" ? state.index.metrics : []}
        activeStoryboardId={activeStoryboard?.id}
      />
      <main className="main">
        {state.status === "loading" && <div className="loading">Loading metrics…</div>}
        {state.status === "error" && <Notice tone="error">{state.error}</Notice>}
        {state.status === "ready" && <Content route={route} metrics={state.metrics} />}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <MetricsProvider>
      <Shell />
    </MetricsProvider>
  );
}
