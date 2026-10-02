import { useEffect, useState } from "react";

export type Route =
  | { name: "storyboard"; id: string | null }
  | { name: "metric"; key: string }
  | { name: "not-found"; path: string };

export function parseHash(hash: string): Route {
  const path = hash.replace(/^#/, "") || "/";
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  if (parts.length === 0) return { name: "storyboard", id: null };
  if (parts[0] === "storyboards" && parts[1]) return { name: "storyboard", id: parts[1] };
  if (parts[0] === "metrics" && parts[1]) return { name: "metric", key: parts[1] };
  return { name: "not-found", path };
}

export const storyboardHref = (id: string) => `#/storyboards/${encodeURIComponent(id)}`;
export const metricHref = (key: string) => `#/metrics/${encodeURIComponent(key)}`;

export function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => {
      setRoute(parseHash(window.location.hash));
      window.scrollTo?.({ top: 0 });
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
