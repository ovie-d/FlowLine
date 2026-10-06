"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** Native <dialog> modal: focus handling, Escape to close, backdrop click to close. */
export function Modal({
  open,
  title,
  onClose,
  children,
  wide = false,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement | null>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      aria-labelledby="modal-title"
      className={`m-auto max-h-[85vh] overflow-hidden rounded-xl border border-border bg-panel p-0 text-fg backdrop:bg-black/60`}
      style={{ width: `min(92vw, ${wide ? 980 : 640}px)` }}
    >
      <div className="flex max-h-[85vh] flex-col">
        <header className="flex items-center justify-between border-b border-border px-5 py-3">
          <h2 id="modal-title" className="text-[15px] font-semibold">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded px-2 text-muted hover:text-fg">
            ✕
          </button>
        </header>
        <div className="min-h-0 overflow-y-auto px-5 py-4">{children}</div>
      </div>
    </dialog>
  );
}
