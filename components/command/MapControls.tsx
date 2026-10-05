"use client";

import { useState } from "react";
import {
  LAYER_LABEL,
  STYLE_LABEL,
  setMapPrefs,
  type LayerKey,
  type MapPrefs,
  type StyleKey,
} from "@/lib/mapPrefs";
import { InfoTip } from "@/components/ui/InfoTip";

const STYLES: StyleKey[] = ["auto", "dark", "light", "streets", "satellite"];
const LAYERS: LayerKey[] = ["incidents", "heatmap", "pipelines", "bases", "crossings"];

const LAYER_TIP: Record<LayerKey, string> = {
  incidents: "CER-reported incidents, coloured by hazard. Grouped into numbered clusters when zoomed out; click a cluster to zoom in, click a dot for details.",
  heatmap: "Density of the incidents currently shown (same year range and hazard filter).",
  pipelines: "CER pipeline systems (simplified lines), for orientation only.",
  bases: "Crew bases from the sample crew table — to be validated with the operator.",
  crossings: "Where CER pipeline systems cross OpenStreetMap rivers and streams in Alberta. Context only; not a model input.",
};

type Props = {
  prefs: MapPrefs;
  offline: boolean;
  crossingsNote: string | null;
  /** False on the Dispatch page, which shows no incident layers. */
  incidentLayers?: boolean;
  /** Keyless open basemaps (MapLibre) instead of Mapbox. */
  openBasemap?: boolean;
};

/** Basemap style, 3D terrain, globe and layer toggles (per browser, display only). */
export function MapControls({ prefs, offline, crossingsNote, incidentLayers = true, openBasemap = false }: Props) {
  const [open, setOpen] = useState(false);
  const toggleLayer = (k: LayerKey) =>
    setMapPrefs((p) => ({ ...p, layers: { ...p.layers, [k]: !p.layers[k] } }));

  return (
    <div className="w-[230px] max-w-[calc(100vw-5rem)] rounded-md border border-border bg-panel/95 text-[12px] shadow backdrop-blur">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-2.5 py-1.5 font-semibold text-fg hover:text-accent"
      >
        <span className="flex items-center gap-1.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <path d="M12 2 2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
          Map &amp; layers
        </span>
        <span aria-hidden className="text-muted">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="grid gap-2.5 border-t border-border px-2.5 pb-2.5 pt-2">
          <fieldset disabled={offline} className="disabled:opacity-50">
            <legend className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">Basemap</legend>
            <div className="flex flex-wrap gap-1" role="radiogroup" aria-label="Basemap style">
              {STYLES.map((s) => (
                <button
                  key={s}
                  type="button"
                  role="radio"
                  aria-checked={prefs.style === s}
                  onClick={() => setMapPrefs((p) => ({ ...p, style: s }))}
                  title={s === "auto" ? "Follows the app theme (dark or light)" : undefined}
                  className={`rounded border px-1.5 py-0.5 ${prefs.style === s ? "border-accent bg-panel-2 font-semibold text-fg" : "border-border text-muted hover:text-fg"}`}
                >
                  {STYLE_LABEL[s]}
                </button>
              ))}
            </div>
            <div className="mt-2 grid gap-1">
              <Check
                label="3D terrain"
                checked={prefs.terrain}
                onChange={() => setMapPrefs((p) => ({ ...p, terrain: !p.terrain }))}
                tip="Mapbox elevation model; tilts the map. Drag with the right mouse button (or Ctrl + drag) to rotate."
              />
              <Check
                label="Globe when zoomed out"
                checked={prefs.globe}
                onChange={() => setMapPrefs((p) => ({ ...p, globe: !p.globe }))}
                tip="Shows the Earth as a globe at low zoom; flat map when zoomed in."
              />
            </div>
            {offline && <p className="mt-1 text-[11px] text-muted">Basemap options need WebGL (interactive map).</p>}
            {openBasemap && (
              <p className="mt-1 text-[11px] text-muted">
                Open basemaps (OpenFreeMap, Esri imagery): no Mapbox token needed. Add one in .env.local for Mapbox styles.
              </p>
            )}
          </fieldset>
          <fieldset>
            <legend className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">Layers</legend>
            <div className="grid gap-1">
              {LAYERS.filter((k) => incidentLayers || (k !== "incidents" && k !== "heatmap")).map((k) => (
                <Check
                  key={k}
                  label={LAYER_LABEL[k]}
                  checked={prefs.layers[k]}
                  onChange={() => toggleLayer(k)}
                  tip={LAYER_TIP[k]}
                  disabled={offline && k === "heatmap"}
                />
              ))}
            </div>
            {prefs.layers.crossings && crossingsNote && <p className="mt-1 text-[11px] text-warn">{crossingsNote}</p>}
          </fieldset>
        </div>
      )}
    </div>
  );
}

function Check({
  label,
  checked,
  onChange,
  tip,
  disabled,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
  tip: string;
  disabled?: boolean;
}) {
  return (
    <div className={`flex items-center justify-between gap-2 ${disabled ? "opacity-50" : ""}`}>
      <label className="flex cursor-pointer items-center gap-1.5 text-fg">
        <input type="checkbox" checked={checked} onChange={onChange} disabled={disabled} className="accent-[var(--accent)]" />
        {label}
      </label>
      <InfoTip tip={tip} align="end">
        <span className="text-[11px] text-muted" aria-label={`About ${label}`}>ⓘ</span>
      </InfoTip>
    </div>
  );
}
