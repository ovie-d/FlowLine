"use client";

import { useIsFetching, useIsMutating } from "@tanstack/react-query";

/** Thin bar along the bottom edge of the top bar while any request is in flight. */
export function FetchBar() {
  const busy = useIsFetching() + useIsMutating() > 0;
  return (
    <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-0.5 overflow-hidden">
      {busy && <div className="fl-progress h-full w-2/5 bg-accent" />}
    </div>
  );
}
