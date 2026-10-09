/**
 * Anonymous visitor id for the online demo: a random id kept in this browser, sent as
 * X-Flowline-Visitor so the server can keep a per-visitor sandbox and count the daily
 * AI prompts. It is not linked to any personal data. Local installs ignore it.
 */

const KEY = "flowline.visitor";
let memo: string | null = null;

function fresh(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function visitorId(): string {
  if (memo) return memo;
  if (typeof window === "undefined") return "";
  try {
    memo = localStorage.getItem(KEY);
    if (!memo || !/^[A-Za-z0-9_-]{8,64}$/.test(memo)) {
      memo = fresh();
      localStorage.setItem(KEY, memo);
    }
  } catch {
    memo = memo ?? fresh(); // storage blocked: one id for this page view
  }
  return memo;
}

export function visitorHeaders(): Record<string, string> {
  const id = visitorId();
  return id ? { "X-Flowline-Visitor": id } : {};
}
