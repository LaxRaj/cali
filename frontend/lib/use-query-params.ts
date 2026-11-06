"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";

const EVENT = "cali:urlchange";

function subscribe(cb: () => void) {
  window.addEventListener("popstate", cb);
  window.addEventListener(EVENT, cb);
  return () => {
    window.removeEventListener("popstate", cb);
    window.removeEventListener(EVENT, cb);
  };
}

/**
 * Filters live in the URL (shareable, survive refresh and back). The server snapshot is "" so a static page hydrates
 * with defaults and then re-renders from the real query string, without a hydration mismatch or a Suspense boundary.
 */
export function useQueryParams(): [URLSearchParams, (patch: Record<string, string | null>) => void] {
  const search = useSyncExternalStore(
    subscribe,
    () => window.location.search,
    () => "",
  );
  const params = useMemo(() => new URLSearchParams(search), [search]);
  const set = useCallback((patch: Record<string, string | null>) => {
    const p = new URLSearchParams(window.location.search);
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === "") p.delete(k);
      else p.set(k, v);
    }
    const qs = p.toString();
    window.history.replaceState(window.history.state, "", qs ? `?${qs}` : window.location.pathname);
    window.dispatchEvent(new Event(EVENT));
  }, []);
  return [params, set];
}
