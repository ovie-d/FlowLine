"use client";

/**
 * First-load intro (once per browser session): an amber pulse travels along a
 * line that bends into the Flowline mark, the wordmark fades in, then the
 * dashboard fades up. Skippable by click, Escape or the Skip button.
 * prefers-reduced-motion: static logo for 0.5 s instead.
 * Before hydration the overlay is a blank cover, so the dashboard never flashes
 * and the animation starts from an empty line.
 */

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  useCallback,
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

const STORAGE_KEY = "flowline.introSeen";
const PLAY_MS = 2600;
const REDUCED_MS = 500;

// Intro geometry (viewBox 0 0 520 120): the mark from FlowlineMark scaled ×2,
// with the flow line extended to the left edge.
const LINE = "M0 94 H140 Q152 94 152 82 V34 Q152 22 164 22 H208";
const BAR = "M152 58 H188";
const NODE = { cx: 208, cy: 22, r: 8 };

function readSeen(): boolean {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false; // storage blocked: show the intro, it just won't be remembered
  }
}

function markSeen(): void {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, "1");
  } catch {
    /* ignore */
  }
}

const noSubscribe = () => () => {};

export function IntroGate({ children }: { children: ReactNode }) {
  // null on the server / during hydration: cover the page without animating.
  const seenAtLoad = useSyncExternalStore<boolean | null>(noSubscribe, readSeen, () => null);
  const [finished, setFinished] = useState(false);
  const reduce = useReducedMotion() ?? false;

  const playing = seenAtLoad === false && !finished;
  const revealed = seenAtLoad === true || finished;

  const finish = useCallback(() => {
    markSeen();
    setFinished(true);
  }, []);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(finish, reduce ? REDUCED_MS : PLAY_MS);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") finish();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("keydown", onKey);
    };
  }, [playing, reduce, finish]);

  return (
    <>
      <motion.div
        className="h-full"
        initial={false}
        animate={revealed ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }}
        transition={{ duration: reduce ? 0 : 0.45, ease: "easeOut" }}
      >
        {children}
      </motion.div>
      <AnimatePresence>
        {(seenAtLoad === null || playing) && (
          <IntroOverlay
            key="intro"
            art={seenAtLoad === null ? "none" : reduce ? "static" : "animated"}
            onSkip={finish}
          />
        )}
      </AnimatePresence>
    </>
  );
}

type Art = "none" | "static" | "animated";

function IntroOverlay({ art, onSkip }: { art: Art; onSkip: () => void }) {
  return (
    <motion.div
      className="fixed inset-0 z-50 flex cursor-pointer items-center justify-center bg-bg"
      initial={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4, ease: "easeInOut" }}
      onClick={onSkip}
      role="presentation"
    >
      {art !== "none" && <IntroArt animated={art === "animated"} />}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onSkip();
        }}
        className="absolute bottom-6 right-6 rounded border border-border px-3 py-1 text-xs text-muted hover:text-fg"
      >
        Skip intro (Esc)
      </button>
    </motion.div>
  );
}

function IntroArt({ animated }: { animated: boolean }) {
  const draw = (delay: number, duration: number) =>
    animated
      ? {
          // Opacity too: a zero-length path with round caps still paints a dot.
          initial: { pathLength: 0, opacity: 0 },
          animate: { pathLength: 1, opacity: 1 },
          transition: {
            delay,
            duration,
            ease: "easeInOut" as const,
            opacity: { delay, duration: 0.05 },
          },
        }
      : { initial: false as const };

  return (
    <svg
      viewBox="0 0 520 120"
      className="w-[min(560px,86vw)]"
      role="img"
      aria-label="Flowline"
    >
      <defs>
        <filter id="fl-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <motion.path
        d={LINE}
        fill="none"
        stroke="var(--accent)"
        strokeWidth={10}
        strokeLinecap="round"
        strokeLinejoin="round"
        {...draw(0, 1.1)}
      />
      {animated && (
        <motion.path
          d={LINE}
          fill="none"
          stroke="#ffd98a"
          strokeWidth={12}
          strokeLinecap="round"
          filter="url(#fl-glow)"
          initial={{ pathLength: 0.08, pathOffset: 0, opacity: 0 }}
          animate={{ pathOffset: 0.92, opacity: [0, 1, 1, 0] }}
          transition={{ duration: 1.25, ease: "easeInOut" }}
        />
      )}
      <motion.path
        d={BAR}
        fill="none"
        stroke="var(--accent)"
        strokeWidth={10}
        strokeLinecap="round"
        {...draw(1.0, 0.35)}
      />
      <motion.circle
        {...NODE}
        fill="var(--safe)"
        filter={animated ? "url(#fl-glow)" : undefined}
        initial={animated ? { scale: 0, opacity: 0 } : false}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 1.15, duration: 0.3 }}
        style={{ transformOrigin: `${NODE.cx}px ${NODE.cy}px` }}
      />
      <motion.text
        x={236}
        y={74}
        fill="var(--text)"
        fontSize={40}
        fontWeight={600}
        letterSpacing={9}
        style={{ fontFamily: "var(--font-sans), 'Helvetica Neue', Arial, sans-serif" }}
        initial={animated ? { opacity: 0, x: 8 } : false}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 1.35, duration: 0.55, ease: "easeOut" }}
      >
        FLOWLINE
      </motion.text>
    </svg>
  );
}
