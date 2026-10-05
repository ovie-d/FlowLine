"use client";

import { useId } from "react";

type Props = {
  /** Explanation shown on hover and keyboard focus. */
  tip: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "bottom";
  align?: "center" | "start" | "end";
  className?: string;
  /** False inside buttons (no nested tab stop); the tip then shows on hover only. */
  focusable?: boolean;
};

/**
 * Hover / focus tooltip for a badge or number. The trigger is focusable and
 * described by the tip, so keyboard and screen-reader users get the same text.
 */
export function InfoTip({ tip, children, side = "top", align = "center", className = "", focusable = true }: Props) {
  const id = useId();
  return (
    <span className={`fl-tip inline-flex ${className}`}>
      <span tabIndex={focusable ? 0 : undefined} aria-describedby={id}
        className="cursor-help rounded-sm decoration-dotted underline-offset-2 hover:underline">
        {children}
      </span>
      <span id={id} role="tooltip" className="fl-tip-body" data-side={side === "bottom" ? "bottom" : undefined}
        data-align={align === "center" ? undefined : align}>
        {tip}
      </span>
    </span>
  );
}
