export function Footer() {
  return (
    <footer className="flex shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-0.5 border-t border-border bg-panel px-4 py-1.5 text-[11px] text-muted">
      <span className="text-fg/90">
        Forecasts are based on historical public incident data. Flowline supports engineering
        judgment; it does not certify any pipe as safe.
      </span>
      <span>
        Data: Canada Energy Regulator incident data &amp; pipeline systems (OGL–Canada) · Environment
        and Climate Change Canada · © OpenStreetMap contributors (routing via OSRM) · Open-Meteo ·
        Mapbox
      </span>
    </footer>
  );
}
