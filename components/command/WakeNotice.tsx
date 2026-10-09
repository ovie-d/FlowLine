"use client";

import { useIsFetching } from "@tanstack/react-query";
import { useEffect, useState } from "react";

const HOSTED = process.env.NEXT_PUBLIC_FLOWLINE_HOSTED === "1";
const SLOW_MS = 4000;

/** Hosted demo only: say so when the free API server is still waking up. */
export function WakeNotice({ waiting }: { waiting: boolean }) {
  const fetching = useIsFetching() > 0;
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!HOSTED || !waiting) return;
    const t = window.setTimeout(() => setSlow(true), SLOW_MS);
    return () => window.clearTimeout(t);
  }, [waiting]);
  if (!HOSTED || !waiting || !slow || !fetching) return null;
  return (
    <div role="status" className="border-b border-border bg-panel-2 px-4 py-1.5 text-[12px] text-fg">
      <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-highlight align-middle" aria-hidden />
      Waking up the free demo server. After a quiet spell this takes about a minute; thanks
      for your patience.
    </div>
  );
}
