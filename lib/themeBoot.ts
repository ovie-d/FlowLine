/** Server-safe theme constants (no "use client"): used by app/layout.tsx. */

export const THEME_KEY = "flowline.theme";

/** Inline <head> script: apply the saved theme before first paint (no flash). */
export const THEME_BOOT_SCRIPT = `try{var t=localStorage.getItem("${THEME_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}catch(e){}`;
