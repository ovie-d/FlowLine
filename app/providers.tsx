"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

// The hosted demo's free API server sleeps when idle and takes about a minute to wake:
// keep retrying for ~90 s there instead of giving up after one retry.
const HOSTED = process.env.NEXT_PUBLIC_FLOWLINE_HOSTED === "1";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: HOSTED ? 9 : 1,
            retryDelay: HOSTED ? 10_000 : undefined,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
