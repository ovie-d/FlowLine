/**
 * Flowline mark: a flow line that runs in from the left, bends up and right,
 * and becomes an "F" — the pipe is the letter. Shared by the intro, the top
 * bar, public/logo.svg and app/icon.svg (keep the paths in sync).
 */

export const MARK_MAIN_PATH = "M6 50 H20 Q26 50 26 44 V20 Q26 14 32 14 H54";
export const MARK_BAR_PATH = "M26 32 H44";
export const MARK_NODE = { cx: 54, cy: 14, r: 4 };

type MarkProps = {
  size?: number;
  className?: string;
  title?: string;
};

export function FlowlineMark({ size = 28, className, title = "Flowline" }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label={title}
      className={className}
    >
      <path
        d={MARK_MAIN_PATH}
        fill="none"
        stroke="var(--accent)"
        strokeWidth={6}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d={MARK_BAR_PATH}
        fill="none"
        stroke="var(--accent)"
        strokeWidth={6}
        strokeLinecap="round"
      />
      <circle {...MARK_NODE} fill="var(--safe)" />
    </svg>
  );
}

export function FlowlineLogo({ size = 28 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2">
      <FlowlineMark size={size} title="" />
      <span
        className="font-semibold text-fg"
        style={{ letterSpacing: "0.28em", fontSize: size * 0.55 }}
      >
        FLOWLINE
      </span>
    </span>
  );
}
