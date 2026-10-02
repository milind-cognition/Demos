import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { loadMetrics, type MetricsBundle } from "./data";

export type MetricsState =
  | { status: "loading" }
  | { status: "error"; error: string }
  | ({ status: "ready" } & MetricsBundle);

const MetricsContext = createContext<MetricsState>({ status: "loading" });

export function MetricsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<MetricsState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    loadMetrics()
      .then((bundle) => !cancelled && setState({ status: "ready", ...bundle }))
      .catch((error: unknown) => !cancelled && setState({ status: "error", error: String(error) }));
    return () => {
      cancelled = true;
    };
  }, []);

  return <MetricsContext.Provider value={state}>{children}</MetricsContext.Provider>;
}

export function useMetrics(): MetricsState {
  return useContext(MetricsContext);
}
